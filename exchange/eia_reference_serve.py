"""Host-owned CLI for the original empty catalogue with an EIA reference feed."""
import argparse
from copy import deepcopy
import json
import math

from .eia_reference_catalogue import compose_eia_reference_catalogue
from .eia_wti_spot_table import SCOPE, SOURCE_URL
from .reference_catalogue_runtime import serve_reference_catalogue

CONFIG_LIMIT = 64 * 1024
POLICY_FIELDS = set(SCOPE) | {
    "sourceURL", "sourceTimezone", "pollSeconds",
    "maxSourceAgeSeconds", "maxClockSkewSeconds",
}
READER_FIELDS = {
    "timeout_seconds", "user_agent", "minimum_fetch_seconds",
    "failure_backoff_seconds",
}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate reference configuration field")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonfinite reference configuration constant")


def load_eia_reference_config(raw):
    """Decode only non-secret source/transport configuration, without startup."""
    if type(raw) is not bytes or not 0 < len(raw) <= CONFIG_LIMIT:
        raise ValueError("bounded reference configuration bytes required")
    config = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                        parse_constant=_reject_constant)
    if (type(config) is not dict or set(config) != {"version", "policy", "reader"}
            or type(config["version"]) is not int or config["version"] != 1):
        raise ValueError("reference configuration version differs")
    policy, reader = config["policy"], config["reader"]
    if (type(policy) is not dict or set(policy) != POLICY_FIELDS
            or policy.get("sourceURL") != SOURCE_URL
            or any(policy.get(key) != value for key, value in SCOPE.items())):
        raise ValueError("fixed daily EIA source configuration required")
    if type(reader) is not dict or set(reader) != READER_FIELDS:
        raise ValueError("explicit non-secret reader settings required")
    if type(policy["sourceTimezone"]) is not str or not policy["sourceTimezone"].strip():
        raise ValueError("explicit source calendar required")
    for key in ("pollSeconds", "maxSourceAgeSeconds", "maxClockSkewSeconds"):
        if type(policy[key]) is not int or policy[key] < (1 if key == "pollSeconds" else 0):
            raise ValueError("explicit reference cadence and freshness required")
    minimum = reader["minimum_fetch_seconds"]
    if (type(minimum) not in (int, float) or not math.isfinite(minimum)
            or minimum <= 0 or policy["pollSeconds"] < minimum):
        raise ValueError("reference polling must cover reader fetch spacing")
    # Transport values and the actual IANA calendar are validated by the
    # existing reader/feed during composition, before the HTTP socket binds.
    return deepcopy(config)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--empty-catalogue", action="store_true", required=True)
    parser.add_argument("--reference-config", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--collateral-selection", action="store_true")
    parser.add_argument("--scenario-selection", action="store_true")
    args = parser.parse_args(argv)
    try:
        with open(args.reference_config, "rb") as stream:
            config = load_eia_reference_config(stream.read(CONFIG_LIMIT + 1))
    except (OSError, ValueError, UnicodeError, RecursionError):
        parser.error("reference configuration could not be loaded")
    policy = config["policy"]
    server = compose_eia_reference_catalogue(
        policy=policy,
        # The operator-owned file defines this host configuration snapshot.
        # Equality is consistency only, not independent provider approval,
        # calendar/SLA attestation or a claim of third-party display rights.
        verify_policy=lambda candidate: candidate == policy,
        reader_options=config["reader"],
        port=args.port, commit=args.commit, tree=args.tree,
        collateral_selection=args.collateral_selection,
        scenario_selection=args.scenario_selection)
    serve_reference_catalogue(server)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
