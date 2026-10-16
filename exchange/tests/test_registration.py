"""T-04, T-05, T-10: serial ordering, idempotency and the three adapters."""
import unittest

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.model import Asset
from exchange.registration import REGISTRATION_PATHS, RegistrationEvidence


class SerialOrdering(unittest.TestCase):
    """T-04: later results wait for the gap; filling it advances in order."""

    def setUp(self):
        self.exchange, self.clock = F.chain_to_d()
        self.requests = F.submit_all(self.exchange)

    def test_a_later_result_does_not_jump_an_open_gap(self):
        _, outcome = F.confirm(self.exchange, self.requests[2], "res-cd")
        self.assertEqual(outcome["disposition"], "deferred")
        self.assertEqual(outcome["holderIndex"], 0)
        self.assertEqual(self.exchange.holder_of("rcpt-8415-0001"), F.A)
        self.assertEqual(self.exchange.deferred_legs("rcpt-8415-0001"), (2,))
        self.assertEqual(self.exchange.leg("rcpt-8415-0001", 2).registration_status, "pending",
                         "a deferred result is not a confirmation")

    def test_two_later_results_both_wait_and_then_drain_in_order(self):
        F.confirm(self.exchange, self.requests[1], "res-bc")
        F.confirm(self.exchange, self.requests[2], "res-cd")
        self.assertEqual(self.exchange.deferred_legs("rcpt-8415-0001"), (1, 2))
        self.assertEqual(self.exchange.holder_index("rcpt-8415-0001"), 0)
        _, outcome = F.confirm(self.exchange, self.requests[0], "res-ab")
        self.assertEqual(outcome["disposition"], "advanced")
        self.assertEqual(self.exchange.holder_index("rcpt-8415-0001"), 3)
        self.assertEqual(self.exchange.holder_of("rcpt-8415-0001"), F.D)
        self.assertEqual(self.exchange.deferred_legs("rcpt-8415-0001"), ())
        statuses = [leg.registration_status for leg in self.exchange.legs("rcpt-8415-0001")]
        self.assertEqual(statuses, ["confirmed", "confirmed", "confirmed"])

    def test_a_deferred_result_is_not_a_rejection(self):
        F.confirm(self.exchange, self.requests[2], "res-cd")
        view = self.exchange.receipt_view("rcpt-8415-0001")
        self.assertEqual(view["deferredLegs"], (2,))
        self.assertEqual(view["rejectedLegs"], ())

    def test_a_confirmed_prefix_leg_cannot_be_re_applied_by_a_new_result(self):
        F.confirm(self.exchange, self.requests[0], "res-ab")
        with self.assertRaises(DomainError) as caught:
            F.confirm(self.exchange, self.requests[0], "res-ab-again")
        self.assertEqual(caught.exception.code, "EX_REGISTRATION_ALREADY_CONFIRMED")

    def test_a_rejection_is_recorded_against_the_single_leg(self):
        _, outcome = F.confirm(self.exchange, self.requests[1], "res-bc-no", outcome="rejected")
        self.assertEqual(outcome["disposition"], "rejected")
        self.assertEqual(self.exchange.leg("rcpt-8415-0001", 1).registration_status, "rejected")
        self.assertEqual(self.exchange.receipt_view("rcpt-8415-0001")["rejectedLegs"], (1,))
        self.assertEqual(self.exchange.leg("rcpt-8415-0001", 0).registration_status, "pending",
                         "one refused hop does not clear the rest of the chain")

    def test_an_overdue_window_is_reported_without_advice(self):
        self.clock.now = self.requests[0].commitment_deadline_at + 1
        overdue = self.exchange.overdue_requests("rcpt-8415-0001")
        self.assertEqual([entry["legIndex"] for entry in overdue], [0, 1, 2])
        self.assertEqual(overdue[0]["meaning"], "commitment-window-passed")
        self.assertEqual(self.exchange.holder_index("rcpt-8415-0001"), 0,
                         "a passed window advances nothing by itself")


class Idempotency(unittest.TestCase):
    """T-05: an exact repeat is a no-op; the same id with other content conflicts."""

    def setUp(self):
        self.exchange, _ = F.chain_to_d()
        self.requests = F.submit_all(self.exchange)

    def test_an_exact_repeat_returns_the_first_result(self):
        evidence, first = F.confirm(self.exchange, self.requests[0], "res-ab")
        again = self.exchange.apply_registration_result(evidence)
        self.assertEqual(first["disposition"], "advanced")
        self.assertEqual(again["disposition"], "idempotent")
        self.assertEqual(self.exchange.holder_index("rcpt-8415-0001"), 1,
                         "a repeated result must not advance the prefix twice")

    def test_the_same_result_id_with_different_content_is_a_conflict(self):
        F.confirm(self.exchange, self.requests[0], "res-ab")
        with self.assertRaises(DomainError) as caught:
            F.confirm(self.exchange, self.requests[1], "res-ab", result_version=2)
        self.assertEqual(caught.exception.code, "EX_REGISTRATION_CONFLICT")

    def test_a_resubmitted_request_is_idempotent_at_the_adapter(self):
        request, acknowledgement = self.exchange.submit_registration(
            "rcpt-8415-0001", 0, "req-leg-0", 86_400)
        self.assertTrue(acknowledgement["repeated"])
        self.assertEqual(request.attempt, 2)

    def test_a_different_request_id_for_the_same_leg_is_a_conflict(self):
        with self.assertRaises(DomainError) as caught:
            self.exchange.submit_registration("rcpt-8415-0001", 0, "req-leg-0-other", 86_400)
        self.assertEqual(caught.exception.code, "EX_REGISTRATION_CONFLICT")


