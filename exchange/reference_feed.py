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


def _instant(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("UTC timestamp required")
    return datetime.fromisoformat(value[:-1] + "+00:00")


class CommodityReferenceFeed:
    def __init__(self, policy, read, verify_policy, *, clock=None):
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
            with self._lock:
                self._attempt = at.isoformat().replace("+00:00", "Z")
                self._failed = result is None
                if result is not None:
                    self._last = result
                self._events.append({"attemptedAt": self._attempt, "result": "unavailable" if self._failed else "read"})
                self._events = self._events[-20:]
        return self.snapshot()

    def snapshot(self):
        with self._lock:
            value = deepcopy(self._last)
            base = {"kind": "external-spot-reference", "sourceURL": self._policy["sourceURL"],
                    "lastAttemptAt": self._attempt, "events": deepcopy(self._events),
                    "executableOrder": False, "conversionPerformed": False}
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

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            def run():
                while not self._stop.is_set():
                    self.refresh()
                    self._stop.wait(self._policy["pollSeconds"])
            self._thread = threading.Thread(target=run, name="commodity-reference-reader", daemon=True)
            self._thread.start()

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
