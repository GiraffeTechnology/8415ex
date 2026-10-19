"""T-11 to T-16, T-28, T-31: segmented funding and independent settlement."""
import unittest

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.model import Asset


class SegmentFunding(unittest.TestCase):
    """T-11: each leg's own buyer funds it, and a failed lock forms no trade."""

    def test_each_leg_has_its_own_position_with_its_own_terms(self):
        exchange, _ = F.funded_chain_to_d()
        expected = ((F.B, F.A, F.PRICE_AB), (F.C, F.B, F.PRICE_BC), (F.D, F.C, F.PRICE_CD))
        for leg_index, (payer, payee, principal) in enumerate(expected):
            escrow = exchange.escrow_for_leg("rcpt-8415-0001", leg_index)
            self.assertEqual((escrow.payer, escrow.payee, escrow.principal),
                             (payer, payee, principal))
            self.assertEqual(escrow.status, "locked")
            self.assertEqual(exchange.leg("rcpt-8415-0001", leg_index).funding_status, "locked")

    def test_without_a_locked_escrow_no_trade_and_no_request_is_formed(self):
        exchange, _ = F.funded_exchange()
        match, leg = F.funded_hop(exchange, F.A, F.B, 1, "transfer-ab",
                                  "session-a", "session-b", lock=False)
        self.assertIsNone(leg)
        with self.assertRaises(DomainError) as caught:
            exchange.execute_transfer(match, "transfer-ab")
        self.assertEqual(caught.exception.code, "EX_SEGMENT_NOT_FUNDED")
        self.assertEqual(exchange.owner_index("rcpt-8415-0001"), 0)
        with self.assertRaises(DomainError):
            exchange.submit_registration("rcpt-8415-0001", 0, "req-leg-0", 86_400)

    def test_an_escrow_on_the_wrong_terms_forms_no_trade(self):
        exchange, _ = F.funded_exchange()
        match, _ = F.funded_hop(exchange, F.A, F.B, 1, "transfer-ab",
                                "session-a", "session-b", lock=False)
        escrow = exchange.lock_escrow(match, "escrow-ab")
        # the position is for the agreed terms; a different principal is refused
        exchange._escrows["escrow-ab"] = escrow.__class__(
            escrow_id="escrow-ab", receipt_id=escrow.receipt_id, leg_index=0,
            payer=escrow.payer, payee=escrow.payee, quote_asset=escrow.quote_asset,
            principal=escrow.principal - 1, locked_at=escrow.locked_at)
        with self.assertRaises(DomainError) as caught:
            exchange.execute_transfer(match, "transfer-ab", escrow_id="escrow-ab")
        self.assertEqual(caught.exception.code, "EX_SEGMENT_FUNDING_MISMATCH")
        self.assertEqual(exchange.owner_index("rcpt-8415-0001"), 0)

    def test_one_leg_cannot_be_funded_twice(self):
        exchange, _ = F.funded_exchange()
        match, _ = F.funded_hop(exchange, F.A, F.B, 1, "transfer-ab",
                                "session-a", "session-b", lock=False)
        exchange.lock_escrow(match, "escrow-ab")
        with self.assertRaises(DomainError) as caught:
            exchange.lock_escrow(match, "escrow-ab-again")
        self.assertEqual(caught.exception.code, "EX_ESCROW_DUPLICATE_REFUSED")

    def test_funded_mode_requires_a_payment_adapter(self):
        from exchange.ledger import Exchange
        with self.assertRaises(DomainError) as caught:
            Exchange(F.ManualClock(), funding_required=True)
        self.assertEqual(caught.exception.code, "EX_PAYMENT_ADAPTER_REQUIRED")


