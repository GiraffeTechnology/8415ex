"""Explicit existing bulk catalogue host entry; never an HTML fallback."""
import argparse
import hashlib
import re

from .eia_bulk_reference_catalogue import compose_eia_bulk_reference_catalogue
from .eia_reference_serve import CONFIG_LIMIT, _load_fixed_eia_reference_config
from .eia_wti_bulk_series import BULK_URL
from .reference_catalogue_runtime import serve_reference_catalogue


def load_eia_bulk_reference_config(raw):
    """Decode only the explicit fixed petroleum bulk host configuration."""
    return _load_fixed_eia_reference_config(raw, BULK_URL)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--empty-catalogue", action="store_true", required=True)
    parser.add_argument("--reference-config", required=True)
    parser.add_argument("--reference-config-sha256", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--collateral-selection", action="store_true")
    parser.add_argument("--scenario-selection", action="store_true")
    args = parser.parse_args(argv)
    if re.fullmatch(r"[0-9a-f]{64}", args.reference_config_sha256) is None:
        parser.error("exact host reference configuration digest required")
    try:
        with open(args.reference_config, "rb") as stream:
            raw = stream.read(CONFIG_LIMIT + 1)
        if hashlib.sha256(raw).hexdigest() != args.reference_config_sha256:
            raise ValueError("host reference configuration identity differs")
        config = load_eia_bulk_reference_config(raw)
    except (OSError, ValueError, UnicodeError, RecursionError):
        parser.error("reference configuration could not be loaded")
    policy = config["policy"]
    server = compose_eia_bulk_reference_catalogue(
        policy=policy,
        # The host-supplied external digest binds this complete configuration;
        # the file does not choose or certify its own expected identity.
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
