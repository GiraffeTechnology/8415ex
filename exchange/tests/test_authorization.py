"""T-06, T-08, T-34: wallet authorization, session changes, and no second
approval layer on top of what the wallet already granted."""
import unittest

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.model import Asset


class AuthorizationChecks(unittest.TestCase):
    """T-06: unauthorized, expired, revoked or altered intents do not execute."""

    def setUp(self):
        self.exchange, self.clock = F.minted()
        self.exchange.connect_wallet(F.B, "session-b")
        self.exchange.register_authorization(
            F.authorization(F.A, "auth-a", "session-a", counterparties=(F.B,)))
        self.exchange.register_authorization(
            F.authorization(F.B, "auth-b", "session-b", counterparties=(F.A,)))

    def _sell(self, **changes):
        base = dict(intent_id="sell-1", side="sell", signer=F.A, authorization_id="auth-a",
                    counterparty=F.B, nonce=1)
        base.update(changes)
        return self.exchange.submit_intent(F.intent(**base))

    def test_an_intent_with_no_authorization_on_record_is_refused(self):
        intent = self._sell(intent_id="sell-none", authorization_id="auth-missing")
        report = self.exchange.validate_intent(intent.intent_id)
        self.assertFalse(report["executable"])
        self.assertIn("EX_AUTH_UNKNOWN", report["reasons"])

    def test_an_expired_authorization_is_refused(self):
        intent = self._sell()
        self.clock.now = 1_700_800_001
        report = self.exchange.validate_intent(intent.intent_id)
        self.assertFalse(report["executable"])
        self.assertIn("EX_AUTH_EXPIRED", report["reasons"])

    def test_an_authorization_not_yet_valid_is_refused(self):
        self.exchange.register_authorization(
            F.authorization(F.A, "auth-future", "session-a", counterparties=(F.B,),
                            not_before=1_700_500_000, expires_at=1_700_800_000))
        intent = self._sell(intent_id="sell-future", authorization_id="auth-future")
        report = self.exchange.validate_intent(intent.intent_id, now=1_700_000_000)
        self.assertFalse(report["executable"])
        self.assertIn("EX_AUTH_NOT_YET_VALID", report["reasons"])

    def test_a_revoked_authorization_is_refused(self):
        intent = self._sell()
        self.exchange.revoke_authorization("auth-a")
        report = self.exchange.validate_intent(intent.intent_id)
        self.assertFalse(report["executable"])
        self.assertIn("EX_AUTH_REVOKED", report["reasons"])

    def test_a_revoked_authorization_cannot_start_a_new_trade(self):
        self._sell(counterparty=None)
        self.exchange.submit_intent(F.intent("buy-1", "buy", F.B, "auth-b", None, 1))
        self.exchange.match_intents("sell-1", "buy-1")
        self.exchange.revoke_authorization("auth-a")
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents("sell-1", "buy-1")
        self.assertEqual(caught.exception.code, "EX_MATCH_UNEXECUTABLE")
        self.assertEqual(self.exchange.owner_index("rcpt-8415-0001"), 0)

    def test_an_amount_above_the_signed_bound_is_refused(self):
        intent = self._sell(intent_id="sell-rich", limit_price=F.PRICE + 1, nonce=2)
        report = self.exchange.validate_intent(intent.intent_id)
        self.assertFalse(report["executable"])
        self.assertIn("EX_AUTH_AMOUNT_REFUSED", report["reasons"])

    def test_another_asset_is_refused(self):
        self.exchange.register_authorization(
            F.authorization(F.A, "auth-other-asset", "session-a", counterparties=(F.B,),
                            asset_override=Asset(F.CHAIN_ID, F.CONTRACT, 777)))
        intent = self._sell(intent_id="sell-other-asset", authorization_id="auth-other-asset", nonce=3)
        report = self.exchange.validate_intent(intent.intent_id)
        self.assertFalse(report["executable"])
        self.assertIn("EX_AUTH_ASSET_REFUSED", report["reasons"])

    def test_an_action_outside_the_signed_scope_is_refused(self):
        self.exchange.register_authorization(
            F.authorization(F.A, "auth-buy-only", "session-a", counterparties=(F.B,), actions=("buy",)))
        intent = self._sell(intent_id="sell-wrong-action", authorization_id="auth-buy-only", nonce=4)
        report = self.exchange.validate_intent(intent.intent_id)
        self.assertFalse(report["executable"])
        self.assertIn("EX_AUTH_ACTION_REFUSED", report["reasons"])

    def test_an_unlisted_counterparty_is_refused(self):
        intent = self._sell(intent_id="sell-wrong-party", counterparty=F.C, nonce=5)
        report = self.exchange.validate_intent(intent.intent_id)
        self.assertFalse(report["executable"])
        self.assertIn("EX_AUTH_COUNTERPARTY_REFUSED", report["reasons"])

    def test_an_authorization_for_a_foreign_chain_cannot_be_constructed(self):
        with self.assertRaises(DomainError) as caught:
            F.authorization(F.A, "auth-foreign", "session-a",
                            asset_override=Asset(1, F.CONTRACT, F.TOKEN_ID))
        self.assertEqual(caught.exception.code, "EX_AUTH_CHAIN_REFUSED")

    def test_an_expired_intent_is_refused_even_under_a_valid_authorization(self):
        intent = self._sell(intent_id="sell-stale", expires_at=1_700_000_000, nonce=6)
        report = self.exchange.validate_intent(intent.intent_id, now=1_700_000_001)
        self.assertFalse(report["executable"])
        self.assertIn("EX_INTENT_EXPIRED", report["reasons"])

    def test_altering_a_signed_term_changes_the_digest(self):
        original = self._sell()
        altered = F.intent("sell-1", "sell", F.A, "auth-a", F.B, 1, limit_price=F.PRICE - 1)
        self.assertNotEqual(original.digest, altered.digest)
        with self.assertRaises(DomainError) as caught:
            self.exchange.submit_intent(altered)
        self.assertEqual(caught.exception.code, "EX_INTENT_CONFLICT")


