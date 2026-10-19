"""Public reverse-hop progress, excluding party and native-journal identities."""
import hashlib

from .public_workbench import integer


class HopProjectionRefused(ValueError):
    pass


def project_hop_progress(report):
    result = {"available": False, "sequence": None, "cursor": None,
              "count": None, "hops": [], "consistent": False}
    if not report.get("open"):
        return result
    if not all(key in report for key in ("sequenceId", "assetHops", "hopCursor", "hopResults")):
        return result
    sequence, path, cursor, outcomes = (report[key] for key in
        ("sequenceId", "assetHops", "hopCursor", "hopResults"))
    # Old reports may explicitly carry absent sequence fields. Keep those
    # observations distinguishable from a real zero-hop completion.
    if sequence is None or cursor is None:
        return result
    if (type(sequence) is not str or not 1 <= len(sequence) <= 256
            or type(path) not in (list, tuple) or type(outcomes) not in (list, tuple)
            or integer(cursor) is None or not 0 <= cursor <= len(path)
            or not path or len(path) != len(outcomes)
            or len(path) != len(report.get("affectedLegs", ()))):
        raise HopProjectionRefused("original sequence, cursor and complete hop observations required")
    seen_keys = set()
    expected_legs = tuple(reversed(report["affectedLegs"]))
    if any(integer(leg) is None for leg in expected_legs):
        raise HopProjectionRefused("original transfer occurrences required")
    previous = None
    for index, (hop, outcome) in enumerate(zip(path, outcomes)):
        if type(hop) is not dict or type(outcome) is not dict:
            raise HopProjectionRefused("original hop records required")
        key = hop.get("key")
        source, destination = integer(hop.get("fromPosition")), integer(hop.get("toPosition"))
        detail = outcome.get("detail")
        status = outcome.get("status")
        if (type(key) is not str or not key or key in seen_keys or outcome.get("key") != key
                or hop.get("legIndex") != expected_legs[index]
                or outcome.get("legIndex") != expected_legs[index]
                or source != expected_legs[index] + 1 or destination is None
                or not destination < source or (previous is not None and previous != source)
                or type(detail) is not dict or status not in ("done", "pending", "blocked")
                or (index < cursor) != (status == "done")):
            raise HopProjectionRefused("original reverse-hop occurrence or confirmed cursor differs")
        reference = detail.get("reference")
        has_result = type(reference) is str and bool(reference)
        if status == "done" and not has_result:
            raise HopProjectionRefused("completed hop lacks its original result reference")
        observed = detail.get("returnStatus")
        display = observed if status == "blocked" and observed in ("unknown", "failed") else status
        result["hops"].append({"legIndex": expected_legs[index],
            "fromPosition": source, "toPosition": destination,
            "status": display, "hasResultReference": has_result})
        seen_keys.add(key)
        previous = destination
    if previous != report.get("lastFinalizedPosition"):
        raise HopProjectionRefused("reverse path ends at another protected boundary")
    result.update(available=True,
        sequence=hashlib.sha256(sequence.encode("utf-8")).hexdigest(),
        cursor=cursor, count=len(path),
        consistent=(not report.get("complete") or cursor == len(path)))
    return result