class IndependentRelease(unittest.TestCase):
    """T-12: AB releases on its own position, without waiting for C or D."""

    def setUp(self):
        self.exchange, self.clock = F.funded_chain_to_d()
        self.requests = F.submit_all(self.exchange)

    def test_ab_releases_while_bc_and_cd_are_still_pending(self):
        F.confirm(self.exchange, self.requests[0], "res-ab")
        outcome = self.exchange.release_segment("rcpt-8415-0001", 0,
                                                F.release_authority(self.exchange, 0, "auth-0"))
        self.assertTrue(outcome["released"])
        self.assertEqual(outcome["payee"], F.A)
        self.assertEqual(outcome["principal"], F.PRICE_AB)
        self.assertEqual(self.exchange.escrow_for_leg("rcpt-8415-0001", 1).status, "locked")
        self.assertEqual(self.exchange.escrow_for_leg("rcpt-8415-0001", 2).status, "locked")

    def test_a_released_segment_loses_its_rollback_capability(self):
        F.confirm(self.exchange, self.requests[0], "res-ab")
        self.exchange.release_segment("rcpt-8415-0001", 0,
                                      F.release_authority(self.exchange, 0, "auth-0"))
        self.assertEqual(self.exchange.leg("rcpt-8415-0001", 0).rollback_status, "detached")
        self.assertEqual(self.exchange.leg("rcpt-8415-0001", 1).rollback_status, "available")

    def test_a_segment_whose_holder_position_is_not_reached_is_not_releasable(self):
        state = self.exchange.segment_release_state("rcpt-8415-0001", 0)
        self.assertFalse(state["eligible"])
        self.assertIn("EX_HOLDER_POSITION_NOT_REACHED", state["reasons"])
        with self.assertRaises(DomainError) as caught:
            self.exchange.release_segment("rcpt-8415-0001", 0,
                                          F.release_authority(self.exchange, 0, "auth-0"))
        self.assertEqual(caught.exception.code, "EX_SEGMENT_NOT_RELEASABLE")

    def test_registration_advancing_releases_the_segments_in_prefix_order(self):
        for index, result in enumerate(("res-ab", "res-bc", "res-cd")):
            F.confirm(self.exchange, self.requests[index], result)
            authorities = {leg: F.release_authority(self.exchange, leg, f"auth-{leg}")
                           for leg in range(index + 1)}
            outcomes = self.exchange.settle_eligible_segments("rcpt-8415-0001", authorities)
            released = [o["legIndex"] for o in outcomes if o.get("released")]
            self.assertEqual(released, [index], "each hop releases exactly once, when it qualifies")
        statuses = [self.exchange.escrow_for_leg("rcpt-8415-0001", i).status for i in range(3)]
        self.assertEqual(statuses, ["released", "released", "released"])
        self.assertEqual(self.exchange.payments.movements, 3)

    def test_a_segment_with_no_authority_is_reported_not_released(self):
        F.confirm(self.exchange, self.requests[0], "res-ab")
        outcomes = self.exchange.settle_eligible_segments("rcpt-8415-0001", {})
        self.assertFalse(outcomes[0].get("released"))
        self.assertIn("EX_RELEASE_AUTHORITY_MISSING", outcomes[0]["reasons"])
        self.assertEqual(self.exchange.payments.movements, 0)

    def test_a_segment_cannot_be_released_twice(self):
        F.confirm(self.exchange, self.requests[0], "res-ab")
        self.exchange.release_segment("rcpt-8415-0001", 0,
                                      F.release_authority(self.exchange, 0, "auth-0"))
        with self.assertRaises(DomainError) as caught:
            self.exchange.release_segment("rcpt-8415-0001", 0,
                                          F.release_authority(self.exchange, 0, "auth-0-again"))
        self.assertEqual(caught.exception.code, "EX_SEGMENT_NOT_RELEASABLE")
        self.assertIn("EX_SEGMENT_ALREADY_RELEASED", str(caught.exception))
        self.assertEqual(self.exchange.payments.movements, 1)


