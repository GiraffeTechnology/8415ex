"""T-27: the same fixtures and fixed clock produce the same result, and the
timeline carries each record's asset, transfer, request and run identity."""
import unittest

from exchange import fixtures as F
from exchange.ids import digest


def scenario():
    """One fully deterministic run: chain to D, file every leg, confirm out of
    order, then fill the gap."""
    clock = F.ManualClock()
    exchange, _ = F.chain_to_d(clock=clock)
    requests = F.submit_all(exchange)
    F.confirm(exchange, requests[2], "res-cd")
    F.confirm(exchange, requests[0], "res-ab")
    F.confirm(exchange, requests[1], "res-bc")
    return exchange


class Determinism(unittest.TestCase):

    def test_two_runs_of_the_same_fixture_are_byte_identical(self):
        first, second = scenario(), scenario()
        self.assertEqual(digest(first.receipt_view("rcpt-8415-0001")),
                         digest(second.receipt_view("rcpt-8415-0001")))
        self.assertEqual(digest(list(first.receipt_timeline("rcpt-8415-0001"))),
                         digest(list(second.receipt_timeline("rcpt-8415-0001"))))

    def test_the_scenario_reaches_the_expected_end_state(self):
        exchange = scenario()
        view = exchange.receipt_view("rcpt-8415-0001")
        self.assertEqual(view["owner"]["account"], F.D)
        self.assertEqual(view["holder"]["account"], F.D)
        self.assertTrue(view["ownerEqualsHolder"])
        self.assertEqual(view["registeredPrefixLegs"], 3)
        self.assertEqual(view["outstandingLegs"], 0)
        self.assertEqual(view["deferredLegs"], ())

    def test_amounts_are_integers_in_the_smallest_unit(self):
        exchange = scenario()
        for leg in exchange.legs("rcpt-8415-0001"):
            self.assertIsInstance(leg.price, int)
        view = exchange.receipt_view("rcpt-8415-0001")
        for leg in view["legs"]:
            self.assertIsInstance(leg["price"], str, "amounts are reported as exact decimal strings")
            self.assertTrue(leg["price"].isdigit())

    def test_no_float_can_enter_a_canonical_record(self):
        from exchange.errors import DomainError
        from exchange.ids import canonical_json
        with self.assertRaises(DomainError) as caught:
            canonical_json({"price": 1.5})
        self.assertEqual(caught.exception.code, "EX_CANONICAL_REFUSED")


class Traceability(unittest.TestCase):
    """EX-NFR-05: every record ties back to asset, transfer, request and leg."""

    def test_the_timeline_is_ordered_and_covers_every_phase(self):
        exchange = scenario()
        timeline = exchange.receipt_timeline("rcpt-8415-0001")
        self.assertEqual([entry["sequence"] for entry in timeline], list(range(len(timeline))))
        kinds = [entry["kind"] for entry in timeline]
        self.assertEqual(kinds.count("receipt-minted"), 1)
        self.assertEqual(kinds.count("transfer-executed"), 3)
        self.assertEqual(kinds.count("registration-submitted"), 3)
        self.assertEqual(kinds.count("registration-result"), 3)
        self.assertEqual(kinds.count("registration-result-drained"), 1,
                         "the deferred leg is drained once the gap is filled")

    def test_every_record_names_the_receipt(self):
        exchange = scenario()
        for entry in exchange.receipt_timeline("rcpt-8415-0001"):
            self.assertEqual(entry["receiptId"], "rcpt-8415-0001")

    def test_transfer_records_name_the_leg_and_both_positions(self):
        exchange = scenario()
        executed = [e for e in exchange.receipt_timeline("rcpt-8415-0001")
                    if e["kind"] == "transfer-executed"]
        for index, entry in enumerate(executed):
            self.assertEqual(entry["detail"]["legIndex"], index)
            self.assertIn("ownerIndex", entry["detail"])
            self.assertIn("holderIndex", entry["detail"])
            self.assertIn("matchBasis", entry["detail"])

    def test_registration_records_name_the_request_source_and_disposition(self):
        exchange = scenario()
        results = [e for e in exchange.receipt_timeline("rcpt-8415-0001")
                   if e["kind"] == "registration-result"]
        dispositions = [entry["detail"]["disposition"] for entry in results]
        self.assertEqual(dispositions, ["deferred", "advanced", "advanced"])
        for entry in results:
            self.assertIn("requestId", entry["detail"])
            self.assertIn("source", entry["detail"])
            self.assertTrue(entry["detail"]["simulated"])


if __name__ == "__main__":
    unittest.main()
