"""Synthetic verified facts only; no chain, provider, signer or deployment claim."""
from dataclasses import asdict, replace
from copy import deepcopy
import unittest

from exchange.deferred_settlement import DeferredSettlement, DeferredRefused, Fact, Profile
from exchange.ids import digest


class SyntheticVerifier:
    """Explicit test-only fixture, never a production proof implementation."""
    def __init__(self):
        self.facts = {}

    def encode(self, fact):
        raw = ("synthetic:" + fact.identity).encode()
        self.facts[raw] = fact
        return raw

    def verify(self, raw, *, kind, now):
        if raw not in self.facts or self.facts[raw].kind != kind:
            raise DeferredRefused("unauthenticated synthetic input")
        return self.facts[raw]


class DeferredTests(unittest.TestCase):
    def setUp(self):
        self.profile = Profile(11155111, "PYUSD", 560048, "ETH", "hoodi-vault",
                               "sepolia-escrow", "explicit-test-policy", 5000, 100)
        self.verifier = SyntheticVerifier()
        self.engine = DeferredSettlement(self.profile, self.verifier)
        self.counter = 0
        self.lock()

    def fact(self, kind, *, chain=None, asset=None, account="B", location=None,
             reference="ab", units=0, at=100, principal_value=0, destination_units=0):
        self.counter += 1
        value = Fact("fact-%d" % self.counter, kind,
                     self.profile.settlement_chain if chain is None else chain,
                     self.profile.principal_asset if asset is None else asset,
                     account, self.profile.escrow if location is None else location,
                     reference, units, at, principal_value, destination_units)
        return self.verifier.encode(value)

    def lock(self, identity="lock-1", **overrides):
        fields = dict(chain=560048, asset="ETH", account="B", location="hoodi-vault",
                      reference=identity, units=100, principal_value=2000)
        fields.update(overrides)
        raw = self.fact("collateral-lock", **fields)
        self.engine.admit_lock(raw, now=100)
        return raw

    def reserve(self, *, identity="ab", principal=800, fee=0, deadline=200):
        terms = digest({"id": identity, "lock": "lock-1", "borrower": "B", "seller": "A",
                        "principal": principal, "fee": fee, "deadline": deadline,
                        "profile": asdict(self.profile)})
        consent = self.fact("seller-consent", account="A", reference=terms, units=principal + fee)
        admission = self.fact("deferred-admission", reference=terms, units=principal + fee)
        return self.engine.reserve(identity, "lock-1", borrower="B", seller="A", principal=principal,
                    fee=fee, deadline=deadline, now=100, seller_consent=consent, borrower_authority=admission)

    def register(self, *, at=150):
        raw = self.fact("registration-cut", at=at)
        self.engine.observe_registration("ab", raw, now=max(150, at))

    def credit(self, units, **fields):
        raw = self.fact("principal-allocation", units=units, **fields)
        self.engine.credit_escrow("ab", raw, now=150)
        return raw

    def quote(self, kind, target, *, asset="PYUSD"):
        item = self.engine.obligations["ab"]
        binding = digest({"obligation": "ab", "kind": kind, "target": target, "asset": asset,
                          "chain": 11155111, "recipient": "sepolia-escrow", "consent": item.consent})
        return self.fact("liquidation-quote", chain=560048, asset="ETH", location="hoodi-vault",
                         reference=binding, units=50, destination_units=target, at=200)

    def reach_deadline(self, *, registered=False):
        evidence = self.fact("deadline-registration", units=int(registered), at=200)
        return self.engine.deadline("ab", now=200, registration_evidence=evidence)

    def complete(self, op, *, units=None, chain=None):
        self.engine.mark_dispatched(op.identity)
        raw = self.fact("operation-receipt", chain=op.chain if chain is None else chain,
                        asset=op.asset, account=op.recipient, reference=op.commitment,
                        units=op.units if units is None else units, at=200)
        return self.engine.confirm(op.identity, raw, now=200), raw

    def test_verified_lock_ratio_and_wrong_chain_refused(self):
        self.assertEqual(self.engine.locks["lock-1"].capacity, 1000)
        before = self.engine.snapshot()
        with self.assertRaises(DeferredRefused):
            self.lock("wrong", chain=11155111)
        self.assertEqual(self.engine.snapshot(), before)

    def test_missing_evidence_never_grants_allowance(self):
        with self.assertRaises(DeferredRefused):
            self.engine.admit_lock(b'not-proof', now=100)

    def test_lock_identity_and_evidence_replay_never_double_capacity(self):
        raw = self.lock("lock-2")
        self.engine.admit_lock(raw, now=100)
        self.assertEqual(len(self.engine.locks), 2)
        with self.assertRaises(DeferredRefused):
            self.lock("lock-2")

    def test_consent_and_wallet_admission_required(self):
        item = self.reserve()
        self.assertEqual(item.paid, 0)
        self.assertEqual(self.engine.locks["lock-1"].reserved, 800)
        with self.assertRaises(DeferredRefused):
            self.reserve(identity="other")

    def test_capacity_includes_fee_without_loan_or_interest(self):
        with self.assertRaises(DeferredRefused):
            self.reserve(principal=1000, fee=1)
        self.assertEqual(self.engine.locks["lock-1"].reserved, 0)

    def test_unregistered_deadline_rolls_back_not_waits_for_payment(self):
        self.reserve()
        self.credit(800)
        self.assertEqual(self.reach_deadline(), "ROLLBACK_REQUIRED")
        with self.assertRaises(DeferredRefused):
            self.engine.prepare("pay", "ab", kind="seller-payment", now=200)
        self.register()
        self.assertTrue(self.engine.obligations["ab"].registered)
        self.assertFalse(self.engine.obligations["ab"].rollback)

    def test_registered_unpaid_debt_never_reopens_nft_rollback(self):
        self.reserve()
        self.register()
        self.assertEqual(self.engine.deadline("ab", now=200), "DEBT_LIQUIDATION_REQUIRED")
        self.assertFalse(self.engine.obligations["ab"].rollback)
        with self.assertRaises(DeferredRefused):
            self.engine.prepare("reverse", "ab", kind="rollback", now=200)

    def test_early_payment_needs_registration_and_full_selected_principal(self):
        self.reserve()
        self.credit(800)
        with self.assertRaises(DeferredRefused):
            self.engine.prepare("pay", "ab", kind="seller-payment", now=150)
        self.register()
        op = self.engine.prepare("pay", "ab", kind="seller-payment", now=150)
        self.complete(op)
        self.assertEqual(self.engine.obligations["ab"].paid, 800)
        self.assertFalse(self.engine.obligations["ab"].rollback)

    def test_deposit_wrong_currency_and_chain_fail_closed(self):
        self.reserve()
        for fields in ({"asset": "USDC"}, {"chain": 560048}):
            with self.assertRaises(DeferredRefused):
                self.credit(800, **fields)
        self.assertEqual(self.engine.obligations["ab"].escrow, 0)

    def test_deposit_and_payment_replay_are_idempotent(self):
        self.reserve()
        raw = self.credit(800)
        self.engine.credit_escrow("ab", raw, now=150)
        self.register()
        op = self.engine.prepare("pay", "ab", kind="seller-payment", now=150)
        _, receipt = self.complete(op)
        self.engine.confirm("pay", receipt, now=200)
        self.assertEqual(self.engine.obligations["ab"].paid, 800)
        self.assertEqual(self.engine.locks["lock-1"].reserved, 0)

    def test_unknown_payment_cannot_be_sent_again_or_reallocated(self):
        self.reserve(); self.credit(800); self.register()
        op = self.engine.prepare("pay", "ab", kind="seller-payment", now=150)
        self.engine.mark_dispatched(op.identity)
        with self.assertRaises(DeferredRefused):
            self.engine.mark_dispatched(op.identity)
        with self.assertRaises(DeferredRefused):
            self.engine.prepare("pay-again", "ab", kind="seller-payment", now=150)
        with self.assertRaises(DeferredRefused):
            self.credit(1)

    def test_liquidation_requires_quote_and_destination_receipt_not_source_sale(self):
        self.reserve(); self.register(); self.credit(300)
        q = self.quote("debt-liquidation", 500)
        op = self.engine.prepare("liquidate", "ab", kind="debt-liquidation", now=200, liquidation_quote=q)
        self.assertEqual(op.collateral_limit, 50)
        self.engine.mark_dispatched(op.identity)
        wrong = self.fact("operation-receipt", chain=560048, asset="ETH", account=op.recipient,
                          reference=op.commitment, units=500, at=200)
        with self.assertRaises(DeferredRefused):
            self.engine.confirm(op.identity, wrong, now=200)
        self.assertEqual(self.engine.obligations["ab"].escrow, 300)
        right = self.fact("operation-receipt", account=op.recipient, reference=op.commitment, units=500, at=200)
        self.engine.confirm(op.identity, right, now=200)
        self.assertEqual(self.engine.obligations["ab"].paid, 0)
        self.assertEqual(self.engine.obligations["ab"].escrow, 800)

    def test_partial_liquidation_proceeds_leave_visible_shortfall(self):
        self.reserve(); self.register()
        op = self.engine.prepare("liquidate", "ab", kind="debt-liquidation", now=200,
                                 liquidation_quote=self.quote("debt-liquidation", 800))
        self.complete(op, units=300)
        self.assertEqual(self.engine.deadline("ab", now=200), "DEBT_LIQUIDATION_REQUIRED")
        self.assertFalse(self.engine.obligations["ab"].resolved)

    def test_rollback_gas_shortage_uses_separate_destination_eth(self):
        self.reserve(); self.credit(800); self.reach_deadline()
        with self.assertRaises(DeferredRefused):
            self.engine.prepare("return", "ab", kind="rollback", now=200)
        raw = self.fact("rollback-gas-shortfall", asset="ETH", units=10, at=200)
        self.engine.observe_gas_requirement("ab", raw, now=200)
        op = self.engine.prepare("gas", "ab", kind="gas-liquidation", now=200,
                                 liquidation_quote=self.quote("gas-liquidation", 10, asset="ETH"))
        self.assertEqual((op.asset, op.chain, op.units), ("ETH", 11155111, 10))
        self.complete(op)
        rollback = self.engine.prepare("return", "ab", kind="rollback", now=200)
        self.complete(rollback)
        self.assertTrue(self.engine.obligations["ab"].rollback_confirmed)
        self.assertEqual(self.engine.obligations["ab"].paid, 0)

    def test_unlock_requires_resolution_and_excess_refund(self):
        self.reserve(); self.credit(900); self.register()
        with self.assertRaises(DeferredRefused):
            self.engine.prepare("unlock", "ab", kind="collateral-unlock", now=150)
        self.complete(self.engine.prepare("pay", "ab", kind="seller-payment", now=150))
        with self.assertRaises(DeferredRefused):
            self.engine.prepare("unlock", "ab", kind="collateral-unlock", now=200)
        self.complete(self.engine.prepare("excess", "ab", kind="excess-refund", now=200))
        self.complete(self.engine.prepare("unlock", "ab", kind="collateral-unlock", now=200))
        self.assertTrue(self.engine.locks["lock-1"].released)

    def test_restart_preserves_unknown_and_rejects_lost_reservation(self):
        self.reserve(); self.credit(800); self.register()
        op = self.engine.prepare("pay", "ab", kind="seller-payment", now=150)
        self.engine.mark_dispatched(op.identity)
        copy = DeferredSettlement.restore(self.profile, self.verifier, self.engine.snapshot())
        self.assertEqual(copy.operations["pay"].status, "UNKNOWN")
        with self.assertRaises(DeferredRefused):
            copy.mark_dispatched("pay")
        broken = deepcopy(self.engine.snapshot()); broken["locks"]["lock-1"]["reserved"] = 0
        with self.assertRaises(DeferredRefused):
            DeferredSettlement.restore(self.profile, self.verifier, broken)

    def test_missing_local_registration_is_not_rollback_authority(self):
        self.reserve()
        self.assertEqual(self.engine.deadline("ab", now=200), "REGISTRATION_RECONCILIATION_REQUIRED")
        self.assertFalse(self.engine.obligations["ab"].rollback)
        with self.assertRaises(DeferredRefused):
            self.engine.prepare("return", "ab", kind="rollback", now=200)
        self.register(at=150)
        self.assertEqual(self.engine.deadline("ab", now=200), "DEBT_LIQUIDATION_REQUIRED")

    def test_authoritative_registered_deadline_cut_preserves_prefix(self):
        self.reserve()
        self.assertEqual(self.reach_deadline(registered=True), "DEBT_LIQUIDATION_REQUIRED")
        self.assertTrue(self.engine.obligations["ab"].registered)
        self.assertFalse(self.engine.obligations["ab"].rollback)

    def test_prepared_unlock_blocks_new_borrowing_before_dispatch(self):
        self.reserve(); self.credit(800); self.register()
        self.complete(self.engine.prepare("pay", "ab", kind="seller-payment", now=150))
        unlock = self.engine.prepare("unlock", "ab", kind="collateral-unlock", now=200)
        self.assertTrue(self.engine.locks["lock-1"].release_pending)
        with self.assertRaises(DeferredRefused):
            self.reserve(identity="new-debt")
        self.complete(unlock)
        self.assertTrue(self.engine.locks["lock-1"].released)

    def test_partial_liquidations_reserve_source_caps_until_verified_consumption(self):
        self.reserve(); self.register()
        first = self.engine.prepare("sale-1", "ab", kind="debt-liquidation", now=200,
                                    liquidation_quote=self.quote("debt-liquidation", 800))
        self.complete(first, units=200)
        second = self.engine.prepare("sale-2", "ab", kind="debt-liquidation", now=200,
                                     liquidation_quote=self.quote("debt-liquidation", 600))
        self.complete(second, units=200)
        with self.assertRaises(DeferredRefused):
            self.engine.prepare("sale-3", "ab", kind="debt-liquidation", now=200,
                                liquidation_quote=self.quote("debt-liquidation", 400))
        for op in (first, second):
            proof = self.fact("liquidation-source", chain=560048, asset="ETH", location="hoodi-vault",
                              reference=op.commitment, units=50, at=200)
            self.engine.observe_liquidation_source(op.identity, proof, now=200)
            self.engine.observe_liquidation_source(op.identity, proof, now=200)
        self.assertEqual(self.engine.locks["lock-1"].units, 0)
        self.assertEqual(self.engine.obligations["ab"].escrow, 400)
        self.assertFalse(self.engine.obligations["ab"].resolved)
        self.assertEqual(self.engine.deadline("ab", now=200), "DEBT_LIQUIDATION_REQUIRED")

    def test_late_timely_cut_cancels_only_unsent_rollback(self):
        self.reserve(); self.credit(800); self.reach_deadline()
        gas = self.fact("rollback-gas-shortfall", asset="ETH", units=0, at=200)
        self.engine.observe_gas_requirement("ab", gas, now=200)
        op = self.engine.prepare("return", "ab", kind="rollback", now=200)
        self.register(at=150)
        self.assertEqual(op.status, "FAILED")
        with self.assertRaises(DeferredRefused):
            self.engine.mark_dispatched(op.identity)
        self.assertFalse(self.engine.obligations["ab"].rollback)

    def test_prepared_unlock_retry_returns_same_operation_without_new_reservation(self):
        self.reserve(); self.credit(800); self.register()
        self.complete(self.engine.prepare("pay", "ab", kind="seller-payment", now=150))
        first = self.engine.prepare("unlock", "ab", kind="collateral-unlock", now=200)
        second = self.engine.prepare("unlock", "ab", kind="collateral-unlock", now=201)
        self.assertIs(first, second)
        with self.assertRaises(DeferredRefused):
            self.engine.prepare("unlock", "ab", kind="collateral-unlock", now=201, units=99)

    def test_liquidation_retry_excludes_own_reserved_cap_and_rejects_changed_quote(self):
        self.reserve(); self.register()
        quote = self.quote("debt-liquidation", 800)
        original = self.verifier.facts[quote]
        self.verifier.facts[quote] = replace(original, units=80)
        first = self.engine.prepare("sale", "ab", kind="debt-liquidation", now=200, liquidation_quote=quote)
        self.assertIs(self.engine.prepare("sale", "ab", kind="debt-liquidation", now=201,
                                         liquidation_quote=quote), first)
        with self.assertRaises(DeferredRefused):
            self.engine.prepare("sale", "ab", kind="debt-liquidation", now=201,
                                liquidation_quote=self.quote("debt-liquidation", 800))