class NoCrossSubsidy(unittest.TestCase):
    """T-13: segment prices never merge, and a later leg never funds an earlier."""

    def setUp(self):
        self.exchange, _ = F.funded_chain_to_d()
        self.requests = F.submit_all(self.exchange)

    def test_the_three_principals_stay_distinct(self):
        principals = [self.exchange.escrow_for_leg("rcpt-8415-0001", i).principal for i in range(3)]
        self.assertEqual(principals, [F.PRICE_AB, F.PRICE_BC, F.PRICE_CD])
        self.assertEqual(len(set(principals)), 3)

    def test_a_release_pays_exactly_its_own_position_to_its_own_payee(self):
        F.confirm(self.exchange, self.requests[0], "res-ab")
        outcome = self.exchange.release_segment("rcpt-8415-0001", 0,
                                                F.release_authority(self.exchange, 0, "auth-0"))
        record = self.exchange.payments.lookup(outcome["paymentKey"])
        self.assertEqual(record["principal"], F.PRICE_AB)
        self.assertEqual(record["payee"], F.A)
        self.assertEqual(record["payer"], F.B)

    def test_a_later_segments_authority_cannot_release_an_earlier_one(self):
        F.confirm(self.exchange, self.requests[0], "res-ab")
        wrong = F.release_authority(self.exchange, 1, "auth-1")
        with self.assertRaises(DomainError) as caught:
            self.exchange.release_segment("rcpt-8415-0001", 0, wrong)
        self.assertEqual(caught.exception.code, "EX_RELEASE_BINDING_REFUSED")
        self.assertEqual(self.exchange.payments.movements, 0)

    def test_an_unfunded_later_leg_cannot_borrow_an_earlier_position(self):
        """Each position is keyed to its own leg, so there is nothing to borrow."""
        escrow_ids = {self.exchange.escrow_for_leg("rcpt-8415-0001", i).escrow_id for i in range(3)}
        self.assertEqual(len(escrow_ids), 3)
        for index in range(3):
            self.assertEqual(self.exchange.escrow_for_leg("rcpt-8415-0001", index).leg_index, index)


class ReleaseAuthorityBinding(unittest.TestCase):
    """T-14: wrong asset, segment, journal, network or source is refused."""

    def setUp(self):
        self.exchange, _ = F.funded_chain_to_d()
        self.requests = F.submit_all(self.exchange)
        F.confirm(self.exchange, self.requests[0], "res-ab")

    def _refused(self, code, **overrides):
        authority = F.release_authority(self.exchange, 0, "auth-bad", **overrides)
        with self.assertRaises(DomainError) as caught:
            self.exchange.release_segment("rcpt-8415-0001", 0, authority)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.exchange.payments.movements, 0)
        self.assertEqual(self.exchange.escrow_for_leg("rcpt-8415-0001", 0).status, "locked")

    def test_an_unverified_source_is_refused(self):
        self._refused("EX_RELEASE_SOURCE_REFUSED", source="someone-elses-authority")

    def test_a_wrong_network_is_refused(self):
        self._refused("EX_RELEASE_BINDING_REFUSED",
                      asset=Asset(1, F.CONTRACT, F.TOKEN_ID))

    def test_a_wrong_token_is_refused(self):
        self._refused("EX_RELEASE_BINDING_REFUSED",
                      asset=Asset(F.CHAIN_ID, F.CONTRACT, 4242))

    def test_a_wrong_segment_is_refused(self):
        from dataclasses import replace
        claims_another_leg = replace(F.release_authority(self.exchange, 0, "auth-bad"), leg_index=1)
        with self.assertRaises(DomainError) as caught:
            self.exchange.release_segment("rcpt-8415-0001", 0, claims_another_leg)
        self.assertEqual(caught.exception.code, "EX_RELEASE_BINDING_REFUSED")
        self.assertEqual(self.exchange.payments.movements, 0)
        self.assertEqual(self.exchange.escrow_for_leg("rcpt-8415-0001", 0).status, "locked")

    def test_a_wrong_transfer_is_refused(self):
        self._refused("EX_RELEASE_BINDING_REFUSED", transfer_id="transfer-cd")

    def test_a_tampered_binding_is_refused(self):
        self._refused("EX_RELEASE_BINDING_REFUSED", binding="0x" + "11" * 32)

    def test_a_plain_signature_or_bare_settlement_id_is_not_authority(self):
        from exchange.settlement import NOT_AUTHORITY
        for substitute in ("0xdeadbeef", "VALID", {"settlementId": "s-1"}, "s-1", None):
            with self.subTest(substitute=substitute):
                with self.assertRaises(DomainError) as caught:
                    self.exchange.release_segment("rcpt-8415-0001", 0, substitute)
                self.assertEqual(caught.exception.code, "EX_RELEASE_AUTHORITY_REFUSED")
        self.assertEqual(len(NOT_AUTHORITY), 4)
        self.assertEqual(self.exchange.payments.movements, 0)

    def test_an_authority_missing_its_journal_reference_cannot_be_built(self):
        with self.assertRaises(DomainError) as caught:
            F.release_authority(self.exchange, 0, "auth-nojournal", journal_reference="")
        self.assertEqual(caught.exception.code, "EX_RELEASE_AUTHORITY_REFUSED")


