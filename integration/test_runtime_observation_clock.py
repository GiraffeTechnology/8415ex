"""Approved Linux definitions; a shared clock is not an atomic checkpoint."""
import unittest

from exchange.cli import scenario
from exchange.workbench import RuntimeBinding


class DeadlineDomain:
    def __init__(self, observed=99):
        self.observed = observed
        self.calls = []

    def receipt_view(self, receipt_id):
        return {"receiptId": receipt_id, "observedAt": self.observed}

    def report(self, name, receipt_id, now):
        self.calls.append((name, receipt_id, now))
        # An implicit second read would cross this deadline.
        moment = 101 if now is None else now
        return {"observedAt": moment, "expired": moment >= 100}

    def reconciliation(self, receipt_id, now=None):
        return self.report("funds", receipt_id, now)

    def rollback_report(self, receipt_id, now=None):
        return self.report("rollback", receipt_id, now)

    def exit_report(self, receipt_id, now=None):
        return self.report("exit", receipt_id, now)

    def receipt_timeline(self, receipt_id):
        return ()

    def overdue_requests(self, receipt_id, now=None):
        row = self.report("overdue", receipt_id, now)
        return (row,) if row["expired"] else ()

    def authorization_state(self, authorization_id, now=None):
        return self.report("authorization", authorization_id, now)


class RuntimeObservationClockTests(unittest.TestCase):
    def test_deadline_and_authorization_use_original_receipt_time(self):
        domain = DeadlineDomain()
        value = RuntimeBinding(domain, "receipt", ("grant",)).snapshot()["state"]
        self.assertEqual(value["overdue"], [])
        self.assertFalse(value["authorizations"][0]["expired"])
        for name in ("funds", "rollback", "exit"):
            self.assertEqual(value[name]["observedAt"], 99)
            self.assertFalse(value[name]["expired"])
        self.assertEqual(domain.calls, [
            ("funds", "receipt", 99), ("rollback", "receipt", 99),
            ("exit", "receipt", 99), ("overdue", "receipt", 99),
            ("authorization", "grant", 99)])

    def test_zero_observation_is_preserved_without_fallback_clock(self):
        domain = DeadlineDomain(0)
        RuntimeBinding(domain, "receipt", ("grant",)).snapshot()
        self.assertEqual([row[2] for row in domain.calls], [0] * 5)

    def test_invalid_observation_is_refused_before_other_reads(self):
        for view in ({"receiptId": "foreign", "observedAt": 99},
                     {"receiptId": "receipt", "observedAt": True},
                     {"receiptId": "receipt", "observedAt": -1},
                     {"receiptId": "receipt", "observedAt": 2**64},
                     {"receiptId": "receipt"}):
            with self.subTest(view=view):
                domain = DeadlineDomain()
                domain.receipt_view = lambda receipt_id, view=view: view
                with self.assertRaises(ValueError):
                    RuntimeBinding(domain, "receipt", ("grant",)).snapshot()
                self.assertEqual(domain.calls, [])

    def test_original_domain_reads_the_advancing_clock_once(self):
        domain, clock, _, _ = scenario()
        initial = domain.receipt_view("rcpt-8415-0001")["observedAt"]
        calls = []
        def advancing_clock():
            calls.append(initial + len(calls))
            return calls[-1]
        domain._clock = advancing_clock
        state = RuntimeBinding(domain, "rcpt-8415-0001").snapshot()["state"]
        self.assertEqual(calls, [initial])
        for name in ("receipt", "funds", "rollback", "exit"):
            self.assertEqual(state[name]["observedAt"], initial)
