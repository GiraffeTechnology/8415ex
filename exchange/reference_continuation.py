"""Original EIA observation continuation for an authorized process replacement.

This accepts an explicit digest-bound private input, not a new provider or a
fresh HTTP observation. It does not create credentials or financial authority.
"""
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math

from .eia_wti_spot_reader import EIAWTISpotReader
from .eia_wti_spot_table import parse_eia_wti_spot_table, SOURCE_URL, SCOPE
from .reference_feed import CommodityReferenceFeed, _instant, _transport_observation

LIMIT = 2 * 1024 * 1024


def _pairs(pairs):
    row = {}
    for key, value in pairs:
        if key in row:
            raise ValueError("duplicate continuation field")
        row[key] = value
    return row


def resume_eia_reference(feed, reader, policy, raw, expected_sha256, *, now=None):
    if (type(feed) is not CommodityReferenceFeed or type(reader) is not EIAWTISpotReader
            or type(raw) is not bytes or len(raw) > LIMIT
            or type(expected_sha256) is not str
            or hashlib.sha256(raw).hexdigest() != expected_sha256):
        raise ValueError("original continuation identity differs")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    if (type(data) is not dict or set(data) != {"schema", "capturedAt", "sourceResponseBase64", "observation"}
            or data["schema"] != "8415ex-eia-reference-continuation/1"):
        raise ValueError("original continuation schema differs")
    clock = now or datetime.now(timezone.utc)
    captured = _instant(data["capturedAt"])
    observation = data["observation"]
    if type(observation) is not dict:
        raise ValueError("original observation required")
    if type(data["sourceResponseBase64"]) is not str:
        raise ValueError("original source encoding required")
    source = base64.b64decode(data["sourceResponseBase64"], validate=True)
    parsed = parse_eia_wti_spot_table(source)
    fetched = _instant(observation["fetchedAt"])
    attempt = _instant(observation["lastAttemptAt"])
    skew = timedelta(seconds=policy["maxClockSkewSeconds"])
    failed = (observation.get("status") == "unavailable"
              and observation.get("retainedValue") is True)
    chronology = fetched <= attempt <= captured if failed else attempt <= fetched <= captured
    if not chronology or captured > clock.astimezone(timezone.utc) + skew:
        raise ValueError("original observation chronology differs")
    if (observation.get("sourceURL") != SOURCE_URL or policy.get("sourceURL") != SOURCE_URL
            or any(observation.get(k) != v or policy.get(k) != v for k, v in SCOPE.items())
            or observation.get("kind") != "external-spot-reference"
            or (not failed and (observation.get("status") not in ("fresh", "stale", "unknown")
                                or observation.get("retainedValue") is not False))
            or observation.get("lastSuccessful") != observation["fetchedAt"]
            or observation.get("executableOrder") is not False
            or observation.get("conversionPerformed") is not False):
        raise ValueError("original successful source observation required")
    for key in ("price", "sourceAsOf", "sourcePrecision"):
        if observation.get(key) != parsed[key]:
            raise ValueError("cached response differs from observation")
    evidence = observation.get("sourceEvidence")
    expected_evidence = {key: parsed[key] for key in ("rawResponseSHA256", "publicationDate")}
    if evidence != expected_evidence:
        raise ValueError("original source evidence differs")
    metadata = observation.get("transportObservation")
    transport = metadata.get("value") if type(metadata) is dict else None
    clean = _transport_observation(transport)
    if clean != transport or type(clean) is not dict:
        raise ValueError("original bounded transport required")
    if failed:
        if clean.get("status") != "unavailable" or clean.get("retainedSource") is not True:
            raise ValueError("original retained failure transport required")
    elif (clean.get("status") not in ("read", "not-modified")
            or clean.get("rawResponseSHA256") != parsed["rawResponseSHA256"]
            or (clean["status"] == "read" and clean.get("bytes") != len(source))):
        raise ValueError("original successful transport required")
    events = observation.get("events")
    if type(events) is not list or not 1 <= len(events) <= 20:
        raise ValueError("original bounded events required")
    previous = None
    for event in events:
        if (type(event) is not dict or set(event) != {"attemptedAt", "result"}
                or event["result"] not in ("read", "unavailable")):
            raise ValueError("original event schema differs")
        at = _instant(event["attemptedAt"])
        if ((previous is not None and at < previous) or at > (attempt if failed else fetched)
                or (event["result"] == "read" and at > fetched)):
            raise ValueError("original event chronology differs")
        previous = at
    if events[-1] != {"attemptedAt": observation["lastAttemptAt"],
                      "result": "unavailable" if failed else "read"}:
        raise ValueError("last successful event differs")
    # The previous reader finished before the feed's normal post-read sleep.
    # Use completion time, preserving at least both original intervals.
    minimum = reader._minimum
    poll = policy["pollSeconds"]
    if (type(poll) is not int or poll <= 0 or not math.isfinite(minimum)):
        raise ValueError("original finite cadence required")
    if failed:
        # Failure completion is not exposed in the observation. Capture is a
        # verified upper bound; wait a full original interval from that bound.
        # Never reset a failed source to its older successful deadline.
        failure = reader._failure
        if type(failure) not in (int, float) or not math.isfinite(failure) or failure <= 0:
            raise ValueError("original finite failure backoff required")
        deadline = captured + timedelta(seconds=max(poll, minimum, failure))
    else:
        deadline = fetched + timedelta(seconds=max(poll, minimum))
    last = {key: observation[key] for key in SCOPE}
    last.update({key: observation[key] for key in ("price", "sourceAsOf", "sourcePrecision", "fetchedAt")})
    last["sourceEvidence"] = deepcopy(evidence)
    validated = {"last": last, "attempt": observation["lastAttemptAt"],
                 "events": deepcopy(events), "transport": deepcopy(clean), "failed": failed}
    reader.resume_validated_response(source, not_before=deadline.timestamp())
    feed.resume_validated_observation(validated, not_before=deadline,
                                     verify=lambda value: value == validated)
    return {"resumed": True, "originalFetchedAt": observation["fetchedAt"],
            "firstRefreshNotBefore": deadline.isoformat().replace("+00:00", "Z")}