class HistoricalAndCurrentEvidence(unittest.TestCase):
    """T-15: an earlier leg's confirmation and a later holder observation both
    hold at once, and each segment settles on its own evidence."""

    def test_a_past_confirmation_is_not_erased_by_a_later_one(self):
        exchange, _ = F.funded_chain_to_d()
        requests = F.submit_all(exchange)
        for index, result in enumerate(("res-ab", "res-bc")):
            F.confirm(exchange, requests[index], result)
        self.assertEqual(exchange.holder_index("rcpt-8415-0001"), 2)
        # leg 0's own confirmation still stands while the holder sits at C
        self.assertEqual(exchange.leg("rcpt-8415-0001", 0).registration_status, "confirmed")
        results = [entry for entry in exchange.receipt_timeline("rcpt-8415-0001")
                   if entry["kind"] == "registration-result"]
        self.assertEqual([entry["detail"]["legIndex"] for entry in results], [0, 1])
        authorities = {leg: F.release_authority(exchange, leg, f"auth-{leg}") for leg in (0, 1)}
        outcomes = exchange.settle_eligible_segments("rcpt-8415-0001", authorities)
        self.assertEqual([o["legIndex"] for o in outcomes if o.get("released")], [0, 1])
        self.assertEqual(outcomes[0]["principal"], F.PRICE_AB)
        self.assertEqual(outcomes[1]["principal"], F.PRICE_BC)

    def test_each_segment_release_carries_its_own_journal_reference(self):
        exchange, _ = F.funded_chain_to_d()
        requests = F.submit_all(exchange)
        F.confirm(exchange, requests[0], "res-ab")
        F.confirm(exchange, requests[1], "res-bc")
        for leg in (0, 1):
            exchange.release_segment("rcpt-8415-0001", leg,
                                     F.release_authority(exchange, leg, f"auth-{leg}"))
        attempts = [entry["detail"] for entry in exchange.receipt_timeline("rcpt-8415-0001")
                    if entry["kind"] == "segment-release-attempt"]
        references = [entry["journalReference"] for entry in attempts]
        self.assertEqual(len(set(references)), 2, "each segment has its own journal reference")


