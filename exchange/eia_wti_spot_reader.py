"""Bounded HTTP reader for the fixed EIA WTI table; no polling lifecycle."""
from copy import deepcopy
from email.utils import parsedate_to_datetime
import math
import re
import threading
import time
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request

from .eia_wti_spot_table import SOURCE_URL, SCOPE, parse_eia_wti_spot_table

LIMIT = 2 * 1024 * 1024


class SpotSourceUnavailable(ValueError):
    pass


class SpotSourceDeferred(SpotSourceUnavailable):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def _positive(value, name, maximum=None):
    if (type(value) not in (int, float) or not math.isfinite(value) or value <= 0
            or (maximum is not None and value > maximum)):
        raise ValueError("explicit positive " + name + " required")
    return value


class EIAWTISpotReader:
    """Trusted host-owned reader, callable by the existing reference feed.

    Cadence and failure delay are explicit host choices, not provider SLA claims.
    The reader never starts a thread, scheduler, credentials or financial action.
    An injected response port is for the original trusted host/test composition,
    never for a caller-supplied HTTP body or alternate source.
    """
    def __init__(self, *, timeout_seconds, user_agent, minimum_fetch_seconds,
                 failure_backoff_seconds, open_response=None, monotonic=None,
                 wall_clock=None):
        self._timeout = _positive(timeout_seconds, "socket timeout", 30)
        self._minimum = _positive(minimum_fetch_seconds, "source request spacing")
        self._failure = _positive(failure_backoff_seconds, "failure backoff")
        if (type(user_agent) is not str or not 1 <= len(user_agent) <= 200
                or any(not 32 <= ord(char) < 127 for char in user_agent)):
            raise ValueError("non-secret printable source user agent required")
        if open_response is None:
            # No environment proxy, cookie jar, Authorization or ambient key.
            self._opener = build_opener(ProxyHandler({}), HTTPSHandler(), _NoRedirect())
            self._open = self._opener.open
        elif callable(open_response):
            self._opener, self._open = None, open_response
        else:
            raise ValueError("original bounded response port required")
        self._monotonic = monotonic or time.monotonic
        self._wall = wall_clock or time.time
        if not callable(self._monotonic) or not callable(self._wall):
            raise ValueError("original clocks required")
        self._agent = user_agent
        self._lock = threading.Lock()
        self._next = 0
        self._cached = None
        self._etag = None
        self._modified = None
        self._last = None

    @staticmethod
    def _validator(value):
        if value is None:
            return None
        if (type(value) is not str or len(value) > 512
                or any(not 32 <= ord(char) < 127 for char in value)):
            raise SpotSourceUnavailable("SPOT_SOURCE_VALIDATOR_REFUSED")
        return value

    def _retry_after(self, headers):
        raw = headers.get("Retry-After")
        if raw is None:
            return 0
        raw = raw.strip()
        if re.fullmatch(r"[0-9]+", raw):
            # Never shorten a valid provider delay. Extremely long values mean
            # no further requests from this reader, rather than a capped retry.
            return float("inf") if len(raw) > 12 else int(raw)
        try:
            instant = parsedate_to_datetime(raw)
            if instant.tzinfo is None:
                return 0
            return max(0, instant.timestamp() - self._wall())
        except (ValueError, TypeError, OverflowError):
            return 0

    def __call__(self, policy):
        if (type(policy) is not dict or policy.get("sourceURL") != SOURCE_URL
                or any(policy.get(key) != value for key, value in SCOPE.items())):
            raise SpotSourceUnavailable("SPOT_SOURCE_POLICY_DIFFERS")
        with self._lock:
            now = self._monotonic()
            if now < self._next:
                raise SpotSourceDeferred("SPOT_SOURCE_FETCH_DEFERRED")
            self._next = now + self._minimum
            headers = {"Accept": "text/html", "Accept-Encoding": "identity",
                       "User-Agent": self._agent}
            if self._cached is not None:
                if self._etag is not None:
                    headers["If-None-Match"] = self._etag
                if self._modified is not None:
                    headers["If-Modified-Since"] = self._modified
            request = Request(SOURCE_URL, headers=headers, method="GET")
            try:
                try:
                    response = self._open(request, timeout=self._timeout)
                except HTTPError as error:
                    response = error
                with response:
                    status = response.code
                    if response.geturl() != SOURCE_URL:
                        raise SpotSourceUnavailable("SPOT_SOURCE_ORIGIN_DIFFERS")
                    if status in (429, 503):
                        self._next = max(self._next, self._monotonic() + self._failure,
                                         self._monotonic() + self._retry_after(response.headers))
                        raise SpotSourceUnavailable("SPOT_SOURCE_HTTP_DEFERRED")
                    if status == 304:
                        if self._cached is None:
                            raise SpotSourceUnavailable("SPOT_SOURCE_CACHE_ABSENT")
                        self._last = {"status": "not-modified", "httpStatus": 304,
                                      "rawResponseSHA256": self._cached["rawResponseSHA256"]}
                        return deepcopy(self._cached)
                    if (status != 200 or response.headers.get_content_type() != "text/html"
                            or response.headers.get("Content-Encoding", "identity") != "identity"):
                        raise SpotSourceUnavailable("SPOT_SOURCE_RESPONSE_REFUSED")
                    raw = response.read(LIMIT + 1)
                    if type(raw) is not bytes or len(raw) > LIMIT:
                        raise SpotSourceUnavailable("SPOT_SOURCE_RESPONSE_TOO_LARGE")
                    parsed = parse_eia_wti_spot_table(raw)
                    etag = self._validator(response.headers.get("ETag"))
                    modified = self._validator(response.headers.get("Last-Modified"))
                # Only a fully decoded response replaces the previous cache.
                self._cached, self._etag, self._modified = deepcopy(parsed), etag, modified
                self._last = {"status": "read", "httpStatus": 200, "bytes": len(raw),
                              "rawResponseSHA256": parsed["rawResponseSHA256"]}
                return deepcopy(parsed)
            except Exception as error:
                self._next = max(self._next, self._monotonic() + self._failure)
                allowed = {"SPOT_SOURCE_VALIDATOR_REFUSED", "SPOT_SOURCE_ORIGIN_DIFFERS",
                           "SPOT_SOURCE_HTTP_DEFERRED", "SPOT_SOURCE_CACHE_ABSENT",
                           "SPOT_SOURCE_RESPONSE_REFUSED", "SPOT_SOURCE_RESPONSE_TOO_LARGE"}
                code = str(error) if isinstance(error, SpotSourceUnavailable) and str(error) in allowed else "SPOT_SOURCE_READ_UNAVAILABLE"
                self._last = {"status": "unavailable", "code": code,
                              "retainedSource": self._cached is not None}
                raise SpotSourceUnavailable(code) from None

    def transport_observation(self):
        """Non-secret diagnostics only; never source freshness or execution proof."""
        with self._lock:
            return deepcopy(self._last)
