"""Continuous reference observation over an explicitly verified source binding.

No provider URL, interval, freshness SLA, credentials or sample prices are chosen
here. The original host supplies an approved bounded reader and verified policy.
Reference observations never enter order matching or financial execution.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re
import threading
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

SCOPE = ("provider", "series", "commodity", "spec", "market", "priceType", "currency", "unit")


_DIAGNOSTIC_UNAVAILABLE = {"status": "diagnostic-unavailable"}
_TRANSPORT_CODES = {
    "SPOT_SOURCE_VALIDATOR_REFUSED", "SPOT_SOURCE_ORIGIN_DIFFERS",
    "SPOT_SOURCE_HTTP_DEFERRED", "SPOT_SOURCE_CACHE_ABSENT",
    "SPOT_SOURCE_RESPONSE_REFUSED", "SPOT_SOURCE_RESPONSE_TOO_LARGE",
    "SPOT_SOURCE_READ_UNAVAILABLE",
}


def _transport_observation(value):
    """Project only the original reader's finite, non-secret diagnostic schema."""
    if value is None:
        return None
    if type(value) is not dict:
        return dict(_DIAGNOSTIC_UNAVAILABLE)
    status = value.get("status")
    digest = value.get("rawResponseSHA256")
    valid_digest = type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
    if (status == "read" and set(value) == {"status", "httpStatus", "bytes", "rawResponseSHA256"}
            and type(value["httpStatus"]) is int and value["httpStatus"] == 200
            and type(value["bytes"]) is int and 0 < value["bytes"] <= 2 * 1024 * 1024
            and valid_digest):
        return deepcopy(value)
    if (status == "not-modified" and set(value) == {"status", "httpStatus", "rawResponseSHA256"}
            and type(value["httpStatus"]) is int and value["httpStatus"] == 304 and valid_digest):
        return deepcopy(value)
    if (status == "unavailable" and set(value) == {"status", "code", "retainedSource"}
            and type(value["code"]) is str and value["code"] in _TRANSPORT_CODES
            and type(value["retainedSource"]) is bool):
        return deepcopy(value)
    return dict(_DIAGNOSTIC_UNAVAILABLE)