class PaymentFailureAndRecovery(unittest.TestCase):
    """T-16, T-28: a late or unknown payment is tracked, never double-sent, and
    never silently reported as paid."""

    def _exchange(self, outcomes):
        exchange, clock = F.funded_chain_to_d(outcomes=outcomes)
        requests = F.submit_all(exchange)
        F.confirm(exchange, requests[0], "res-ab")
        return exchange, requests

    def test_a_failed_payment_leaves_the_segment_locked_and_says_so(self):
        exchange, _ = self._exchange({"release:escrow-ab": "failed"})
        outcome = exchange.release_segment("rcpt-8415-0001", 0,
                                           F.release_authority(exchange, 0, "auth-0"))
        self.assertFalse(outcome["released"])
        self.assertEqual(outcome["paymentStatus"], "failed")
        self.assertEqual(exchange.escrow_for_leg("rcpt-8415-0001", 0).status, "locked")
        self.assertEqual(exchange.leg("rcpt-8415-0001", 0).funding_status, "release-failed")
        self.assertEqual(exchange.payments.movements, 0)

    def test_a_confirmed_segment_with_a_failed_payment_is_not_swept_into_refund(self):
        exchange, _ = self._exchange({"release:escrow-ab": "failed"})
        exchange.release_segment("rcpt-8415-0001", 0, F.release_authority(exchange, 0, "auth-0"))
        leg = exchange.leg("rcpt-8415-0001", 0)
        self.assertEqual(leg.registration_status, "confirmed")
        self.assertNotEqual(leg.funding_status, "refunded")
        self.assertEqual(exchange.escrow_for_leg("rcpt-8415-0001", 0).refunded_at, None)

    def test_a_failed_payment_can_be_retried_under_the_same_key(self):
        exchange, _ = self._exchange({"release:escrow-ab": "failed"})
        exchange.release_segment("rcpt-8415-0001", 0, F.release_authority(exchange, 0, "auth-0"))
        again = exchange.release_segment("rcpt-8415-0001", 0,
                                         F.release_authority(exchange, 0, "auth-0-retry"))
        self.assertTrue(again["released"])
        self.assertEqual(again["paymentKey"], "release:escrow-ab")
        self.assertEqual(exchange.payments.movements, 1, "exactly one movement in total")

    def test_an_unknown_outcome_is_not_read_as_failed(self):
        exchange, _ = self._exchange({"release:escrow-ab": "unknown"})
        outcome = exchange.release_segment("rcpt-8415-0001", 0,
                                           F.release_authority(exchange, 0, "auth-0"))
        self.assertEqual(outcome["paymentStatus"], "unknown")
        self.assertFalse(outcome["released"])
        self.assertEqual(exchange.leg("rcpt-8415-0001", 0).funding_status,
                         "release-outcome-unknown")

    def test_an_unknown_outcome_is_never_repaired_by_a_second_payment(self):
        exchange, _ = self._exchange({"release:escrow-ab": "unknown"})
        exchange.release_segment("rcpt-8415-0001", 0, F.release_authority(exchange, 0, "auth-0"))
        before = exchange.payments.movements
        exchange.release_segment("rcpt-8415-0001", 0, F.release_authority(exchange, 0, "auth-0b"))
        self.assertEqual(exchange.payments.movements, before,
                         "a retry must not send a second payment for an unknown outcome")

    def test_a_restart_queries_before_retrying_and_records_what_it_finds(self):
        exchange, _ = self._exchange({"release:escrow-ab": "unknown"})
        exchange.release_segment("rcpt-8415-0001", 0, F.release_authority(exchange, 0, "auth-0"))
        resumed = exchange.resume_payments("rcpt-8415-0001")
        self.assertEqual(resumed[0]["paymentStatus"], "unknown")
        self.assertIn("no second payment", resumed[0]["action"])
        exchange.payments.resolve_unknown("release:escrow-ab", "settled")
        resumed = exchange.resume_payments("rcpt-8415-0001")
        self.assertEqual(resumed[0]["paymentStatus"], "settled")
        self.assertEqual(exchange.escrow_for_leg("rcpt-8415-0001", 0).status, "released")
        self.assertEqual(exchange.payments.movements, 0,
                         "the enquiry recorded the result; it sent nothing")

    def test_a_substituted_recipient_under_an_existing_key_is_refused(self):
        exchange, _ = self._exchange({})
        exchange.release_segment("rcpt-8415-0001", 0, F.release_authority(exchange, 0, "auth-0"))
        with self.assertRaises(DomainError) as caught:
            exchange.payments.pay("release:escrow-ab", F.B, F.C, F.QUOTE_ASSET, F.PRICE_AB)
        self.assertEqual(caught.exception.code, "EX_PAYMENT_SUBSTITUTION_REFUSED")

    def test_a_repeated_consumption_moves_nothing_more(self):
        exchange, _ = self._exchange({})
        exchange.release_segment("rcpt-8415-0001", 0, F.release_authority(exchange, 0, "auth-0"))
        for _ in range(3):
            exchange.payments.pay("release:escrow-ab", F.B, F.A, F.QUOTE_ASSET, F.PRICE_AB)
        self.assertEqual(exchange.payments.movements, 1)