class EvidenceBinding(unittest.TestCase):
    """T-04/T-10 negative side: a mismatched result advances nothing."""

    def setUp(self):
        self.exchange, _ = F.chain_to_d()
        self.requests = F.submit_all(self.exchange)

    def _evidence(self, **changes):
        base = dict(result_id="res-x", request_id=self.requests[0].request_id,
                    receipt_id="rcpt-8415-0001", transfer_id=self.requests[0].transfer_id,
                    leg_index=0, adapter="REG_DIRECT", source="sim-direct-desk",
                    outcome="confirmed", asset=F.asset(), observed_at=1_700_000_100)
        base.update(changes)
        return RegistrationEvidence(**base)

    def test_a_wrong_network_is_refused(self):
        with self.assertRaises(DomainError) as caught:
            self.exchange.apply_registration_result(
                self._evidence(asset=Asset(1, F.CONTRACT, F.TOKEN_ID)))
        self.assertEqual(caught.exception.code, "EX_REGISTRATION_BINDING_REFUSED")

    def test_a_wrong_token_is_refused(self):
        with self.assertRaises(DomainError) as caught:
            self.exchange.apply_registration_result(
                self._evidence(asset=Asset(F.CHAIN_ID, F.CONTRACT, 4242)))
        self.assertEqual(caught.exception.code, "EX_REGISTRATION_BINDING_REFUSED")

    def test_an_untrusted_source_is_refused(self):
        with self.assertRaises(DomainError) as caught:
            self.exchange.apply_registration_result(self._evidence(source="someone-else"))
        self.assertEqual(caught.exception.code, "EX_REGISTRATION_SOURCE_REFUSED")

    def test_a_result_naming_another_leg_than_its_request_is_refused(self):
        with self.assertRaises(DomainError) as caught:
            self.exchange.apply_registration_result(self._evidence(leg_index=2))
        self.assertEqual(caught.exception.code, "EX_REGISTRATION_BINDING_REFUSED")

    def test_a_result_naming_another_transfer_is_refused(self):
        with self.assertRaises(DomainError) as caught:
            self.exchange.apply_registration_result(self._evidence(transfer_id="transfer-cd"))
        self.assertEqual(caught.exception.code, "EX_REGISTRATION_BINDING_REFUSED")

    def test_a_result_for_an_unknown_request_is_refused(self):
        with self.assertRaises(DomainError) as caught:
            self.exchange.apply_registration_result(self._evidence(request_id="req-never-filed"))
        self.assertEqual(caught.exception.code, "EX_REGISTRATION_UNKNOWN_REQUEST")

    def test_the_adapter_must_match_the_request(self):
        with self.assertRaises(DomainError) as caught:
            self.exchange.apply_registration_result(self._evidence(adapter="REG_ELECTRONIC"))
        self.assertEqual(caught.exception.code, "EX_REGISTRATION_BINDING_REFUSED")

    def test_no_state_moved_after_every_refusal(self):
        self.assertEqual(self.exchange.holder_index("rcpt-8415-0001"), 0)
        self.assertEqual(self.exchange.deferred_legs("rcpt-8415-0001"), ())


class ThreeAdapters(unittest.TestCase):
    """T-10: three paths, one contract, every one of them marked simulated."""

    def test_each_path_carries_the_same_chain_through_the_same_contract(self):
        for path in REGISTRATION_PATHS:
            with self.subTest(path=path):
                exchange, _ = F.chain_to_d(registration_path=path)
                requests = F.submit_all(exchange)
                for index, request in enumerate(requests):
                    self.assertEqual(request.adapter, path)
                    _, outcome = F.confirm(exchange, request, f"res-{path}-{index}")
                    self.assertEqual(outcome["disposition"], "advanced")
                self.assertEqual(exchange.holder_index("rcpt-8415-0001"), 3)
                self.assertEqual(exchange.holder_of("rcpt-8415-0001"), F.D)

    def test_every_path_is_labelled_simulated(self):
        exchange, _ = F.minted()
        for path in REGISTRATION_PATHS:
            registrar = exchange.registrars[path]
            self.assertTrue(registrar.simulated)
            self.assertIn("simulated", registrar.label)
            self.assertEqual(registrar.path, path)

    def test_the_paths_differ_only_in_the_recorded_hand_off(self):
        exchange, _ = F.minted()
        filed_by = set()
        for path in REGISTRATION_PATHS:
            other, _ = F.chain_to_d(registration_path=path)
            _, acknowledgement = other.submit_registration("rcpt-8415-0001", 0, "req-hand", 86_400)
            self.assertTrue(acknowledgement["simulated"])
            filed_by.add(acknowledgement["handover"]["filedBy"])
        self.assertEqual(len(filed_by), 3, "each path records a distinct hand-off")

    def test_success_on_one_path_is_not_success_on_another(self):
        direct, _ = F.chain_to_d(registration_path="REG_DIRECT")
        requests = F.submit_all(direct)
        F.confirm(direct, requests[0], "res-direct-0")
        self.assertEqual(direct.holder_index("rcpt-8415-0001"), 1)
        electronic, _ = F.chain_to_d(registration_path="REG_ELECTRONIC")
        self.assertEqual(electronic.holder_index("rcpt-8415-0001"), 0,
                         "a confirmation on one path leaves the other path untouched")

    def test_a_request_filed_to_the_wrong_adapter_is_refused(self):
        exchange, _ = F.chain_to_d(registration_path="REG_DIRECT")
        request, _ = exchange.submit_registration("rcpt-8415-0001", 0, "req-leg-0", 86_400)
        with self.assertRaises(DomainError) as caught:
            exchange.registrars["REG_ELECTRONIC"].submit(request)
        self.assertEqual(caught.exception.code, "EX_REGISTRATION_PATH_REFUSED")


if __name__ == "__main__":
    unittest.main()
