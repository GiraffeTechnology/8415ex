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
                               "sepolia-escrow", "explicit-test-policy", 5000, 100, "case", "ex-fee-receiver")
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
                     reference, units, at, principal_value, destination_units, digest(asdict(self.profile)))
        return self.verifier.encode(value)

    def lock(self, identity="lock-1", **overrides):
        fields = dict(chain=560048, asset="ETH", account="B", location="hoodi-vault",
                      reference=identity, units=100, principal_value=2000)
        fields.update(overrides)
        raw = self.fact("collateral-lock", **fields)
        self.engine.admit_lock(raw, now=100)
        return raw

    def normal_gas(self, identity="ab"):
        return {"budget": "normal-budget-" + identity, "quote": "normal-quote-" + identity,
                "scope": "normal-scope-" + identity, "grant": "normal-grant-" + identity,
                "location": "original-normal-gas-journal", "capWei": 10,
                "maxAgeSeconds": 100, "payer": "B"}

    def source_normal_gas(self, identity="ab"):
        # A separately evidenced original Hoodi budget, never a derived bridge
        # or a claim that a Sepolia receipt is already spendable on Hoodi.
        return {"budget": "source-normal-budget-" + identity, "quote": "source-normal-quote-" + identity,
                "scope": "source-normal-scope-" + identity, "grant": "source-normal-grant-" + identity,
                "location": "original-source-normal-gas-journal", "capWei": 7,
                "maxAgeSeconds": 100, "payer": "synthetic-source-treasury"}

    def reserve_arguments(self, *, identity="ab", principal=800, fee=20,
                          deadline=200, now=100, normal_gas=None, source_normal_gas=None):
        # These numbers are synthetic fixtures, not a production fee or rate.
        normal = self.normal_gas(identity) if normal_gas is None else deepcopy(normal_gas)
        source = self.source_normal_gas(identity) if source_normal_gas is None else deepcopy(source_normal_gas)
        terms = digest({"id": identity, "lock": "lock-1", "borrower": "B", "seller": "A",
                        "principal": principal, "settlementFeeWei": fee, "normalGas": normal,
                        "sourceNormalGas": source, "deadline": deadline, "profile": asdict(self.profile)})
        consent = self.fact("seller-consent", account="A", reference=terms, units=principal, at=now)
        admission = self.fact("deferred-admission", reference=terms, units=principal, at=now)
        receipt = self.fact("settlement-fee-receipt", asset="ETH", reference=terms,
                            location=self.profile.fee_receiver, units=fee, at=now)
        allocation_reference = digest({"terms": terms,
            "feeReceipt": self.verifier.facts[receipt].identity, "normalGas": normal})
        allocation = self.fact("normal-gas-allocation", asset="ETH", reference=allocation_reference,
                               location=normal["location"], units=normal["capWei"], at=now)
        source_reference = digest({"terms": terms,
            "feeReceipt": self.verifier.facts[receipt].identity, "sourceNormalGas": source})
        source_allocation = self.fact("source-normal-gas-allocation", chain=self.profile.collateral_chain,
            asset="ETH", reference=source_reference, location=source["location"], units=source["capWei"], at=now)
        return dict(borrower="B", seller="A", principal=principal, settlement_fee_wei=fee,
                    normal_gas=normal, source_normal_gas=source, deadline=deadline, now=now,
                    seller_consent=consent, borrower_authority=admission, fee_receipt=receipt,
                    gas_allocation=allocation, source_gas_allocation=source_allocation)

    def reserve(self, *, identity="ab", principal=800, fee=20, deadline=200, now=100):
        return self.engine.reserve(identity, "lock-1", **self.reserve_arguments(
            identity=identity, principal=principal, fee=fee, deadline=deadline, now=now))

    def liquidation_terms(self):
        # Explicit test-only policy identifiers and bounded units, not invented
        # commercial defaults, a fee rate, actual funding, or a bridge provider.
        return {"gasPayer": "synthetic-EX", "gasBudget": "synthetic-ex-original-budget",
                "gasAsset": "ETH", "gasCapUnits": 7, "fundingMaxAge": 30,
                "penaltyPolicy": "explicit-fixture-penalty", "penaltyAsset": "ETH",
                "penaltyCapUnits": 5, "priorityPolicy": "explicit-fixture-priority",
                "conversionPolicy": "explicit-fixture-conversion"}

    def prepare(self, operation_id, obligation_id, *, kind, **kwargs):
        if kind == "debt-liquidation":
            terms = kwargs.setdefault("liquidation_terms", self.liquidation_terms())
            quote = self.verifier.facts[kwargs["liquidation_quote"]]
            authority_reference = digest({"operation": operation_id, "quote": digest(asdict(quote)),
                "terms": quote.reference, "collateralCap": quote.units})
            if "liquidation_authority" not in kwargs:
                previous = self.engine.operations.get(operation_id)
                if previous is not None and previous.authority_record is not None:
                    kwargs["liquidation_authority"] = ("synthetic:" + previous.authority_record["identity"]).encode()
                else:
                    kwargs["liquidation_authority"] = self.fact("liquidation-authority",
                        chain=560048, asset="ETH", location="hoodi-vault", reference=authority_reference,
                        units=quote.units, at=kwargs["now"])
        return self.engine.prepare(operation_id, obligation_id, kind=kind, **kwargs)

    def fund(self, op, *, at=200, **overrides):
        terms = op.liquidation_terms
        fields = dict(chain=560048, asset=terms["gasAsset"], account=terms["gasPayer"],
                      location=terms["gasBudget"], reference=op.commitment,
                      units=terms["gasCapUnits"], at=at)
        fields.update(overrides)
        raw = self.fact("liquidation-ex-funding", **fields)
        self.engine.observe_liquidation_funding(op.identity, raw, now=at)
        return raw

    def dispatch(self, operation_id, *, now=200):
        op = self.engine.operations[operation_id]
        if op.kind == "debt-liquidation" and op.status == "PREPARED" and op.funding_record is None:
            self.fund(op, at=now)
        return self.engine.mark_dispatched(operation_id, now=now)

    def normal_gas_fact(self, *, units=10, required=10, **overrides):
        item = self.engine.obligations["ab"]
        reference = digest({"obligation": "ab", "terms": item.consent,
                            "allocation": item.gas_allocation, "normalGas": item.normal_gas})
        fields = dict(asset="ETH", location=item.normal_gas["location"], reference=reference,
                      units=units, destination_units=required, at=200)
        fields.update(overrides)
        return self.fact("normal-gas-availability", **fields)

    def expenses(self, op, *, cost=2, penalty=3):
        terms = op.liquidation_terms
        cost_fact = self.fact("liquidation-cost", chain=560048, asset=terms["gasAsset"],
            account=terms["gasPayer"], location=terms["gasBudget"], reference=op.commitment,
            units=cost, at=200)
        reference = digest({"operation": op.commitment, "policy": terms["penaltyPolicy"],
                            "priority": terms["priorityPolicy"], "conversion": terms["conversionPolicy"]})
        penalty_fact = self.fact("liquidation-penalty", chain=560048, asset=terms["penaltyAsset"],
            location="hoodi-vault", reference=reference, units=penalty, at=200)
        self.engine.observe_liquidation_cost(op.identity, cost_fact, now=200)
        self.engine.observe_liquidation_penalty(op.identity, penalty_fact, now=200)
        return cost_fact, penalty_fact

    def register(self, *, at=150):
        raw = self.fact("registration-cut", at=at)
        self.engine.observe_registration("ab", raw, now=max(150, at))

    def credit(self, units, **fields):
        raw = self.fact("principal-allocation", units=units, **fields)
        self.engine.credit_escrow("ab", raw, now=150)
        return raw

    def quote(self, kind, target, *, asset="PYUSD", obligation="ab", collateral=50, terms=None):
        item = self.engine.obligations[obligation]
        binding = digest({"obligation": obligation, "kind": kind, "target": target, "asset": asset,
                          "chain": 11155111, "recipient": "sepolia-escrow", "consent": item.consent,
                          "liquidationTerms": self.liquidation_terms() if terms is None else terms})
        return self.fact("liquidation-quote", chain=560048, asset="ETH", location="hoodi-vault",
                         reference=binding, units=collateral, destination_units=target, at=200)

    def reach_deadline(self, *, registered=False):
        evidence = self.fact("deadline-registration", units=int(registered), at=200)
        return self.engine.deadline("ab", now=200, registration_evidence=evidence)

    def complete(self, op, *, units=None, chain=None):
        # Synthetic terminal aggregate of the original route, never its first fragment.
        self.dispatch(op.identity)
        raw = self.fact("terminal-operation-receipt", chain=op.chain if chain is None else chain,
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

    def test_capacity_excludes_upfront_eth_fee_without_loan_or_interest(self):
        # Preserves the historical capacity boundary with revised commercial terms.
        # exclude the ETH fee from PYUSD principal and collateral allowance.
        item = self.reserve(principal=1000, fee=20)
        self.assertEqual(item.due, 1000)
        self.assertEqual(item.settlement_fee_wei, 20)
        self.assertEqual(self.engine.locks["lock-1"].reserved, 1000)
        with self.assertRaises(DeferredRefused):
            self.reserve(identity="over-capacity", principal=1)
        self.assertEqual(self.engine.locks["lock-1"].reserved, 1000)

    def test_unregistered_deadline_rolls_back_not_waits_for_payment(self):
        self.reserve()
        self.credit(800)
        self.assertEqual(self.reach_deadline(), "ROLLBACK_REQUIRED")
        with self.assertRaises(DeferredRefused):
            self.prepare("pay", "ab", kind="seller-payment", now=200)
        self.register()
        self.assertTrue(self.engine.obligations["ab"].registered)
        self.assertFalse(self.engine.obligations["ab"].rollback)

    def test_registered_unpaid_debt_never_reopens_nft_rollback(self):
        self.reserve()
        self.register()
        self.assertEqual(self.engine.deadline("ab", now=200), "DEBT_LIQUIDATION_REQUIRED")
        self.assertFalse(self.engine.obligations["ab"].rollback)
        with self.assertRaises(DeferredRefused):
            self.prepare("reverse", "ab", kind="rollback", now=200)

    def test_early_payment_needs_registration_and_full_selected_principal(self):
        self.reserve()
        self.credit(800)
        with self.assertRaises(DeferredRefused):
            self.prepare("pay", "ab", kind="seller-payment", now=150)
        self.register()
        op = self.prepare("pay", "ab", kind="seller-payment", now=150)
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
        op = self.prepare("pay", "ab", kind="seller-payment", now=150)
        _, receipt = self.complete(op)
        self.engine.confirm("pay", receipt, now=200)
        self.assertEqual(self.engine.obligations["ab"].paid, 800)
        self.assertEqual(self.engine.locks["lock-1"].reserved, 0)

    def test_unknown_payment_cannot_be_sent_again_or_reallocated(self):
        self.reserve(); self.credit(800); self.register()
        op = self.prepare("pay", "ab", kind="seller-payment", now=150)
        self.dispatch(op.identity)
        with self.assertRaises(DeferredRefused):
            self.dispatch(op.identity)
        with self.assertRaises(DeferredRefused):
            self.prepare("pay-again", "ab", kind="seller-payment", now=150)
        with self.assertRaises(DeferredRefused):
            self.credit(1)

    def test_liquidation_requires_quote_and_destination_receipt_not_source_sale(self):
        self.reserve(); self.register(); self.credit(300)
        q = self.quote("debt-liquidation", 500)
        op = self.prepare("liquidate", "ab", kind="debt-liquidation", now=200, liquidation_quote=q)
        self.assertEqual(op.collateral_limit, 50)
        self.dispatch(op.identity)
        wrong = self.fact("terminal-operation-receipt", chain=560048, asset="ETH", account=op.recipient,
                          reference=op.commitment, units=500, at=200)
        with self.assertRaises(DeferredRefused):
            self.engine.confirm(op.identity, wrong, now=200)
        self.assertEqual(self.engine.obligations["ab"].escrow, 300)
        right = self.fact("terminal-operation-receipt", account=op.recipient, reference=op.commitment, units=500, at=200)
        self.engine.confirm(op.identity, right, now=200)
        self.assertEqual(self.engine.obligations["ab"].paid, 0)
        self.assertEqual(self.engine.obligations["ab"].escrow, 800)

    def test_partial_liquidation_proceeds_leave_visible_shortfall(self):
        self.reserve(); self.register()
        op = self.prepare("liquidate", "ab", kind="debt-liquidation", now=200,
                                 liquidation_quote=self.quote("debt-liquidation", 800))
        self.complete(op, units=300)
        self.assertEqual(self.engine.deadline("ab", now=200), "DEBT_LIQUIDATION_REQUIRED")
        self.assertFalse(self.engine.obligations["ab"].resolved)

    def test_rollback_gas_shortage_reuses_original_allocation_not_liquidation(self):
        # Retained coverage, revised rule: no new liquidation-to-gas operation.
        self.reserve(); self.credit(800); self.reach_deadline()
        with self.assertRaises(DeferredRefused):
            self.prepare("return", "ab", kind="rollback", now=200)
        short = self.normal_gas_fact(units=0, required=10, at=199)
        self.engine.observe_gas_requirement("ab", short, now=200)
        with self.assertRaises(DeferredRefused):
            self.prepare("gas", "ab", kind="gas-liquidation", now=200,
                         liquidation_quote=self.quote("gas-liquidation", 10, asset="ETH"))
        with self.assertRaises(DeferredRefused):
            self.prepare("return", "ab", kind="rollback", now=200)
        available = self.normal_gas_fact(units=10, required=10)
        self.engine.observe_gas_requirement("ab", available, now=200)
        rollback = self.prepare("return", "ab", kind="rollback", now=200)
        self.complete(rollback)
        self.assertTrue(self.engine.obligations["ab"].rollback_confirmed)
        self.assertEqual(self.engine.obligations["ab"].paid, 0)
        self.assertEqual(self.engine.obligations["ab"].settlement_fee_wei, 20)
        self.assertNotIn("gas", self.engine.operations)

    def test_unlock_requires_resolution_and_excess_refund(self):
        self.reserve(); self.credit(900); self.register()
        with self.assertRaises(DeferredRefused):
            self.prepare("unlock", "ab", kind="collateral-unlock", now=150)
        self.complete(self.prepare("pay", "ab", kind="seller-payment", now=150))
        with self.assertRaises(DeferredRefused):
            self.prepare("unlock", "ab", kind="collateral-unlock", now=200)
        self.complete(self.prepare("excess", "ab", kind="excess-refund", now=200))
        self.complete(self.prepare("unlock", "ab", kind="collateral-unlock", now=200))
        self.assertTrue(self.engine.locks["lock-1"].released)

    def test_restart_preserves_unknown_and_rejects_lost_reservation(self):
        self.reserve(); self.credit(800); self.register()
        op = self.prepare("pay", "ab", kind="seller-payment", now=150)
        self.dispatch(op.identity)
        copy = DeferredSettlement.restore(self.profile, self.verifier, self.engine.snapshot())
        self.assertEqual(copy.operations["pay"].status, "UNKNOWN")
        with self.assertRaises(DeferredRefused):
            copy.mark_dispatched("pay", now=200)
        broken = deepcopy(self.engine.snapshot()); broken["locks"]["lock-1"]["reserved"] = 0
        with self.assertRaises(DeferredRefused):
            DeferredSettlement.restore(self.profile, self.verifier, broken)

    def test_missing_local_registration_is_not_rollback_authority(self):
        self.reserve()
        self.assertEqual(self.engine.deadline("ab", now=200), "REGISTRATION_RECONCILIATION_REQUIRED")
        self.assertFalse(self.engine.obligations["ab"].rollback)
        with self.assertRaises(DeferredRefused):
            self.prepare("return", "ab", kind="rollback", now=200)
        self.register(at=150)
        self.assertEqual(self.engine.deadline("ab", now=200), "DEBT_LIQUIDATION_REQUIRED")

    def test_authoritative_registered_deadline_cut_preserves_prefix(self):
        self.reserve()
        self.assertEqual(self.reach_deadline(registered=True), "DEBT_LIQUIDATION_REQUIRED")
        self.assertTrue(self.engine.obligations["ab"].registered)
        self.assertFalse(self.engine.obligations["ab"].rollback)

    def test_prepared_unlock_blocks_new_borrowing_before_dispatch(self):
        self.reserve(); self.credit(800); self.register()
        self.complete(self.prepare("pay", "ab", kind="seller-payment", now=150))
        unlock = self.prepare("unlock", "ab", kind="collateral-unlock", now=200)
        self.assertTrue(self.engine.locks["lock-1"].release_pending)
        with self.assertRaises(DeferredRefused):
            self.reserve(identity="new-debt")
        self.complete(unlock)
        self.assertTrue(self.engine.locks["lock-1"].released)

    def test_partial_liquidations_reserve_source_caps_until_verified_consumption(self):
        self.reserve(principal=1000); self.register()
        first = self.prepare("sale-1", "ab", kind="debt-liquidation", now=200,
                                    liquidation_quote=self.quote("debt-liquidation", 1000))
        self.complete(first, units=200)
        second = self.prepare("sale-2", "ab", kind="debt-liquidation", now=200,
                                     liquidation_quote=self.quote("debt-liquidation", 800))
        self.complete(second, units=200)
        with self.assertRaises(DeferredRefused):
            self.prepare("sale-3", "ab", kind="debt-liquidation", now=200,
                                liquidation_quote=self.quote("debt-liquidation", 600))
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
        gas = self.normal_gas_fact(units=0, required=0)
        self.engine.observe_gas_requirement("ab", gas, now=200)
        op = self.prepare("return", "ab", kind="rollback", now=200)
        self.register(at=150)
        self.assertEqual(op.status, "FAILED")
        with self.assertRaises(DeferredRefused):
            self.dispatch(op.identity)
        self.assertFalse(self.engine.obligations["ab"].rollback)

    def test_prepared_unlock_retry_returns_same_operation_without_new_reservation(self):
        self.reserve(); self.credit(800); self.register()
        self.complete(self.prepare("pay", "ab", kind="seller-payment", now=150))
        first = self.prepare("unlock", "ab", kind="collateral-unlock", now=200)
        second = self.prepare("unlock", "ab", kind="collateral-unlock", now=201)
        self.assertIs(first, second)
        with self.assertRaises(DeferredRefused):
            self.prepare("unlock", "ab", kind="collateral-unlock", now=201, units=99)

    def test_liquidation_retry_excludes_own_reserved_cap_and_rejects_changed_quote(self):
        self.reserve(); self.register()
        quote = self.quote("debt-liquidation", 800)
        original = self.verifier.facts[quote]
        self.verifier.facts[quote] = replace(original, units=80)
        first = self.prepare("sale", "ab", kind="debt-liquidation", now=200, liquidation_quote=quote)
        self.assertIs(self.prepare("sale", "ab", kind="debt-liquidation", now=201,
                                         liquidation_quote=quote), first)
        with self.assertRaises(DeferredRefused):
            self.prepare("sale", "ab", kind="debt-liquidation", now=201,
                                liquidation_quote=self.quote("debt-liquidation", 800))

    def test_expired_lock_valuation_cannot_grant_new_trade_capacity(self):
        arguments = self.reserve_arguments(identity="late", deadline=500, now=300)
        with self.assertRaises(DeferredRefused):
            self.engine.reserve("late", "lock-1", **arguments)
        self.assertEqual(self.engine.locks["lock-1"].reserved, 0)

    def test_terminal_nonexecution_requires_exact_evidence_and_never_replays(self):
        self.reserve(); self.credit(800); self.register()
        op = self.prepare("pay", "ab", kind="seller-payment", now=150)
        self.dispatch(op.identity)
        with self.assertRaises(DeferredRefused):
            self.engine.confirm_nonexecution("pay", b'RPC-not-found', now=200)
        proof = self.fact("terminal-nonexecution", reference=op.commitment, account="A", units=0, at=200)
        self.engine.confirm_nonexecution("pay", proof, now=200)
        self.engine.confirm_nonexecution("pay", proof, now=200)
        self.assertEqual(op.status, "FAILED")
        self.assertEqual(self.engine.obligations["ab"].paid, 0)
        with self.assertRaises(DeferredRefused):
            self.dispatch("pay")
        replacement = self.prepare("pay-new", "ab", kind="seller-payment", now=200)
        self.assertEqual(replacement.status, "PREPARED")
        self.assertEqual(self.engine.obligations["ab"].escrow, 800)

    def test_multiple_obligations_share_only_unreserved_collateral_units(self):
        first = self.reserve(principal=800)
        second = self.reserve(identity="other", principal=200)
        self.assertEqual((first.collateral_remaining, second.collateral_remaining), (80, 20))
        self.assertEqual(self.engine.locks["lock-1"].reserved, 1000)
        with self.assertRaises(DeferredRefused):
            self.reserve(identity="over", principal=1)
        DeferredSettlement.restore(self.profile, self.verifier, self.engine.snapshot())

    def test_liquidation_cannot_spend_another_obligations_collateral(self):
        self.reserve(principal=800)
        self.reserve(identity="other", principal=200)
        self.register()
        quote = self.quote("debt-liquidation", 800)
        self.verifier.facts[quote] = replace(self.verifier.facts[quote], units=81)
        with self.assertRaises(DeferredRefused):
            self.prepare("over", "ab", kind="debt-liquidation", now=200, liquidation_quote=quote)
        self.assertEqual(self.engine.obligations["other"].collateral_remaining, 20)

    def test_lock_proof_is_bound_to_destination_profile_not_just_source_asset(self):
        raw = self.lock("bound-lock")
        other_profile = replace(self.profile, principal_asset="USDC")
        other = DeferredSettlement(other_profile, self.verifier)
        with self.assertRaises(DeferredRefused):
            other.admit_lock(raw, now=100)
        self.assertEqual(other.locks, {})

    def test_explicit_schedules_have_no_default_or_timezone_guess(self):
        from exchange.deferred_settlement import settlement_deadline
        self.assertEqual(settlement_deadline("T_PLUS_N", trade_at=100,
                         registration_deadline=1000000, delay_seconds=86400), 86500)
        self.assertEqual(settlement_deadline("BEFORE_REGISTRATION_72H", trade_at=100,
                         registration_deadline=1000000), 740800)
        with self.assertRaises(DeferredRefused):
            settlement_deadline("T_PLUS_N", trade_at=100, registration_deadline=1000000)
        with self.assertRaises(DeferredRefused):
            settlement_deadline("BEFORE_REGISTRATION_72H", trade_at=900000, registration_deadline=1000000)

    def test_original_refusal_may_require_rollback_before_deferred_due_date(self):
        self.reserve()
        proof = self.fact("original-rollback-authority", units=0, at=150)
        self.assertEqual(self.engine.observe_rollback_authority("ab", proof, now=150), "ROLLBACK_REQUIRED")
        self.assertTrue(self.engine.obligations["ab"].rollback)
        self.assertEqual(self.engine.obligations["ab"].paid, 0)

    def test_original_rollback_authority_cannot_reverse_registered_prefix(self):
        self.reserve(); self.register()
        proof = self.fact("original-rollback-authority", units=0, at=150)
        with self.assertRaises(DeferredRefused):
            self.engine.observe_rollback_authority("ab", proof, now=150)
        self.assertFalse(self.engine.obligations["ab"].rollback)

    def test_whole_lock_unlock_waits_for_every_obligations_excess_refund(self):
        self.reserve(principal=800); self.reserve(identity="other", principal=200)
        self.credit(900); self.register()
        self.complete(self.prepare("pay-ab", "ab", kind="seller-payment", now=150))
        self.engine.observe_registration("other", self.fact("registration-cut", reference="other", at=150), now=150)
        self.engine.credit_escrow("other", self.fact("principal-allocation", reference="other", units=200), now=150)
        self.complete(self.prepare("pay-other", "other", kind="seller-payment", now=150))
        with self.assertRaises(DeferredRefused):
            self.prepare("unlock-other", "other", kind="collateral-unlock", now=200)
        self.complete(self.prepare("refund-ab", "ab", kind="excess-refund", now=200))
        self.complete(self.prepare("unlock-other", "other", kind="collateral-unlock", now=200))
        self.assertTrue(self.engine.locks["lock-1"].released)

    def test_terminal_destination_failure_retains_source_cap_until_independent_fact(self):
        self.reserve(principal=1000); self.register()
        op = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                                 liquidation_quote=self.quote("debt-liquidation", 1000))
        self.dispatch("sale")
        terminal = self.fact("terminal-nonexecution", reference=op.commitment, account=op.recipient, at=200)
        self.engine.confirm_nonexecution("sale", terminal, now=200)
        quote = self.quote("debt-liquidation", 1000)
        self.verifier.facts[quote] = replace(self.verifier.facts[quote], units=60)
        with self.assertRaises(DeferredRefused):
            self.prepare("next", "ab", kind="debt-liquidation", now=200, liquidation_quote=quote)
        source = self.fact("liquidation-source", chain=560048, asset="ETH", location="hoodi-vault",
                           reference=op.commitment, units=20, at=200)
        self.engine.observe_liquidation_source("sale", source, now=200)
        self.prepare("next", "ab", kind="debt-liquidation", now=200, liquidation_quote=quote)
        self.assertEqual(self.engine.locks["lock-1"].units, 80)
        self.assertEqual(self.engine.obligations["ab"].paid, 0)
        self.assertEqual(self.engine.obligations["ab"].escrow, 0)
        DeferredSettlement.restore(self.profile, self.verifier, self.engine.snapshot())

    def test_policy_or_scope_change_cannot_reuse_source_proof(self):
        raw = self.lock("profile-bound")
        for other_profile in (replace(self.profile, policy="other-policy"),
                              replace(self.profile, checkpoint_scope="other-scope")):
            other = DeferredSettlement(other_profile, self.verifier)
            with self.assertRaises(DeferredRefused):
                other.admit_lock(raw, now=100)

    def test_rounding_cannot_allocate_more_collateral_than_exists(self):
        self.engine = DeferredSettlement(self.profile, self.verifier)
        self.lock(units=3)
        self.reserve(principal=333)
        self.reserve(identity="second", principal=333)
        self.reserve(identity="third", principal=333)
        with self.assertRaises(DeferredRefused):
            self.reserve(identity="rounding-over", principal=1)
        self.assertEqual(self.engine.locks["lock-1"].reserved, 999)

    def test_two_debts_interleave_payment_liquidation_and_restore_without_cross_spend(self):
        self.reserve(principal=800); self.reserve(identity="other", principal=200)
        self.credit(800); self.register()
        self.complete(self.prepare("pay-ab", "ab", kind="seller-payment", now=150))
        self.engine.observe_registration("other", self.fact("registration-cut", reference="other", at=150), now=150)
        quote = self.quote("debt-liquidation", 200, obligation="other", collateral=20)
        sale = self.prepare("sale-other", "other", kind="debt-liquidation", now=200, liquidation_quote=quote)
        self.complete(sale)
        self.assertEqual(self.engine.obligations["ab"].paid, 800)
        source = self.fact("liquidation-source", chain=560048, asset="ETH", location="hoodi-vault",
                           reference=sale.commitment, units=15, at=200)
        self.engine.observe_liquidation_source(sale.identity, source, now=200)
        self.expenses(sale)
        self.engine = DeferredSettlement.restore(self.profile, self.verifier, self.engine.snapshot())
        self.complete(self.prepare("pay-other", "other", kind="seller-payment", now=200))
        remainder = self.fact("collateral-remainder", chain=560048, asset="ETH", location="hoodi-vault",
                              reference="lock-1", units=85, at=200)
        self.engine.observe_collateral_remainder("lock-1", remainder, now=200)
        unlock = self.prepare("unlock", "other", kind="collateral-unlock", now=200)
        self.assertEqual(unlock.units, 85)
        self.complete(unlock)
        self.assertEqual(self.engine.locks["lock-1"].reserved, 0)

    def test_public_projection_excludes_wallet_and_private_binding_fields(self):
        self.reserve(); self.register()
        projection = self.engine.public_status("ab")
        self.assertEqual(projection["debtStatus"], "OUTSTANDING")
        self.assertTrue(projection["nftRollbackDetached"])
        import json
        encoded = json.dumps(projection)
        for private in ('"borrower"', '"seller"', '"consent"', '"quote"', 'hoodi-vault', 'sepolia-escrow', 'lock-1'):
            self.assertNotIn(private, encoded)

    def test_public_projection_does_not_call_pending_rollback_completed(self):
        self.reserve(); self.reach_deadline()
        self.assertEqual(self.engine.public_status("ab")["debtStatus"], "ROLLBACK_PENDING")
        gas = self.normal_gas_fact(units=0, required=0)
        self.engine.observe_gas_requirement("ab", gas, now=200)
        self.complete(self.prepare("return", "ab", kind="rollback", now=200))
        self.assertEqual(self.engine.public_status("ab")["debtStatus"], "CANCELLED_BY_ROLLBACK")

    def test_projection_separates_recorded_allocation_from_live_collateral(self):
        self.reserve(); self.credit(800); self.register()
        self.assertEqual(self.engine.public_status("ab")["collateralUnits"], 80)
        self.complete(self.prepare("pay", "ab", kind="seller-payment", now=150))
        settled = self.engine.public_status("ab")
        self.assertEqual(settled["collateralUnits"], 0)
        self.assertFalse(settled["collateralReconciliationPending"])
        self.assertEqual(settled["recordedCollateralAllocationUnits"], 80)
        self.assertEqual(settled["collateralLockState"], "LOCKED")
        self.complete(self.prepare("unlock", "ab", kind="collateral-unlock", now=200))
        released = self.engine.public_status("ab")
        self.assertEqual(released["collateralUnits"], 0)
        self.assertEqual(released["recordedCollateralAllocationUnits"], 80)
        self.assertEqual(released["collateralLockState"], "RELEASED")
        self.assertEqual(self.engine.obligations["ab"].collateral_remaining, 80)

    def test_settled_projection_does_not_hide_unknown_source_exposure(self):
        self.reserve(); self.register()
        sale = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                                   liquidation_quote=self.quote("debt-liquidation", 800))
        self.complete(sale)
        self.complete(self.prepare("pay", "ab", kind="seller-payment", now=200))
        projection = self.engine.public_status("ab")
        self.assertEqual(projection["collateralUnits"], 80)
        self.assertTrue(projection["sourceExposurePending"])
        self.assertTrue(projection["collateralReconciliationPending"])
        self.assertEqual(projection["collateralLockState"], "LOCKED")
        with self.assertRaises(DeferredRefused):
            self.prepare("unlock", "ab", kind="collateral-unlock", now=200)

    def test_upfront_fee_receipt_exact_binding_matrix_is_atomic(self):
        arguments = self.reserve_arguments()
        raw = arguments["fee_receipt"]
        original = self.verifier.facts[raw]
        mutations = ({"chain": 560048}, {"asset": "PYUSD"}, {"account": "C"},
                     {"location": "other-fee-receiver"}, {"reference": "wrong-terms"},
                     {"units": 19}, {"units": 21}, {"units": True},
                     {"profile_commitment": "0x" + "0" * 64})
        before = self.engine.snapshot()
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.verifier.facts[raw] = replace(original, **mutation)
                with self.assertRaises(DeferredRefused):
                    self.engine.reserve("ab", "lock-1", **arguments)
                self.assertEqual(self.engine.snapshot(), before)
        self.verifier.facts[raw] = original
        self.engine.reserve("ab", "lock-1", **arguments)
        self.assertEqual(self.engine.obligations["ab"].settlement_fee_wei, 20)

    def test_normal_allocation_exact_binding_and_sufficiency_matrix(self):
        arguments = self.reserve_arguments()
        raw = arguments["gas_allocation"]
        original = self.verifier.facts[raw]
        before = self.engine.snapshot()
        for mutation in ({"chain": 560048}, {"asset": "PYUSD"}, {"account": "A"},
                         {"location": "new-freeze"}, {"reference": "another-receipt-or-terms"},
                         {"units": 0}, {"units": 9}, {"units": 11}, {"units": True}):
            with self.subTest(mutation=mutation):
                self.verifier.facts[raw] = replace(original, **mutation)
                with self.assertRaises(DeferredRefused):
                    self.engine.reserve("ab", "lock-1", **arguments)
                self.assertEqual(self.engine.snapshot(), before)
        self.verifier.facts[raw] = original
        self.engine.reserve("ab", "lock-1", **arguments)
        self.assertEqual(self.engine.obligations["ab"].gas_received, 0)

    def test_missing_unverified_or_underfunded_normal_fee_never_admits(self):
        for evidence in ("fee_receipt", "gas_allocation", "source_gas_allocation"):
            arguments = self.reserve_arguments()
            arguments[evidence] = b"not-authenticated"
            with self.subTest(evidence=evidence), self.assertRaises(DeferredRefused):
                self.engine.reserve("ab", "lock-1", **arguments)
        for fee in (0, 9, True):
            with self.subTest(fee=fee), self.assertRaises(DeferredRefused):
                self.reserve(fee=fee)
        self.assertEqual(self.engine.obligations, {})
        self.assertEqual(self.engine.locks["lock-1"].reserved, 0)

    def test_fee_and_normal_allocation_replay_cannot_fund_another_obligation(self):
        first = self.reserve(principal=400)
        for key, identity in (("fee_receipt", first.fee_receipt),
                              ("gas_allocation", first.gas_allocation),
                              ("source_gas_allocation", first.source_gas_allocation)):
            arguments = self.reserve_arguments(identity="second", principal=400)
            arguments[key] = ("synthetic:" + identity).encode()
            before = self.engine.snapshot()
            with self.subTest(key=key), self.assertRaises(DeferredRefused):
                self.engine.reserve("second", "lock-1", **arguments)
            self.assertEqual(self.engine.snapshot(), before)
        self.assertEqual(self.engine.locks["lock-1"].reserved, 400)

    def test_original_normal_budget_cannot_be_reallocated_with_fresh_fact_ids(self):
        first = self.reserve(principal=400)
        normal = self.normal_gas("second")
        normal["budget"] = first.normal_gas["budget"]
        arguments = self.reserve_arguments(identity="second", principal=400, normal_gas=normal)
        before = self.engine.snapshot()
        with self.assertRaises(DeferredRefused):
            self.engine.reserve("second", "lock-1", **arguments)
        self.assertEqual(self.engine.snapshot(), before)

    def test_seller_and_borrower_authority_bind_principal_not_eth_fee(self):
        for key in ("seller_consent", "borrower_authority"):
            arguments = self.reserve_arguments()
            raw = arguments[key]
            self.verifier.facts[raw] = replace(self.verifier.facts[raw], units=820)
            with self.subTest(key=key), self.assertRaises(DeferredRefused):
                self.engine.reserve("ab", "lock-1", **arguments)
        self.assertEqual(self.engine.obligations, {})
        self.reserve(); self.register(); self.credit(800)
        payment = self.prepare("pay", "ab", kind="seller-payment", now=150)
        self.assertEqual((payment.units, payment.asset, payment.chain), (800, "PYUSD", 11155111))
        self.complete(payment)
        item = self.engine.obligations["ab"]
        self.assertEqual((item.paid, item.due, item.settlement_fee_wei), (800, 0, 20))

    def test_normal_terms_changes_invalidate_original_receipts_and_authority(self):
        for key, value in (("budget", "other-budget"), ("quote", "other-quote"),
                           ("scope", "other-scope"), ("grant", "other-grant"),
                           ("location", "other-journal"), ("capWei", 9), ("maxAgeSeconds", 99),
                           ("payer", "other-payer")):
            arguments = self.reserve_arguments()
            arguments["normal_gas"][key] = value
            with self.subTest(key=key), self.assertRaises(DeferredRefused):
                self.engine.reserve("ab", "lock-1", **arguments)
        self.assertEqual(self.engine.obligations, {})

    def test_restore_rejects_boolean_amounts_in_new_funding_fields(self):
        self.reserve()
        original = self.engine.snapshot()
        for section, key in ((None, "settlement_fee_wei"), ("normal_gas", "capWei"),
                             ("normal_gas", "maxAgeSeconds"), ("source_normal_gas", "capWei"),
                             ("source_normal_gas", "maxAgeSeconds"), ("source_gas_record", "units"),
                             ("fee_receipt_record", "units"), ("gas_allocation_record", "units"),
                             ("fee_receipt_record", "principal_value"),
                             ("gas_allocation_record", "destination_units")):
            broken = deepcopy(original)
            item = broken["obligations"]["ab"]
            target = item if section is None else item[section]
            target[key] = True
            if section in ("fee_receipt_record", "gas_allocation_record", "source_gas_record"):
                broken["evidence"][target["identity"]] = digest(target)
            with self.subTest(section=section, key=key), self.assertRaises(DeferredRefused):
                DeferredSettlement.restore(self.profile, self.verifier, broken)
        self.assertEqual(self.engine.snapshot(), original)

    def test_restore_rejects_missing_or_rebound_upfront_fee_evidence(self):
        self.reserve()
        original = self.engine.snapshot()
        for section in ("fee_receipt_record", "gas_allocation_record", "source_gas_record"):
            for key, value in (("chain", 11155111 if section == "source_gas_record" else 560048),
                               ("asset", "PYUSD"),
                               ("account", "C"), ("location", "other"),
                               ("reference", "other-terms")):
                broken = deepcopy(original)
                target = broken["obligations"]["ab"][section]
                target[key] = value
                broken["evidence"][target["identity"]] = digest(target)
                with self.subTest(section=section, key=key), self.assertRaises(DeferredRefused):
                    DeferredSettlement.restore(self.profile, self.verifier, broken)
            broken = deepcopy(original)
            broken["obligations"]["ab"][section] = None
            with self.assertRaises(DeferredRefused):
                DeferredSettlement.restore(self.profile, self.verifier, broken)
            broken = deepcopy(original)
            identity = broken["obligations"]["ab"][section]["identity"]
            del broken["evidence"][identity]
            with self.assertRaises(DeferredRefused):
                DeferredSettlement.restore(self.profile, self.verifier, broken)

    def test_schema_two_separates_fee_and_preserves_private_originals(self):
        self.reserve(); self.register()
        snapshot = self.engine.snapshot()
        self.assertEqual(snapshot["schema"], "8415ex-deferred/2")
        restored = DeferredSettlement.restore(self.profile, self.verifier, snapshot)
        self.assertEqual(restored.snapshot(), snapshot)
        projection = restored.public_status("ab")
        self.assertEqual(projection["schema"], "8415ex-deferred-status/2")
        self.assertEqual((projection["principalUnits"], projection["shortfallUnits"]), (800, 800))
        self.assertEqual((projection["settlementFeeWei"], projection["settlementFeeAsset"],
                          projection["settlementFeeChain"], projection["normalGasCapWei"]),
                         (20, "ETH", 11155111, 10))
        self.assertEqual((projection["sourceNormalGasCapWei"], projection["sourceNormalGasChain"]), (7, 560048))
        self.assertNotIn("feeUnits", projection)
        import json
        rendered = json.dumps(projection)
        for secret in ("ex-fee-receiver", "normal-budget-ab", "normal-quote-ab",
                       "normal-grant-ab", "original-normal-gas-journal", "fee_receipt_record",
                       "source-normal-budget-ab", "synthetic-source-treasury", "source_gas_record"):
            self.assertNotIn(secret, rendered)

    def test_schema_one_is_held_without_silent_fee_migration(self):
        self.reserve()
        legacy = self.engine.snapshot()
        legacy["schema"] = "8415ex-deferred/1"
        before = deepcopy(legacy)
        with self.assertRaisesRegex(DeferredRefused, "LEGACY_FEE_ACCOUNTING_RECONCILIATION_REQUIRED"):
            DeferredSettlement.restore(self.profile, self.verifier, legacy)
        self.assertEqual(legacy, before)
        self.assertEqual(self.engine.operations, {})

    def test_rollback_reuses_only_original_normal_budget_and_cap(self):
        self.reserve(); self.reach_deadline()
        before = self.engine.snapshot()
        for mutation in ({"chain": 560048}, {"asset": "PYUSD"}, {"account": "C"},
                         {"location": "fresh-freeze"}, {"reference": "another-original-budget"},
                         {"units": 11}, {"destination_units": 11}, {"units": True}):
            raw = self.normal_gas_fact(**mutation)
            with self.subTest(mutation=mutation), self.assertRaises(DeferredRefused):
                self.engine.observe_gas_requirement("ab", raw, now=200)
            self.assertEqual(self.engine.snapshot(), before)
        raw = self.normal_gas_fact()
        self.engine.observe_gas_requirement("ab", raw, now=200)
        self.engine.observe_gas_requirement("ab", raw, now=200)
        self.complete(self.prepare("return", "ab", kind="rollback", now=200))
        self.assertEqual(self.engine.obligations["ab"].gas_received, 10)
        self.assertEqual(self.engine.obligations["ab"].settlement_fee_wei, 20)

    def test_liquidation_terms_and_original_authority_are_not_optional(self):
        self.reserve(); self.register()
        quote = self.quote("debt-liquidation", 800)
        for key in self.liquidation_terms():
            terms = self.liquidation_terms()
            del terms[key]
            with self.subTest(missing=key), self.assertRaises(DeferredRefused):
                self.engine.prepare("sale", "ab", kind="debt-liquidation", now=200,
                    liquidation_quote=quote, liquidation_terms=terms, liquidation_authority=b"absent")
        with self.assertRaises(DeferredRefused):
            self.engine.prepare("sale", "ab", kind="debt-liquidation", now=200,
                liquidation_quote=quote, liquidation_terms=self.liquidation_terms(),
                liquidation_authority=b"not-original-authority")
        self.assertEqual(self.engine.operations, {})

    def test_liquidation_authority_binds_exact_quote_terms_and_source_cap(self):
        self.reserve(); self.register()
        quote = self.quote("debt-liquidation", 800)
        quote_fact = self.verifier.facts[quote]
        reference = digest({"operation": "sale", "quote": digest(asdict(quote_fact)),
                            "terms": quote_fact.reference, "collateralCap": quote_fact.units})
        authority = self.fact("liquidation-authority", chain=560048, asset="ETH",
            location="hoodi-vault", reference=reference, units=50, at=200)
        original = self.verifier.facts[authority]
        before = self.engine.snapshot()
        for mutation in ({"chain": 11155111}, {"asset": "PYUSD"}, {"account": "A"},
                         {"location": "other-vault"}, {"reference": "other-commercial-terms"},
                         {"units": 51}, {"units": True}):
            self.verifier.facts[authority] = replace(original, **mutation)
            with self.subTest(mutation=mutation), self.assertRaises(DeferredRefused):
                self.engine.prepare("sale", "ab", kind="debt-liquidation", now=200,
                    liquidation_quote=quote, liquidation_terms=self.liquidation_terms(),
                    liquidation_authority=authority)
            self.assertEqual(self.engine.snapshot(), before)
        self.verifier.facts[authority] = original
        self.engine.prepare("sale", "ab", kind="debt-liquidation", now=200,
            liquidation_quote=quote, liquidation_terms=self.liquidation_terms(), liquidation_authority=authority)

    def test_liquidation_requires_ex_funding_before_dispatch_not_b_eth_or_proceeds(self):
        self.reserve(); self.register()
        sale = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                            liquidation_quote=self.quote("debt-liquidation", 800))
        before = self.engine.snapshot()
        with self.assertRaises(DeferredRefused):
            self.engine.mark_dispatched("sale", now=200)
        self.assertEqual(self.engine.snapshot(), before)
        self.assertEqual(self.engine.obligations["ab"].escrow, 0)
        self.fund(sale)
        # No new buyer balance, ETH payment, liquidation proceeds or bridge fact
        # is supplied. Original EX funding alone makes this issued operation safe.
        self.engine.mark_dispatched("sale", now=200)
        self.assertEqual(sale.status, "UNKNOWN")
        self.assertEqual(self.engine.obligations["ab"].settlement_fee_wei, 20)
        self.assertEqual(self.engine.obligations["ab"].due, 800)

    def test_ex_funding_exact_scope_amount_and_freshness_are_required(self):
        self.reserve(); self.register()
        sale = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                            liquidation_quote=self.quote("debt-liquidation", 800))
        before = self.engine.snapshot()
        for mutation in ({"chain": 11155111}, {"asset": "PYUSD"}, {"account": "B"},
                         {"location": "buyer-normal-budget"}, {"reference": "other-operation"},
                         {"units": 6}, {"units": 8}, {"units": True}):
            with self.subTest(mutation=mutation), self.assertRaises(DeferredRefused):
                self.fund(sale, **mutation)
            self.assertEqual(self.engine.snapshot(), before)
        funding = self.fund(sale)
        self.engine.observe_liquidation_funding("sale", funding, now=200)
        with self.assertRaises(DeferredRefused):
            self.engine.mark_dispatched("sale", now=231)
        self.assertEqual(sale.status, "PREPARED")
        self.engine.mark_dispatched("sale", now=230)
        self.assertEqual(sale.status, "UNKNOWN")

    def test_later_same_binding_ex_funding_refreshes_only_prepared_claim(self):
        self.reserve(); self.register()
        sale = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                            liquidation_quote=self.quote("debt-liquidation", 800))
        old = self.fund(sale)
        before = self.engine.snapshot()
        with self.assertRaises(DeferredRefused):
            self.fund(sale, at=200)
        with self.assertRaises(DeferredRefused):
            self.fund(sale, at=199)
        with self.assertRaises(DeferredRefused):
            self.fund(sale, at=201, location="different-ex-budget")
        self.assertEqual(self.engine.snapshot(), before)
        fresh = self.fund(sale, at=201)
        self.assertEqual(sale.funding_record, asdict(self.verifier.facts[fresh]))
        self.engine.observe_liquidation_funding("sale", fresh, now=201)
        after = self.engine.snapshot()
        with self.assertRaises(DeferredRefused):
            self.engine.observe_liquidation_funding("sale", old, now=201)
        self.assertEqual(self.engine.snapshot(), after)
        self.engine.mark_dispatched("sale", now=231)
        with self.assertRaises(DeferredRefused):
            self.fund(sale, at=232)
        self.assertEqual(sale.status, "UNKNOWN")

    def test_penalty_is_part_of_gross_source_consumption_not_second_debit(self):
        self.reserve(); self.register()
        sale = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                            liquidation_quote=self.quote("debt-liquidation", 800))
        self.complete(sale)
        source = self.fact("liquidation-source", chain=560048, asset="ETH", location="hoodi-vault",
                           reference=sale.commitment, units=20, at=200)
        self.engine.observe_liquidation_source("sale", source, now=200)
        before = (self.engine.locks["lock-1"].units, self.engine.obligations["ab"].collateral_remaining)
        cost, penalty = self.expenses(sale)
        self.engine.observe_liquidation_cost("sale", cost, now=200)
        self.engine.observe_liquidation_penalty("sale", penalty, now=200)
        self.engine.observe_liquidation_source("sale", source, now=200)
        self.assertEqual(before, (80, 60))
        self.assertEqual((self.engine.locks["lock-1"].units,
                          self.engine.obligations["ab"].collateral_remaining), before)
        self.assertEqual((self.engine.obligations["ab"].due, self.engine.obligations["ab"].escrow), (800, 800))
        self.assertEqual((sale.cost_record["units"], sale.penalty_record["units"]), (2, 3))
        self.complete(self.prepare("pay", "ab", kind="seller-payment", now=200))
        restored = DeferredSettlement.restore(self.profile, self.verifier, self.engine.snapshot())
        self.assertEqual(restored.obligations["ab"].due, 0)
        self.assertEqual(restored.obligations["ab"].paid, 800)
        self.assertEqual(restored.locks["lock-1"].units, 80)

    def test_penalty_before_source_cannot_exceed_later_gross_source_consumption(self):
        self.reserve(); self.register()
        sale = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                            liquidation_quote=self.quote("debt-liquidation", 800))
        self.dispatch("sale")
        self.expenses(sale, penalty=3)
        before = self.engine.snapshot()
        source = self.fact("liquidation-source", chain=560048, asset="ETH", location="hoodi-vault",
                           reference=sale.commitment, units=2, at=200)
        with self.assertRaises(DeferredRefused):
            self.engine.observe_liquidation_source("sale", source, now=200)
        self.assertEqual(self.engine.snapshot(), before)

    def test_unlock_waits_for_source_cost_and_penalty_reconciliation(self):
        self.reserve(); self.register()
        sale = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                            liquidation_quote=self.quote("debt-liquidation", 800))
        self.complete(sale)
        self.complete(self.prepare("pay", "ab", kind="seller-payment", now=200))
        source = self.fact("liquidation-source", chain=560048, asset="ETH", location="hoodi-vault",
                           reference=sale.commitment, units=20, at=200)
        remainder = self.fact("collateral-remainder", chain=560048, asset="ETH", location="hoodi-vault",
                              reference="lock-1", units=80, at=200)
        with self.assertRaises(DeferredRefused):
            self.engine.observe_collateral_remainder("lock-1", remainder, now=200)
        self.engine.observe_liquidation_source("sale", source, now=200)
        projection = self.engine.public_status("ab")
        self.assertFalse(projection["sourceExposurePending"])
        self.assertTrue(projection["collateralReconciliationPending"])
        self.assertEqual(projection["collateralUnits"], 60)
        with self.assertRaises(DeferredRefused):
            self.engine.observe_collateral_remainder("lock-1", remainder, now=200)
        cost, penalty = self.expenses(sale)
        self.engine.observe_collateral_remainder("lock-1", remainder, now=200)
        unlock = self.prepare("unlock", "ab", kind="collateral-unlock", now=200)
        self.assertEqual(unlock.units, 80)
        self.complete(unlock)
        self.assertTrue(self.engine.locks["lock-1"].released)

    def test_restore_holds_issued_liquidation_without_original_ex_funding(self):
        self.reserve(); self.register()
        sale = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                            liquidation_quote=self.quote("debt-liquidation", 800))
        self.dispatch("sale")
        original = self.engine.snapshot()
        broken = deepcopy(original)
        broken["operations"]["sale"]["funding_record"] = None
        with self.assertRaises(DeferredRefused):
            DeferredSettlement.restore(self.profile, self.verifier, broken)
        for record in ("quote_record", "authority_record", "funding_record"):
            broken = deepcopy(original)
            raw = broken["operations"]["sale"][record]
            raw["units"] = True
            broken["evidence"][raw["identity"]] = digest(raw)
            with self.subTest(record=record), self.assertRaises(DeferredRefused):
                DeferredSettlement.restore(self.profile, self.verifier, broken)
        restored = DeferredSettlement.restore(self.profile, self.verifier, original)
        self.assertEqual(restored.operations["sale"].status, "UNKNOWN")
        with self.assertRaises(DeferredRefused):
            restored.mark_dispatched("sale", now=200)

    def test_ex_cost_and_collateral_penalty_bind_separate_evidence_and_caps(self):
        self.reserve(); self.register()
        sale = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                            liquidation_quote=self.quote("debt-liquidation", 800))
        self.dispatch("sale")
        terms = sale.liquidation_terms
        cost = self.fact("liquidation-cost", chain=560048, asset="ETH",
            account=terms["gasPayer"], location=terms["gasBudget"], reference=sale.commitment,
            units=2, at=200)
        penalty_reference = digest({"operation": sale.commitment, "policy": terms["penaltyPolicy"],
            "priority": terms["priorityPolicy"], "conversion": terms["conversionPolicy"]})
        penalty = self.fact("liquidation-penalty", chain=560048, asset="ETH", location="hoodi-vault",
                            reference=penalty_reference, units=3, at=200)
        before = self.engine.snapshot()
        for raw, observer, mutations in (
            (cost, self.engine.observe_liquidation_cost,
             ({"chain": 11155111}, {"asset": "PYUSD"}, {"account": "B"},
              {"location": "normal-budget-ab"}, {"reference": "other-operation"},
              {"units": 8}, {"units": True})),
            (penalty, self.engine.observe_liquidation_penalty,
             ({"chain": 11155111}, {"asset": "PYUSD"}, {"account": "synthetic-EX"},
              {"location": "other-vault"}, {"reference": "other-penalty-policy"},
              {"units": 6}, {"units": True})),
        ):
            original = self.verifier.facts[raw]
            for mutation in mutations:
                self.verifier.facts[raw] = replace(original, **mutation)
                with self.subTest(kind=original.kind, mutation=mutation), self.assertRaises(DeferredRefused):
                    observer("sale", raw, now=200)
                self.assertEqual(self.engine.snapshot(), before)
            self.verifier.facts[raw] = original
        self.engine.observe_liquidation_cost("sale", cost, now=200)
        self.assertEqual(self.engine.obligations["ab"].due, 800)
        self.assertIsNone(sale.penalty_record)
        self.engine.observe_liquidation_penalty("sale", penalty, now=200)
        self.assertEqual(self.engine.obligations["ab"].due, 800)
        self.assertEqual(self.engine.locks["lock-1"].units, 100)
        restored = DeferredSettlement.restore(self.profile, self.verifier, self.engine.snapshot())
        self.assertEqual(restored.operations["sale"].cost_record["units"], 2)
        self.assertEqual(restored.operations["sale"].penalty_record["units"], 3)

    def test_liquidation_cost_alone_never_counts_as_penalty_or_seller_payment(self):
        self.reserve(); self.register()
        sale = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                            liquidation_quote=self.quote("debt-liquidation", 800))
        self.complete(sale)
        source = self.fact("liquidation-source", chain=560048, asset="ETH", location="hoodi-vault",
                           reference=sale.commitment, units=20, at=200)
        self.engine.observe_liquidation_source("sale", source, now=200)
        terms = sale.liquidation_terms
        cost = self.fact("liquidation-cost", chain=560048, asset="ETH", account=terms["gasPayer"],
                        location=terms["gasBudget"], reference=sale.commitment, units=2, at=200)
        self.engine.observe_liquidation_cost("sale", cost, now=200)
        self.complete(self.prepare("pay", "ab", kind="seller-payment", now=200))
        self.assertEqual(self.engine.obligations["ab"].paid, 800)
        self.assertEqual(self.engine.obligations["ab"].due, 0)
        self.assertIsNone(sale.penalty_record)
        self.assertTrue(self.engine.public_status("ab")["collateralReconciliationPending"])
        remainder = self.fact("collateral-remainder", chain=560048, asset="ETH", location="hoodi-vault",
                              reference="lock-1", units=80, at=200)
        with self.assertRaises(DeferredRefused):
            self.engine.observe_collateral_remainder("lock-1", remainder, now=200)
        with self.assertRaises(DeferredRefused):
            self.prepare("unlock", "ab", kind="collateral-unlock", now=200)

    def test_restore_rejects_tampered_liquidation_cost_and_penalty_amount_types(self):
        self.reserve(); self.register()
        sale = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                            liquidation_quote=self.quote("debt-liquidation", 800))
        self.dispatch("sale"); self.expenses(sale)
        original = self.engine.snapshot()
        for record in ("cost_record", "penalty_record"):
            for units in (True, -1, 2 ** 256):
                broken = deepcopy(original)
                raw = broken["operations"]["sale"][record]
                raw["units"] = units
                broken["evidence"][raw["identity"]] = digest(raw)
                with self.subTest(record=record, units=units), self.assertRaises(DeferredRefused):
                    DeferredSettlement.restore(self.profile, self.verifier, broken)
        self.assertEqual(self.engine.snapshot(), original)

    def test_verified_net_proceeds_above_target_preserve_source_cap_and_refund_excess(self):
        self.reserve(); self.register(); self.credit(300)
        sale = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                            liquidation_quote=self.quote("debt-liquidation", 500))
        self.assertEqual((sale.units, sale.collateral_limit), (500, 50))
        _, receipt = self.complete(sale, units=550)
        self.engine.confirm("sale", receipt, now=200)
        self.assertEqual(self.engine.obligations["ab"].escrow, 850)
        self.assertEqual(self.engine.obligations["ab"].due, 800)
        over_cap = self.fact("liquidation-source", chain=560048, asset="ETH", location="hoodi-vault",
                             reference=sale.commitment, units=51, at=200)
        before = self.engine.snapshot()
        with self.assertRaises(DeferredRefused):
            self.engine.observe_liquidation_source("sale", over_cap, now=200)
        self.assertEqual(self.engine.snapshot(), before)
        source = self.fact("liquidation-source", chain=560048, asset="ETH", location="hoodi-vault",
                           reference=sale.commitment, units=40, at=200)
        self.engine.observe_liquidation_source("sale", source, now=200)
        self.expenses(sale)
        payment = self.prepare("pay", "ab", kind="seller-payment", now=200)
        self.assertEqual(payment.units, 800)
        self.complete(payment)
        self.assertEqual((self.engine.obligations["ab"].due, self.engine.obligations["ab"].escrow), (0, 50))
        with self.assertRaises(DeferredRefused):
            self.prepare("unlock", "ab", kind="collateral-unlock", now=200)
        refund = self.prepare("excess", "ab", kind="excess-refund", now=200)
        self.assertEqual((refund.units, refund.asset, refund.chain, refund.recipient), (50, "PYUSD", 11155111, "B"))
        self.complete(refund)
        remainder = self.fact("collateral-remainder", chain=560048, asset="ETH", location="hoodi-vault",
                              reference="lock-1", units=60, at=200)
        self.engine.observe_collateral_remainder("lock-1", remainder, now=200)
        self.complete(self.prepare("unlock", "ab", kind="collateral-unlock", now=200))
        restored = DeferredSettlement.restore(self.profile, self.verifier, self.engine.snapshot())
        self.assertEqual(restored.obligations["ab"].paid, 800)
        self.assertEqual(restored.obligations["ab"].escrow, 0)
        self.assertEqual(restored.operations["sale"].collateral_limit, 50)
        self.assertEqual(restored.operations["sale"].collateral_spent, 40)

    def test_exact_five_fact_reserve_retry_is_idempotent_even_after_deadline(self):
        arguments = self.reserve_arguments()
        first = self.engine.reserve("ab", "lock-1", **arguments)
        before = self.engine.snapshot()
        self.assertIs(self.engine.reserve("ab", "lock-1", **arguments), first)
        late = dict(arguments, now=300)
        self.assertIs(self.engine.reserve("ab", "lock-1", **late), first)
        self.assertEqual(self.engine.snapshot(), before)
        self.assertEqual(self.engine.locks["lock-1"].reserved, 800)
        self.assertEqual(len(self.engine.obligations), 1)
        restored = DeferredSettlement.restore(self.profile, self.verifier, before)
        restored.reserve("ab", "lock-1", **late)
        self.assertEqual(restored.snapshot(), before)

    def test_reserve_retry_rejects_changed_fact_identity_or_terms(self):
        arguments = self.reserve_arguments()
        self.engine.reserve("ab", "lock-1", **arguments)
        before = self.engine.snapshot()
        for key in ("seller_consent", "borrower_authority", "fee_receipt", "gas_allocation",
                    "source_gas_allocation"):
            changed = dict(arguments)
            original = self.verifier.facts[changed[key]]
            changed[key] = self.verifier.encode(replace(original, identity="replacement-" + key))
            with self.subTest(key=key), self.assertRaises(DeferredRefused):
                self.engine.reserve("ab", "lock-1", **changed)
            self.assertEqual(self.engine.snapshot(), before)
        for changed in (dict(arguments, principal=801), dict(arguments, settlement_fee_wei=21),
                        dict(arguments, deadline=201)):
            with self.assertRaises(DeferredRefused):
                self.engine.reserve("ab", "lock-1", **changed)
            self.assertEqual(self.engine.snapshot(), before)

    def test_normal_observation_validity_policy_is_explicit_and_not_boolean(self):
        for value in (None, 0, True):
            normal = self.normal_gas()
            if value is None:
                del normal["maxAgeSeconds"]
            else:
                normal["maxAgeSeconds"] = value
            arguments = self.reserve_arguments(normal_gas=normal)
            before = self.engine.snapshot()
            with self.subTest(value=value), self.assertRaises(DeferredRefused):
                self.engine.reserve("ab", "lock-1", **arguments)
            self.assertEqual(self.engine.snapshot(), before)

    def test_normal_gas_observation_rejects_stale_and_future_facts(self):
        self.reserve(); self.reach_deadline()
        before = self.engine.snapshot()
        for observed_at in (99, 201):
            raw = self.normal_gas_fact(at=observed_at)
            with self.subTest(observed_at=observed_at), self.assertRaises(DeferredRefused):
                self.engine.observe_gas_requirement("ab", raw, now=200)
            self.assertEqual(self.engine.snapshot(), before)
        edge = self.normal_gas_fact(at=100)
        self.engine.observe_gas_requirement("ab", edge, now=200)
        item = self.engine.obligations["ab"]
        self.assertEqual(item.normal_gas_availability, asdict(self.verifier.facts[edge]))
        self.assertTrue(item.gas_assessed)
        self.assertEqual((item.gas_received, item.gas_required), (10, 10))

    def test_normal_gas_observation_refresh_rejects_out_of_order_and_old_replay(self):
        self.reserve(); self.reach_deadline()
        old = self.normal_gas_fact(units=0, required=10, at=199)
        self.engine.observe_gas_requirement("ab", old, now=200)
        current = self.normal_gas_fact(units=10, required=10, at=200)
        self.engine.observe_gas_requirement("ab", current, now=200)
        self.engine.observe_gas_requirement("ab", current, now=200)
        before = self.engine.snapshot()
        for raw in (old, self.normal_gas_fact(units=0, at=199), self.normal_gas_fact(units=0, at=200)):
            with self.assertRaises(DeferredRefused):
                self.engine.observe_gas_requirement("ab", raw, now=200)
            self.assertEqual(self.engine.snapshot(), before)
        restored = DeferredSettlement.restore(self.profile, self.verifier, before)
        self.assertEqual(restored.obligations["ab"].normal_gas_availability,
                         asdict(self.verifier.facts[current]))

    def test_rollback_dispatch_rechecks_normal_observation_expiry(self):
        self.reserve(); self.reach_deadline()
        raw = self.normal_gas_fact(at=200)
        self.engine.observe_gas_requirement("ab", raw, now=200)
        self.prepare("return", "ab", kind="rollback", now=200)
        before = self.engine.snapshot()
        with self.assertRaises(DeferredRefused):
            self.engine.mark_dispatched("return", now=301)
        self.assertEqual(self.engine.snapshot(), before)
        boundary = DeferredSettlement.restore(self.profile, self.verifier, before)
        boundary.mark_dispatched("return", now=300)
        self.assertEqual(boundary.operations["return"].status, "UNKNOWN")

    def test_restore_cannot_fabricate_normal_gas_assessment_without_original_fact(self):
        self.reserve(); self.reach_deadline()
        original = self.engine.snapshot()
        for changes in ({"gas_assessed": True}, {"gas_received": 1}, {"gas_required": 1},
                        {"gas_assessed": True, "gas_received": 10, "gas_required": 10}):
            broken = deepcopy(original)
            broken["obligations"]["ab"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(DeferredRefused):
                DeferredSettlement.restore(self.profile, self.verifier, broken)
        self.assertEqual(self.engine.snapshot(), original)

    def test_restore_normal_gas_observation_binds_evidence_metrics_cap_and_scope(self):
        self.reserve(); self.reach_deadline()
        raw = self.normal_gas_fact()
        self.engine.observe_gas_requirement("ab", raw, now=200)
        original = self.engine.snapshot()
        for mutation in ({"chain": 560048}, {"asset": "PYUSD"}, {"account": "A"},
                         {"location": "new-budget"}, {"reference": "wrong-terms"},
                         {"units": 9}, {"destination_units": 9}, {"units": True},
                         {"destination_units": True}):
            broken = deepcopy(original)
            fact = broken["obligations"]["ab"]["normal_gas_availability"]
            fact.update(mutation)
            broken["evidence"][fact["identity"]] = digest(fact)
            with self.subTest(mutation=mutation), self.assertRaises(DeferredRefused):
                DeferredSettlement.restore(self.profile, self.verifier, broken)
        for metric, field in (("gas_received", "units"), ("gas_required", "destination_units")):
            broken = deepcopy(original)
            item = broken["obligations"]["ab"]
            item[metric] = 11
            item["normal_gas_availability"][field] = 11
            fact = item["normal_gas_availability"]
            broken["evidence"][fact["identity"]] = digest(fact)
            with self.subTest(metric=metric), self.assertRaises(DeferredRefused):
                DeferredSettlement.restore(self.profile, self.verifier, broken)
        broken = deepcopy(original)
        identity = broken["obligations"]["ab"]["normal_gas_availability"]["identity"]
        del broken["evidence"][identity]
        with self.assertRaises(DeferredRefused):
            DeferredSettlement.restore(self.profile, self.verifier, broken)

    def test_prepared_rollback_can_refresh_same_original_budget_after_expiry(self):
        self.reserve(); self.reach_deadline()
        old = self.normal_gas_fact(at=200)
        self.engine.observe_gas_requirement("ab", old, now=200)
        operation = self.prepare("return", "ab", kind="rollback", now=200)
        commitment = operation.commitment
        with self.assertRaises(DeferredRefused):
            self.engine.mark_dispatched("return", now=301)
        current = self.normal_gas_fact(units=8, required=7, at=301)
        self.engine.observe_gas_requirement("ab", current, now=301)
        self.assertEqual((operation.identity, operation.commitment, operation.status),
                         ("return", commitment, "PREPARED"))
        item = self.engine.obligations["ab"]
        self.assertEqual((item.settlement_fee_wei, item.normal_gas["capWei"]), (20, 10))
        self.assertEqual(item.normal_gas_availability, asdict(self.verifier.facts[current]))
        self.engine.mark_dispatched("return", now=301)
        self.assertEqual(operation.status, "UNKNOWN")
        before = self.engine.snapshot()
        newer = self.normal_gas_fact(at=302)
        with self.assertRaises(DeferredRefused):
            self.engine.observe_gas_requirement("ab", newer, now=302)
        self.assertEqual(self.engine.snapshot(), before)

    def test_nonterminal_fragments_cannot_finalize_liquidation(self):
        self.reserve(); self.register()
        sale = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                            liquidation_quote=self.quote("debt-liquidation", 800))
        self.dispatch("sale")
        before = self.engine.snapshot()
        for units in (0, 300, 800, 850):
            fragment = self.fact("operation-receipt", asset=sale.asset, account=sale.recipient,
                                 reference=sale.commitment, units=units, at=200)
            with self.subTest(units=units), self.assertRaises(DeferredRefused):
                self.engine.confirm("sale", fragment, now=200)
            self.assertEqual(self.engine.snapshot(), before)
        # Synthetic terminal aggregate, not the first transfer of the route.
        terminal = self.fact("terminal-operation-receipt", asset=sale.asset, account=sale.recipient,
                             reference=sale.commitment, units=300, at=200)
        self.engine.confirm("sale", terminal, now=200)
        self.assertEqual(sale.status, "CONFIRMED")
        self.assertEqual((self.engine.obligations["ab"].escrow, self.engine.obligations["ab"].paid), (300, 0))

    def test_restore_requires_source_evidence_even_for_zero_gross_consumption(self):
        self.reserve(); self.register()
        sale = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                            liquidation_quote=self.quote("debt-liquidation", 800))
        self.dispatch("sale")
        original = self.engine.snapshot()
        forged = deepcopy(original)
        forged["operations"]["sale"]["collateral_spent"] = 0
        with self.assertRaises(DeferredRefused):
            DeferredSettlement.restore(self.profile, self.verifier, forged)
        self.assertEqual(self.engine.snapshot(), original)
        zero = self.fact("liquidation-source", chain=560048, asset="ETH", location="hoodi-vault",
                         reference=sale.commitment, units=0, at=200)
        self.engine.observe_liquidation_source("sale", zero, now=200)
        restored = DeferredSettlement.restore(self.profile, self.verifier, self.engine.snapshot())
        self.assertEqual(restored.operations["sale"].collateral_spent, 0)
        self.assertEqual(restored.operations["sale"].source_record, asdict(self.verifier.facts[zero]))
        self.assertEqual(restored.locks["lock-1"].units, 100)
        self.assertEqual(restored.obligations["ab"].due, 800)

    def test_restore_binds_original_source_gross_fact_and_evidence_index(self):
        self.reserve(); self.register()
        sale = self.prepare("sale", "ab", kind="debt-liquidation", now=200,
                            liquidation_quote=self.quote("debt-liquidation", 800))
        self.dispatch("sale")
        source = self.fact("liquidation-source", chain=560048, asset="ETH", location="hoodi-vault",
                           reference=sale.commitment, units=20, at=200)
        self.engine.observe_liquidation_source("sale", source, now=200)
        original = self.engine.snapshot()
        for mutation in ({"chain": 11155111}, {"asset": "PYUSD"}, {"account": "other-borrower"},
                         {"location": "different-vault"}, {"reference": "other-commitment"},
                         {"kind": "liquidation-penalty"}, {"units": 21}, {"units": True},
                         {"profile_commitment": "0" * 64}):
            broken = deepcopy(original)
            raw = broken["operations"]["sale"]["source_record"]
            raw.update(mutation)
            broken["evidence"][raw["identity"]] = digest(raw)
            with self.subTest(mutation=mutation), self.assertRaises(DeferredRefused):
                DeferredSettlement.restore(self.profile, self.verifier, broken)
        for mutation in ({"source_record": None}, {"collateral_spent": None}, {"collateral_spent": 0}):
            broken = deepcopy(original)
            broken["operations"]["sale"].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(DeferredRefused):
                DeferredSettlement.restore(self.profile, self.verifier, broken)
        missing = deepcopy(original)
        del missing["evidence"][sale.source_record["identity"]]
        with self.assertRaises(DeferredRefused):
            DeferredSettlement.restore(self.profile, self.verifier, missing)
        self.assertEqual(self.engine.snapshot(), original)

    def test_source_native_allocation_is_independent_and_exact(self):
        arguments = self.reserve_arguments()
        raw = arguments["source_gas_allocation"]
        original = self.verifier.facts[raw]
        before = self.engine.snapshot()
        for mutation in ({"chain": 11155111}, {"asset": "PYUSD"}, {"account": "A"},
                         {"location": "original-normal-gas-journal"}, {"reference": "wrong-fee-or-terms"},
                         {"units": 0}, {"units": 6}, {"units": 8}, {"units": True},
                         {"kind": "normal-gas-allocation"}):
            self.verifier.facts[raw] = replace(original, **mutation)
            with self.subTest(mutation=mutation), self.assertRaises(DeferredRefused):
                self.engine.reserve("ab", "lock-1", **arguments)
            self.assertEqual(self.engine.snapshot(), before)
        self.verifier.facts[raw] = original
        item = self.engine.reserve("ab", "lock-1", **arguments)
        self.assertEqual(item.source_gas_record, asdict(original))
        self.assertNotEqual(item.source_gas_allocation, item.gas_allocation)
        self.assertEqual((item.gas_allocation_record["chain"], item.source_gas_record["chain"]),
                         (11155111, 560048))
        self.assertEqual(item.source_normal_gas["payer"], "synthetic-source-treasury")
        self.assertEqual((item.principal, item.settlement_fee_wei, item.due), (800, 20, 800))

    def test_missing_source_budget_or_fact_never_uses_sepolia_allocation(self):
        for field, value in (("source_normal_gas", None), ("source_normal_gas", {}),
                             ("source_gas_allocation", None), ("source_gas_allocation", b"unverified")):
            arguments = self.reserve_arguments()
            arguments[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(DeferredRefused):
                self.engine.reserve("ab", "lock-1", **arguments)
        arguments = self.reserve_arguments()
        arguments["source_gas_allocation"] = arguments["gas_allocation"]
        with self.assertRaises(DeferredRefused):
            self.engine.reserve("ab", "lock-1", **arguments)
        self.assertEqual(self.engine.obligations, {})
        self.assertEqual(self.engine.locks["lock-1"].reserved, 0)

    def test_source_budget_cannot_be_reallocated_with_fresh_evidence(self):
        first = self.reserve(principal=400)
        source = self.source_normal_gas("second")
        source["budget"] = first.source_normal_gas["budget"]
        arguments = self.reserve_arguments(identity="second", principal=400, source_normal_gas=source)
        before = self.engine.snapshot()
        with self.assertRaises(DeferredRefused):
            self.engine.reserve("second", "lock-1", **arguments)
        self.assertEqual(self.engine.snapshot(), before)

    def test_source_budget_terms_are_bound_by_fee_and_both_parties(self):
        for key, value in (("payer", "other-source-payer"), ("budget", "other-source-budget"),
                           ("quote", "other-source-quote"), ("scope", "other-source-scope"),
                           ("grant", "other-source-grant"), ("location", "other-source-journal"),
                           ("capWei", 6), ("maxAgeSeconds", 99)):
            arguments = self.reserve_arguments()
            arguments["source_normal_gas"][key] = value
            before = self.engine.snapshot()
            with self.subTest(key=key), self.assertRaises(DeferredRefused):
                self.engine.reserve("ab", "lock-1", **arguments)
            self.assertEqual(self.engine.snapshot(), before)

    def test_payment_refund_and_unlock_bind_their_own_original_chain_budget(self):
        item = self.reserve(); self.register(); self.credit(850)
        pay = self.prepare("pay", "ab", kind="seller-payment", now=200)
        expected_normal = {"chain": 11155111, "asset": "ETH", "allocation": item.gas_allocation,
                           "terms": item.normal_gas}
        self.assertEqual(pay.normal_funding, expected_normal)
        self.complete(pay)
        refund = self.prepare("excess", "ab", kind="excess-refund", now=200)
        self.assertEqual(refund.normal_funding, expected_normal)
        self.complete(refund)
        unlock = self.prepare("unlock", "ab", kind="collateral-unlock", now=200)
        self.assertEqual(unlock.normal_funding, {"chain": 560048, "asset": "ETH",
            "allocation": item.source_gas_allocation, "terms": item.source_normal_gas})
        self.assertNotEqual(unlock.normal_funding["allocation"], pay.normal_funding["allocation"])
        restored = DeferredSettlement.restore(self.profile, self.verifier, self.engine.snapshot())
        self.assertEqual(restored.operations["unlock"].normal_funding, unlock.normal_funding)
        self.assertEqual(restored.obligations["ab"].settlement_fee_wei, 20)

    def test_restore_rejects_recommitted_normal_funding_not_in_original_allocation(self):
        self.reserve(); self.register(); self.credit(800)
        self.prepare("pay", "ab", kind="seller-payment", now=200)
        original = self.engine.snapshot()
        for field, value in (("chain", 560048), ("asset", "PYUSD"),
                             ("allocation", "another-allocation"), ("terms", self.source_normal_gas())):
            broken = deepcopy(original)
            operation = broken["operations"]["pay"]
            operation["normal_funding"][field] = value
            item = broken["obligations"]["ab"]
            # Even a recomputed operation hash cannot change original admission terms.
            operation["commitment"] = digest({"id": operation["identity"], "obligation": operation["obligation"],
                "kind": operation["kind"], "units": operation["units"], "asset": operation["asset"],
                "chain": operation["chain"], "recipient": operation["recipient"], "consent": item["consent"],
                "profile": asdict(self.profile), "collateralLimit": operation["collateral_limit"],
                "quote": operation["quote"], "liquidationTerms": operation["liquidation_terms"],
                "normalFunding": operation["normal_funding"]})
            with self.subTest(field=field), self.assertRaises(DeferredRefused):
                DeferredSettlement.restore(self.profile, self.verifier, broken)
        self.assertEqual(self.engine.snapshot(), original)
