"""Synthetic owned-state capture; no live service restoration or native effects."""
import unittest

from exchange.ledger import Exchange
from exchange.fixtures import A
from exchange.priority_exchange import PriorityBook
from exchange.exchange_fact_snapshot import (encode_exchange_snapshot, decode_exchange_snapshot,
    ExchangeSnapshotRefused, DOMAIN_FIELDS)
from exchange.operational_facts_codec import encode_operational_facts, decode_operational_facts
from integration.test_mint_specification_codec import specification


class ExchangeFactSnapshotTests(unittest.TestCase):
    def exchange(self, minted=True):
        exchange = Exchange(lambda: 20, mint_verifier=lambda kind, evidence: True)
        if minted:
            spec = specification()
            exchange.mint(spec.receipt, spec)
        return exchange

    def test_empty_exchange_retains_explicit_complete_owned_maps(self):
        result = decode_exchange_snapshot(encode_exchange_snapshot(self.exchange(False)))
        self.assertEqual(result.receipts, {})
        self.assertEqual(set(result.domain), set(DOMAIN_FIELDS))
        self.assertFalse(result.execution_authorized)
        self.assertFalse(result.complete_recovery)

    def test_mint_terms_currency_and_three_uniqueness_indexes_preserved(self):
        original = self.exchange()
        result = decode_exchange_snapshot(encode_exchange_snapshot(original))
        self.assertEqual(result.receipts, original._receipts)
        self.assertEqual(result.domain["_mint_declarations"], original._mint_declarations)
        self.assertEqual(result.domain["_nft0_currency_sets"], original._nft0_currency_sets)
        for name in ("_assets", "_receipts", "_documents"):
            self.assertEqual(result.mint_indexes[name], getattr(original._mint_book, name))

    def test_capture_does_not_call_runtime_dependencies_or_verifier(self):
        original = self.exchange()
        def forbidden(*args, **kwargs):
            raise AssertionError("runtime callback invoked")
        original._clock = forbidden
        original._mint_book.verify = forbidden
        original.payments = object()
        original.asset_control = object()
        original._priority_store = object()
        original.voucher_desk = object()
        raw = encode_exchange_snapshot(original)
        self.assertFalse(decode_exchange_snapshot(raw).execution_authorized)

    def test_nonce_consumption_and_historical_unknown_facts_do_not_change(self):
        original = self.exchange()
        original._used_nonces.add((A, 7))
        original._sessions[A] = "later-session"
        original._gas["receipt-1"][0] = [{"status": "UNKNOWN", "reference": "original-attempt"}]
        result = decode_exchange_snapshot(encode_exchange_snapshot(original))
        self.assertEqual(result.wallet["usedNonces"], frozenset(((A, 7),)))
        self.assertEqual(result.wallet["sessions"][A], "later-session")
        self.assertEqual(result.domain["_gas"]["receipt-1"][0][0]["status"], "UNKNOWN")

    def test_snapshot_and_each_decode_are_detached(self):
        original = self.exchange()
        raw = encode_exchange_snapshot(original)
        original._events["receipt-1"].append({"synthetic": "later"})
        first = decode_exchange_snapshot(raw)
        second = decode_exchange_snapshot(raw)
        self.assertEqual(len(first.domain["_events"]["receipt-1"]), 1)
        first.domain["_events"]["receipt-1"].clear()
        self.assertEqual(len(second.domain["_events"]["receipt-1"]), 1)

    def test_priority_admission_counter_and_unresolved_rows_are_not_recomputed(self):
        original = self.exchange()
        book = PriorityBook(original, "receipt-1", "quote-a", lambda: 20)
        book._sequence = 25
        book._unresolved = ("missing-intent",)
        book._nonces[(A, 7)] = "missing-intent"
        original._order_books[("receipt-1", "quote-a")] = book
        result = decode_exchange_snapshot(encode_exchange_snapshot(original))
        facts = result.priority_books[("receipt-1", "quote-a")]
        self.assertEqual(facts["sequence"], 25)
        self.assertEqual(facts["unresolved"], ("missing-intent",))
        self.assertEqual(facts["nonces"][(A, 7)], "missing-intent")

    def test_source_field_drift_refused_instead_of_silently_omitted(self):
        original = self.exchange()
        original._new_native_state = {"status": "UNKNOWN"}
        with self.assertRaises(ExchangeSnapshotRefused):
            encode_exchange_snapshot(original)

    def test_dangling_receipt_asset_currency_and_occurrence_indexes_refused(self):
        raw = encode_exchange_snapshot(self.exchange())
        for change in ("missing-map", "asset", "currency", "holder", "active"):
            value = decode_operational_facts(raw).value
            domain = value["domain"]
            if change == "missing-map": del domain["_events"]["receipt-1"]
            if change == "asset": domain["_asset_keys"].clear()
            if change == "currency": domain["_nft0_currency_sets"]["receipt-1"] = (("other",), "other")
            if change == "holder": domain["_holder_index"]["receipt-1"] = True
            if change == "active": domain["_active_legs"]["receipt-1"] = [0]
            with self.subTest(change=change), self.assertRaises(ExchangeSnapshotRefused):
                decode_exchange_snapshot(encode_operational_facts(value))

    def test_unsupported_historical_objects_are_refused_without_erasing_evidence(self):
        original = self.exchange()
        legacy = object()
        original._exits["receipt-1"] = {"steps": [legacy], "status": "UNKNOWN"}
        with self.assertRaises(ExchangeSnapshotRefused):
            encode_exchange_snapshot(original)
        self.assertIs(original._exits["receipt-1"]["steps"][0], legacy)