def _instant(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("UTC timestamp required")
    return datetime.fromisoformat(value[:-1] + "+00:00")


class CommodityReferenceFeed:
    def __init__(self, policy, read, verify_policy, *, clock=None, observe_transport=None):
        if observe_transport is not None and not callable(observe_transport):
            raise ValueError("original transport observation port required")
        self._observe_transport = observe_transport
        self._transport = None
        policy = deepcopy(policy)
        if not callable(read) or not callable(verify_policy) or verify_policy(deepcopy(policy)) is not True:
            raise ValueError("verified original source policy and reader required")
        if any(not isinstance(policy.get(key), str) or not policy[key].strip() for key in SCOPE):
            raise ValueError("complete fixed reference series required")
        if policy["priceType"] != "spot-reference":
            raise ValueError("futures or executable NFT orders are not reference data")
        parsed = urlsplit(policy.get("sourceURL", ""))
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment):
            raise ValueError("public HTTPS source identity required")
        for key in ("pollSeconds", "maxSourceAgeSeconds", "maxClockSkewSeconds"):
            if type(policy.get(key)) is not int or policy[key] < (1 if key == "pollSeconds" else 0):
                raise ValueError("explicit source cadence and freshness policy required")
        self._source_zone = (None if policy["sourceTimezone"] == "unknown"
                             else ZoneInfo(policy["sourceTimezone"]))
        self._policy, self._read = policy, read
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock, self._fetch_lock = threading.RLock(), threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._last, self._attempt = None, None
        self._failed = False
        self._events = []
        self._resume_not_before = None
        self._resumed = False

    def refresh(self):
        # Serialize fetches: an older slow response cannot replace a newer read.
        with self._fetch_lock:
            at = self._clock().astimezone(timezone.utc)
            result = None
            try:
                row = deepcopy(self._read(deepcopy(self._policy)))
                completed = self._clock().astimezone(timezone.utc)
                if not isinstance(row, dict) or any(row.get(key) != self._policy[key] for key in SCOPE):
                    raise ValueError("reference series mismatch")
                price = row.get("price")
                if not isinstance(price, str) or len(price) > 80 or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", price) or Decimal(price) <= 0:
                    raise ValueError("positive decimal source price required")
                precision, source = row.get("sourcePrecision"), row.get("sourceAsOf")
                if precision == "date":
                    if not isinstance(source, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", source):
                        raise ValueError("source date precision mismatch")
                    observed_date = datetime.fromisoformat(source).date()
                    if self._source_zone is None:
                        start = end = None
                        # A civil source date can be tomorrow at the fetch site.
                        # This excludes impossible future dates without assigning
                        # an observation instant or an unsupported source zone.
                        latest_date = (completed + timedelta(
                            seconds=self._policy["maxClockSkewSeconds"], days=1)).date()
                        if observed_date > latest_date:
                            raise ValueError("future source date")
                    else:
                        start = datetime.fromisoformat(source).replace(tzinfo=self._source_zone)
                        end = start + timedelta(days=1)
                elif precision == "instant":
                    start = end = _instant(source)
                else:
                    raise ValueError("source precision not provided")
                if start is not None and start > completed + timedelta(seconds=self._policy["maxClockSkewSeconds"]):
                    raise ValueError("future source observation")
                result = {key: row[key] for key in SCOPE}
                result.update(price=price, sourceAsOf=source, sourcePrecision=precision,
                              fetchedAt=completed.isoformat().replace("+00:00", "Z"))
                evidence = {}
                if "sourceURL" in row and row["sourceURL"] != self._policy["sourceURL"]:
                    raise ValueError("source response URL differs")
                if "rawResponseSHA256" in row:
                    digest = row["rawResponseSHA256"]
                    if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                        raise ValueError("source response digest differs")
                    evidence["rawResponseSHA256"] = digest
                if "publicationDate" in row:
                    publication = row["publicationDate"]
                    if type(publication) is not str or re.fullmatch(r"\d{4}-\d{2}-\d{2}", publication) is None:
                        raise ValueError("source publication date differs")
                    published = datetime.fromisoformat(publication).date()
                    observation_date = (observed_date if precision == "date" else
                                        start.astimezone(self._source_zone or timezone.utc).date())
                    if published < observation_date:
                        raise ValueError("source publication precedes observation")
                    publication_limit = (completed + timedelta(
                        seconds=self._policy["maxClockSkewSeconds"],
                        days=1 if precision == "date" and self._source_zone is None else 0)).astimezone(
                            self._source_zone or timezone.utc).date()
                    if published > publication_limit:
                        raise ValueError("source publication exceeds fetch date")
                    evidence["publicationDate"] = publication
                if evidence:
                    result["sourceEvidence"] = evidence
            except (Exception, InvalidOperation):
                result = None
            # Capture metadata only after the reader has returned or raised. Do
            # not call it from snapshot(), under the UI state lock, or as another
            # request. A diagnostic failure never invalidates a good price.
            transport = None
            if self._observe_transport is not None:
                try:
                    transport = _transport_observation(self._observe_transport())
                except Exception:
                    transport = dict(_DIAGNOSTIC_UNAVAILABLE)
            with self._lock:
                self._transport = transport
                self._attempt = at.isoformat().replace("+00:00", "Z")
                self._failed = result is None
                if result is not None:
                    self._last = result
                    self._resumed = False
                self._events.append({"attemptedAt": self._attempt, "result": "unavailable" if self._failed else "read"})
                self._events = self._events[-20:]
        return self.snapshot()

    def snapshot(self):
        with self._lock:
            value = deepcopy(self._last)
            base = {"kind": "external-spot-reference", "sourceURL": self._policy["sourceURL"],
                    "lastAttemptAt": self._attempt, "events": deepcopy(self._events),
                    "executableOrder": False, "conversionPerformed": False}
            if self._resumed:
                base["resumedObservation"] = True
            if self._observe_transport is not None:
                base["transportObservation"] = {
                    "value": deepcopy(self._transport),
                    "attemptCorrelation": "NOT_ESTABLISHED",
                    "meaning": "last reader transport metadata, not price validity, freshness or execution",
                }
            if value is None:
                return dict(base, status="unavailable", lastSuccessful=None, price=None)
            now = self._clock().astimezone(timezone.utc)
            unknown_calendar = value["sourcePrecision"] == "date" and self._source_zone is None
            if unknown_calendar:
                minimum = maximum = None
                status = "unknown"
            else:
                if value["sourcePrecision"] == "date":
                    start = datetime.fromisoformat(value["sourceAsOf"]).replace(tzinfo=self._source_zone)
                    end = start + timedelta(days=1)
                else:
                    start = end = _instant(value["sourceAsOf"])
                minimum = max(0, int((now - end).total_seconds()))
                maximum = max(0, int((now - start).total_seconds()))
                age = self._policy["maxSourceAgeSeconds"]
                status = "stale" if minimum > age else ("fresh" if maximum <= age else "unknown")
            if self._failed:
                status = "unavailable"
            return dict(base, **value, status=status, lastSuccessful=value["fetchedAt"],
                        sourceDelay={"minimumSeconds": minimum, "maximumSeconds": maximum},
                        sourceTimezone=(None if unknown_calendar else
                                        self._policy["sourceTimezone"] if self._source_zone is not None else "UTC"),
                        retainedValue=self._failed)


    def resume_validated_observation(self, value, *, not_before, verify):
        """Retain an original observation without recording another source read.

        The trusted composition verifies its original response and timestamps.
        This port neither fetches data nor updates the original fetchedAt/event.
        """
        value = deepcopy(value)
        if (not callable(verify) or verify(deepcopy(value)) is not True
                or not isinstance(not_before, datetime) or not_before.tzinfo is not timezone.utc):
            raise ValueError("verified original continuation required")
        with self._lock:
            if self._thread is not None or self._last is not None or self._attempt is not None:
                raise ValueError("continuation is initial construction only")
            self._last = value["last"]
            self._attempt = value["attempt"]
            self._events = value["events"]
            self._transport = value["transport"]
            self._resume_not_before = not_before
            self._resumed = True

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            def run():
                if self._resume_not_before is not None:
                    delay = max(0, (self._resume_not_before - self._clock().astimezone(timezone.utc)).total_seconds())
                    if self._stop.wait(delay):
                        return
                while not self._stop.is_set():
                    self.refresh()
                    self._stop.wait(self._policy["pollSeconds"])
            self._thread = threading.Thread(target=run, name="commodity-reference-reader", daemon=True)
            self._thread.start()

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