class SessionAndAccountChanges(unittest.TestCase):
    """T-08: switching, disconnecting or losing a session does not carry the
    previous account's authorization forward."""

    def setUp(self):
        self.exchange, self.clock = F.minted()
        self.exchange.register_authorization(
            F.authorization(F.A, "auth-a", "session-a", counterparties=(F.B,)))
        self.exchange.connect_wallet(F.B, "session-b")
        self.exchange.register_authorization(
            F.authorization(F.B, "auth-b", "session-b", counterparties=(F.A,)))
        self.exchange.submit_intent(F.intent("sell-1", "sell", F.A, "auth-a", None, 1))
        self.exchange.submit_intent(F.intent("buy-1", "buy", F.B, "auth-b", None, 1))
        self.exchange.match_intents("sell-1", "buy-1")

    def test_a_lost_session_refuses_the_authorization(self):
        self.exchange.disconnect_wallet(F.A)
        state = self.exchange.authorization_state("auth-a")
        self.assertFalse(state["applies"])
        self.assertIn("EX_AUTH_SESSION_LOST", state["reasons"])
        report = self.exchange.validate_intent("sell-1")
        self.assertIn("EX_AUTH_SESSION_LOST", report["reasons"])

    def test_a_reconnected_different_session_refuses_the_old_authorization(self):
        self.exchange.connect_wallet(F.A, "session-a-new")
        state = self.exchange.authorization_state("auth-a")
        self.assertFalse(state["applies"])
        self.assertIn("EX_AUTH_SESSION_REFUSED", state["reasons"])
        self.assertEqual(state["activeSession"], "session-a-new")
        self.assertEqual(state["boundSession"], "session-a")

    def test_switching_the_selected_account_does_not_reuse_the_previous_grant(self):
        self.exchange.switch_account(F.C, "session-c")
        report = self.exchange.validate_intent("sell-1")
        self.assertTrue(report["executable"], "switching to C must not disturb A's own session")
        self.exchange.switch_account(F.A, "session-a-switched")
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents("sell-1", "buy-1")
        self.assertEqual(caught.exception.code, "EX_MATCH_UNEXECUTABLE")
        self.assertEqual(self.exchange.owner_index("rcpt-8415-0001"), 0)

    def test_an_authorization_cannot_be_used_for_another_account(self):
        intent = self.exchange.submit_intent(F.intent("sell-impostor", "sell", F.B, "auth-a", F.A, 5))
        report = self.exchange.validate_intent(intent.intent_id)
        self.assertFalse(report["executable"])
        self.assertIn("EX_AUTH_ACCOUNT_REFUSED", report["reasons"])


class NoSecondApprovalLayer(unittest.TestCase):
    """T-34: inside the wallet's grant, consecutive agent actions need no extra
    step-by-step platform approval; outside it they are still refused."""

    def test_three_consecutive_hops_execute_with_no_additional_approval(self):
        exchange, _ = F.minted()
        for seller, buyer, nonce, transfer in ((F.A, F.B, 1, "transfer-ab"),
                                               (F.B, F.C, 2, "transfer-bc"),
                                               (F.C, F.D, 3, "transfer-cd")):
            leg = F.hop(exchange, seller, buyer, nonce, transfer,
                        f"session-{seller[-1]}", f"session-{buyer[-1]}")
            self.assertEqual(leg.execution_status, "executed")
        self.assertEqual(exchange.owner_index("rcpt-8415-0001"), 3)

    def test_execute_transfer_accepts_no_platform_approval_argument(self):
        """There is no approval token to pass: the wallet grant is the authority."""
        import inspect

        from exchange.ledger import Exchange
        parameters = set(inspect.signature(Exchange.execute_transfer).parameters)
        self.assertEqual(parameters, {"self", "match", "transfer_id", "escrow_id", "now", "deferred_admission"},
                         "escrow and optional deferred funding ports are not platform approval tokens")
        self.assertIsNone(inspect.signature(Exchange.execute_transfer).parameters["deferred_admission"].default)
        self.assertEqual(inspect.signature(Exchange.execute_transfer).parameters["deferred_admission"].kind, inspect.Parameter.KEYWORD_ONLY)
        for forbidden in ("approval", "platform_approval", "operator_approval", "override",
                          "operator_sign_off", "manual_confirm"):
            self.assertNotIn(forbidden, parameters)

    def test_an_action_beyond_the_grant_is_still_refused_within_the_same_session(self):
        exchange, _ = F.minted()
        F.hop(exchange, F.A, F.B, 1, "transfer-ab", "session-a", "session-b")
        exchange.register_authorization(
            F.authorization(F.B, "auth-b-scoped", "session-b", counterparties=(F.C,),
                            max_amount=F.PRICE - 1))
        exchange.connect_wallet(F.C, "session-c")
        exchange.register_authorization(
            F.authorization(F.C, "auth-c", "session-c", counterparties=(F.B,)))
        exchange.submit_intent(F.intent("sell-over", "sell", F.B, "auth-b-scoped", F.C, 8))
        exchange.submit_intent(F.intent("buy-over", "buy", F.C, "auth-c", F.B, 8))
        with self.assertRaises(DomainError) as caught:
            exchange.match_intents("sell-over", "buy-over")
        self.assertEqual(caught.exception.code, "EX_MATCH_UNEXECUTABLE")
        self.assertEqual(exchange.owner_index("rcpt-8415-0001"), 1)


if __name__ == "__main__":
    unittest.main()
