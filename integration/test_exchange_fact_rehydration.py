"""Synthetic second-Exchange reconstruction; no live process or wallet restart."""
import unittest

from exchange import fixtures as F
from exchange.exchange_fact_rehydration import rehydrate_exchange_facts, ExchangeRehydrationRefused
from exchange.exchange_fact_snapshot import encode_exchange_snapshot
from exchange.ledger import Exchange
from exchange.tests.test_rollback import refused_at_ab


R = "rcpt-8415-0001"


def current_runtime(original, *, sessions=False):
    runtime = Exchange(original._clock, payment_adapter=original.payments,
        release_sources=original._release_sources, funding_required=original.funding_required,
        asset_control=original.asset_control, rollback_sources=original._rollback_sources,
        gas_budgets=original._budgets, voucher_desk=original.voucher_desk,
        mint_verifier=original._mint_book.verify if original._mint_book else None,
        eth_gas_gate=original._eth_gas_gate, price_balance_gate=original._price_balance_gate,
        priority_store=original._priority_store)
    runtime.registrars = original.registrars
    if sessions:
        for account, session in original._sessions.items():
            runtime.connect_wallet(account, session)
    return runtime


class ExchangeFactRehydrationTests(unittest.TestCase):
    def opened(self):
        exchange, _, _ = refused_at_ab()
        state = exchange.begin_rollback(R, 0, F.rollback_authority(exchange, 0, "rehydration"))
        return exchange, state

    def test_second_exchange_preserves_completed_direct_return_without_another_effect(self):
        exchange, state = self.opened()
        exchange.advance_rollback(R)
        before_keys = set(exchange.asset_control._records)
        movements = exchange.payments.movements
        restored = rehydrate_exchange_facts(encode_exchange_snapshot(exchange), current_runtime(exchange))
        self.assertEqual(restored.owner_of(R), F.A)
        self.assertTrue(restored.rollback_report(R)["complete"])
        self.assertEqual(set(exchange.asset_control._records), before_keys)
        report = restored.advance_rollback(R)
        self.assertTrue(report["complete"])
        self.assertEqual(restored.owner_of(R), F.A)
        self.assertEqual(exchange.asset_control.returns, 1)
        self.assertEqual(exchange.asset_control.hops_walked, 0)
        self.assertEqual(exchange.payments.movements, movements)
        self.assertEqual(state["state"], "complete")

    def test_unknown_direct_return_is_reconstructed_without_enquiry_or_new_send(self):
        exchange, state = self.opened()
        key = "return:" + R + ":rehydration"
        exchange.asset_control._outcomes[key] = "unknown"
        exchange.advance_rollback(R)
        calls = []
        lookup = exchange.asset_control.lookup
        def counted(identity):
            calls.append(identity)
            return lookup(identity)
        exchange.asset_control.lookup = counted
        restored = rehydrate_exchange_facts(encode_exchange_snapshot(exchange), current_runtime(exchange))
        self.assertEqual(calls, [])
        self.assertFalse(restored.advance_rollback(R)["complete"])
        self.assertEqual(calls, [key])
        self.assertEqual(len(exchange.asset_control._records), 1)
        self.assertEqual(restored.owner_of(R), F.D)
        exchange.asset_control.resolve_unknown(key, "returned")
        self.assertTrue(restored.advance_rollback(R)["complete"])
        self.assertEqual(restored.owner_of(R), F.A)
        self.assertEqual(exchange.asset_control.returns, 0)
        self.assertEqual(len(exchange.asset_control._records), 1)

    def test_snapshot_session_does_not_reconnect_wallet_and_current_session_is_kept(self):
        exchange, _ = self.opened()
        raw = encode_exchange_snapshot(exchange)
        empty = rehydrate_exchange_facts(raw, current_runtime(exchange))
        self.assertEqual(empty._exchange._sessions, {})
        runtime = current_runtime(exchange)
        runtime.connect_wallet(F.A, "current-session-a")
        restored = rehydrate_exchange_facts(raw, runtime)
        self.assertEqual(restored._exchange._sessions, {F.A: "current-session-a"})
        self.assertEqual(runtime._receipts, {})

    def test_known_current_revocation_overrides_older_saved_reference(self):
        exchange, _ = self.opened()
        reference = next(iter(exchange._authorizations.values()))
        runtime = current_runtime(exchange, sessions=True)
        runtime.register_authorization(reference.revoke())
        restored = rehydrate_exchange_facts(encode_exchange_snapshot(exchange), runtime)
        self.assertTrue(restored.authorization(reference.authorization_id).revoked)
        self.assertIn("EX_AUTH_REVOKED", restored.authorization_state(reference.authorization_id)["reasons"])

    def test_current_and_saved_consumed_nonce_sets_are_both_retained(self):
        exchange, _ = self.opened()
        runtime = current_runtime(exchange)
        runtime._used_nonces.add((F.A, 123456))
        restored = rehydrate_exchange_facts(encode_exchange_snapshot(exchange), runtime)
        self.assertEqual(restored._exchange._used_nonces,
                         exchange._used_nonces | {(F.A, 123456)})
        self.assertEqual(runtime._used_nonces, {(F.A, 123456)})

    def test_priority_sequence_and_original_intent_are_rebuilt_without_new_admission(self):
        exchange, _ = F.minted()
        exchange.register_authorization(F.authorization(F.A, "rehydrate-sell", "session-a"))
        intent = F.intent("rehydrate-order", "sell", F.A, "rehydrate-sell", None, 77)
        exchange.submit_intent(intent)
        original = exchange._order_books[(R, F.QUOTE_ASSET)]
        restored = rehydrate_exchange_facts(encode_exchange_snapshot(exchange),
                                            current_runtime(exchange, sessions=True))
        book = restored._exchange._order_books[(R, F.QUOTE_ASSET)]
        self.assertIs(book.exchange, restored._exchange)
        self.assertIsNot(book._lock, original._lock)
        self.assertEqual(book._entries, original._entries)
        self.assertEqual(book._nonces, original._nonces)
        self.assertEqual(book._sequence, original._sequence)
        self.assertEqual(book._book_scope, original._book_scope)
        self.assertEqual(restored.enter_order(intent.intent_id), original._entries[intent.intent_id][1])
        self.assertEqual(book._sequence, original._sequence)

    def test_mint_uniqueness_and_current_verifier_survive_without_callback_execution(self):
        exchange, _ = self.opened()
        runtime = current_runtime(exchange)
        def forbidden(*args):
            raise AssertionError("rehydration called a declaration verifier")
        runtime._mint_book.verify = forbidden
        restored = rehydrate_exchange_facts(encode_exchange_snapshot(exchange), runtime)
        self.assertIs(restored._exchange._mint_book.verify, forbidden)
        for name in ("_assets", "_receipts", "_documents"):
            self.assertEqual(getattr(restored._exchange._mint_book, name),
                             getattr(exchange._mint_book, name))
            self.assertEqual(getattr(runtime._mint_book, name), {})

    def test_existing_domain_history_is_not_overwritten(self):
        exchange, _ = self.opened()
        before = encode_exchange_snapshot(exchange)
        with self.assertRaises(ExchangeRehydrationRefused):
            rehydrate_exchange_facts(before, exchange)
        self.assertEqual(encode_exchange_snapshot(exchange), before)
