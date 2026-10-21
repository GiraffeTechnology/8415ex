"""Explicit keyless petroleum bulk supply; no scheduler or source fallback."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from urllib.error import HTTPError
from urllib.request import Request

from .eia_wti_spot_reader import EIAWTISpotReader, SpotSourceDeferred, SpotSourceUnavailable
from .eia_wti_spot_table import SCOPE
from .eia_wti_bulk_series import BULK_URL
from .eia_wti_bulk_archive import MAX_ARCHIVE_BYTES, select_eia_wti_bulk_archive

MANIFEST_URL = "https://www.eia.gov/opendata/bulk/manifest.txt"
MANIFEST_LIMIT = 256 * 1024


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate manifest field")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonfinite manifest constant")


def _petroleum(raw):
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                       parse_constant=_reject_constant)
    item = value["dataset"]["PET"]
    if (type(item) is not dict or item.get("identifier") != "PET"
            or item.get("data_set") != "PET" or item.get("accessURL") != BULK_URL
            or item.get("accessLevel") != "public"):
        raise ValueError("fixed public petroleum distribution required")
    stamp = item.get("last_updated")
    if type(stamp) is not str or len(stamp) > 64:
        raise ValueError("petroleum update timestamp required")
    updated = datetime.fromisoformat(stamp)
    if updated.tzinfo is None or updated.utcoffset() is None:
        raise ValueError("petroleum update offset required")
    marker = hashlib.sha256(json.dumps(item, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=True).encode()).hexdigest()
    return stamp, marker


class EIAWTIBulkReader(EIAWTISpotReader):
    """Use the existing bounded reader's clocks, spacing and backoff contract.

    This is an explicit source-format choice, never an HTML failure fallback.
    The original constructor starts no thread and makes no request. Its trusted
    response port, socket timeout and non-secret diagnostics are reused.
    """
    def __init__(self, **options):
        super().__init__(**options)
        self._petroleum_marker = None
        self._bulk_evidence = None

    def _get(self, url, limit, content_types):
        request = Request(url, headers={"Accept": ", ".join(content_types),
                          "Accept-Encoding": "identity", "User-Agent": self._agent},
                          method="GET")
        try:
            response = self._open(request, timeout=self._timeout)
        except HTTPError as error:
            response = error
        with response:
            if response.geturl() != url:
                raise SpotSourceUnavailable("BULK_SOURCE_ORIGIN_DIFFERS")
            if response.code in (429, 503):
                self._next = max(self._next, self._monotonic() + self._failure,
                                 self._monotonic() + self._retry_after(response.headers))
                raise SpotSourceUnavailable("BULK_SOURCE_HTTP_DEFERRED")
            if (response.code != 200
                    or response.headers.get_content_type() not in content_types
                    or response.headers.get("Content-Encoding", "identity") != "identity"):
                raise SpotSourceUnavailable("BULK_SOURCE_RESPONSE_REFUSED")
            raw = response.read(limit + 1)
            if type(raw) is not bytes or not 0 < len(raw) <= limit:
                raise SpotSourceUnavailable("BULK_SOURCE_RESPONSE_BOUND")
            return raw

    def __call__(self, policy):
        if (type(policy) is not dict or policy.get("sourceURL") != BULK_URL
                or any(policy.get(key) != value for key, value in SCOPE.items())):
            raise SpotSourceUnavailable("BULK_SOURCE_POLICY_DIFFERS")
        with self._lock:
            now = self._monotonic()
            if now < self._next:
                raise SpotSourceDeferred("BULK_SOURCE_FETCH_DEFERRED")
            self._next = now + self._minimum
            try:
                raw = self._get(MANIFEST_URL, MANIFEST_LIMIT,
                                ("text/plain", "application/json"))
                stamp, marker = _petroleum(raw)
                manifest_hash = hashlib.sha256(raw).hexdigest()
                if self._cached is not None and marker == self._petroleum_marker:
                    self._last = {"status": "petroleum-unchanged",
                                  "manifestSHA256": manifest_hash,
                                  "datasetUpdatedAt": stamp,
                                  "archiveDownloaded": False,
                                  "bulkEvidence": deepcopy(self._bulk_evidence)}
                    return deepcopy(self._cached)
                archive = self._get(BULK_URL, MAX_ARCHIVE_BYTES,
                                    ("application/x-zip-compressed", "application/zip"))
                selected = select_eia_wti_bulk_archive(archive)
                observation = selected["observation"]
                line_hash = observation["rawResponseSHA256"]
                observation["rawResponseSHA256"] = selected["archiveEvidence"]["sha256"]
                observation["responseDigestScope"] = "complete-petroleum-archive"
                evidence = dict(selected["archiveEvidence"], selectedLineSHA256=line_hash,
                                manifestSHA256=manifest_hash, datasetUpdatedAt=stamp)
                # Publish the new cache only after the complete archive verifies.
                self._cached = deepcopy(observation)
                self._petroleum_marker = marker
                self._bulk_evidence = deepcopy(evidence)
                self._last = {"status": "read", "archiveDownloaded": True,
                              "bulkEvidence": evidence}
                return deepcopy(observation)
            except Exception as error:
                self._next = max(self._next, self._monotonic() + self._failure)
                allowed = {"BULK_SOURCE_ORIGIN_DIFFERS", "BULK_SOURCE_HTTP_DEFERRED",
                           "BULK_SOURCE_RESPONSE_REFUSED", "BULK_SOURCE_RESPONSE_BOUND"}
                code = str(error) if isinstance(error, SpotSourceUnavailable) and str(error) in allowed else "BULK_SOURCE_READ_UNAVAILABLE"
                self._last = {"status": "unavailable", "code": code,
                              "retainedSource": self._cached is not None}
                raise SpotSourceUnavailable(code) from None
