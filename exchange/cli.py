"""A diagnostic command line. It supplements the UI and never replaces it.

Printing a state here is development and test output. It is not UI acceptance
evidence, and this module says so rather than implying otherwise.
"""
import argparse
import json

from . import fixtures as F
from .ids import canonical_json


def scenario(registration_path="REG_DIRECT"):
    """The Stage 1 demonstration state: A->B->C->D, AB registered, CD deferred."""
    exchange, clock = F.chain_to_d(registration_path=registration_path)
    requests = F.submit_all(exchange)
    outcomes = [F.confirm(exchange, requests[0], "res-ab")[1],
                F.confirm(exchange, requests[2], "res-cd")[1]]
    return exchange, clock, requests, outcomes


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect the local Stage 1 domain state.")
    parser.add_argument("command", choices=("view", "timeline", "queue"))
    parser.add_argument("--registration-path", default="REG_DIRECT")
    parser.add_argument("--canonical", action="store_true",
                        help="print the canonical encoding used for digests")
    arguments = parser.parse_args(argv)
    exchange, _, _, _ = scenario(arguments.registration_path)
    receipt_id = "rcpt-8415-0001"
    payload = {
        "view": lambda: exchange.receipt_view(receipt_id),
        "timeline": lambda: list(exchange.receipt_timeline(receipt_id)),
        "queue": lambda: {"deferredLegs": list(exchange.deferred_legs(receipt_id)),
                          "overdue": list(exchange.overdue_requests(receipt_id))},
    }[arguments.command]()
    print(canonical_json(payload) if arguments.canonical else json.dumps(payload, indent=1, default=list))
    print("# development and diagnostic output; not UI acceptance evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