class Reconciliation(unittest.TestCase):
    """T-31: release and refund are exclusive, and every segment reconciles."""

    def setUp(self):
        self.exchange, _ = F.funded_chain_to_d()
        self.requests = F.submit_all(self.exchange)
        F.confirm(self.exchange, self.requests[0], "res-ab")

    def test_an_escrow_cannot_hold_both_outcomes(self):
        from exchange.settlement import EscrowPosition
        with self.assertRaises(DomainError) as caught:
            EscrowPosition(escrow_id="e", receipt_id="r", leg_index=0, payer=F.B, payee=F.A,
                           quote_asset="q", principal=1, settled_at=1, refunded_at=2)
        self.assertEqual(caught.exception.code, "EX_ESCROW_DOUBLE_OUTCOME_REFUSED")

    def test_the_report_shows_principal_gas_and_net_per_segment(self):
        self.exchange.release_segment("rcpt-8415-0001", 0,
                                      F.release_authority(self.exchange, 0, "auth-0"))
        self.exchange.record_gas("rcpt-8415-0001", 0, "trade", 21_000)
        report = self.exchange.reconciliation("rcpt-8415-0001")
        first = report["segments"][0]
        self.assertEqual(first["principal"], str(F.PRICE_AB))
        self.assertEqual(first["netToPayee"], str(F.PRICE_AB))
        self.assertEqual(first["netToPayer"], "0")
        self.assertEqual(first["gasTotal"], "21000")
        self.assertEqual(first["gasBorneBy"], F.B, "the leg's buyer bears that leg's gas")
        self.assertTrue(first["released"])
        self.assertFalse(first["refunded"])
        self.assertTrue(report["releaseAndRefundMutuallyExclusive"])

    def test_an_unsettled_segment_is_not_reported_as_paid(self):
        report = self.exchange.reconciliation("rcpt-8415-0001")
        for segment in report["segments"]:
            self.assertEqual(segment["netToPayee"], "0")
            self.assertFalse(segment["released"])
            self.assertEqual(segment["escrowStatus"], "locked")

    def test_a_shared_operation_is_not_charged_in_full_to_every_leg(self):
        self.exchange.record_gas("rcpt-8415-0001", 1, "shared-return", 40_000, shared_with=(2,))
        with self.assertRaises(DomainError) as caught:
            self.exchange.record_gas("rcpt-8415-0001", 2, "shared-return", 40_000, shared_with=(1,))
        self.assertEqual(caught.exception.code, "EX_GAS_DOUBLE_CHARGE_REFUSED")
        report = self.exchange.reconciliation("rcpt-8415-0001")
        self.assertEqual(report["segments"][1]["gasTotal"], "40000")
        self.assertEqual(report["segments"][2]["gasTotal"], "0")
        self.assertIn("undecided", report["gasApportionmentForSharedOperations"])

    def test_a_shared_entry_records_the_sharers_and_leaves_the_split_open(self):
        entry = self.exchange.record_gas("rcpt-8415-0001", 1, "shared-return", 40_000,
                                         shared_with=(2,))
        self.assertEqual(entry["sharedWith"], (1, 2))
        self.assertTrue(entry["sharedOperation"])
        self.assertEqual(entry["apportionment"], "undecided")


class FundedConsole(unittest.TestCase):
    """The pages report segment money truthfully once funding is modelled."""

    def setUp(self):
        self.exchange, _ = F.funded_chain_to_d(outcomes={"release:escrow-bc": "unknown"})
        self.requests = F.submit_all(self.exchange)
        F.confirm(self.exchange, self.requests[0], "res-ab")
        F.confirm(self.exchange, self.requests[1], "res-bc")
        self.exchange.release_segment("rcpt-8415-0001", 0,
                                      F.release_authority(self.exchange, 0, "auth-0"))
        self.exchange.release_segment("rcpt-8415-0001", 1,
                                      F.release_authority(self.exchange, 1, "auth-1"))
        self.exchange.record_gas("rcpt-8415-0001", 0, "trade", 21_000)

    def _page(self, name):
        from exchange import views
        return views.page(self.exchange, "rcpt-8415-0001", name,
                          authorization_ids=("auth-sell-ab",), run={"runId": "funded"})

    def test_the_banner_says_payments_are_simulated(self):
        self.assertIn("Payments are simulated", self._page("timeline"))
        self.assertIn("Not provided", self._page("receipt"))

    def test_the_timeline_distinguishes_released_from_unknown(self):
        html = self._page("timeline")
        self.assertIn("released to this leg&#x27;s seller", html)
        self.assertIn("payment outcome unknown", html)
        self.assertIn("no second payment sent", html)

    def test_the_rollback_page_lists_each_segment_separately(self):
        html = self._page("rollback")
        self.assertIn(str(F.PRICE_AB), html)
        self.assertIn(str(F.PRICE_BC), html)
        self.assertIn(str(F.PRICE_CD), html)
        self.assertIn("Net to seller", html)
        self.assertIn("Gas borne by buyer", html)
        self.assertIn("apportionment is still undecided", html)

    def test_an_unknown_payment_is_not_shown_as_net_paid(self):
        report = self.exchange.reconciliation("rcpt-8415-0001")
        self.assertEqual(report["segments"][1]["netToPayee"], "0")
        self.assertEqual(report["segments"][1]["paymentStatus"], "unknown")
        self.assertFalse(report["segments"][1]["released"])

    def test_the_receipt_page_states_that_each_leg_funds_itself(self):
        self.assertIn("this leg&#x27;s buyer funded its own escrow", self._page("timeline"))


if __name__ == "__main__":
    unittest.main()
