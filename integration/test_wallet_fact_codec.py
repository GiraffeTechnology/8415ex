"""Synthetic EX reference/nonce facts; no real wallet or session authentication."""
from dataclasses import replace
import unittest

from exchange.fixtures import A, B, asset, authorization
from exchange.model import TradeIntent
from exchange.operational_facts_codec import encode_operational_facts, decode_operational_facts
from exchange.wallet_fact_codec import WalletFactsRefused, decode_wallet_facts, encode_wallet_facts


class WalletFactCodecTests(unittest.TestCase):
    def facts(self):
        reference = authorization(A, "original-auth", "session-before", counterparties=(B,))
        intent = TradeIntent("intent-1", "sell", A, asset(), 103, "local-test-quote", 1, 7,
                             1700800000, reference.authorization_id, B, "original-currency-set")
        return {"authorizations": (reference,), "intents": (intent,),
                "sessions": {A: "session-after"}, "usedNonces": frozenset(((A, 7),))}

    def test_signed_terms_and_digest_remain_exact(self):
        original = self.facts()
        result = decode_wallet_facts(encode_wallet_facts(original))
        self.assertEqual(result.facts, original)
        self.assertEqual(result.facts["intents"][0].signed_terms, original["intents"][0].signed_terms)
        self.assertEqual(result.facts["intents"][0].digest, original["intents"][0].digest)
        self.assertFalse(result.execution_authorized)

    def test_revoked_expired_reference_does_not_become_fresh_authority(self):
        original = self.facts()
        reference = replace(original["authorizations"][0], revoked=True, not_before=1, expires_at=2)
        original["authorizations"] = (reference,)
        result = decode_wallet_facts(encode_wallet_facts(original))
        self.assertTrue(result.facts["authorizations"][0].revoked)
        self.assertEqual(result.facts["authorizations"][0].expires_at, 2)
        self.assertFalse(result.execution_authorized)

    def test_later_session_and_used_nonce_survive_without_realignment(self):
        original = self.facts()
        result = decode_wallet_facts(encode_wallet_facts(original)).facts
        self.assertEqual(result["authorizations"][0].session_id, "session-before")
        self.assertEqual(result["sessions"][A], "session-after")
        self.assertIn((A, 7), result["usedNonces"])
        self.assertIs(type(result["usedNonces"]), frozenset)

    def test_input_and_returned_session_maps_do_not_share_state(self):
        original = self.facts(); raw = encode_wallet_facts(original)
        original["sessions"][A] = "changed-after-save"
        result = decode_wallet_facts(raw)
        self.assertEqual(result.facts["sessions"][A], "session-after")
        result.facts["sessions"][A] = "changed-after-read"
        self.assertEqual(decode_wallet_facts(raw).facts["sessions"][A], "session-after")

    def test_cross_account_asset_and_missing_authorization_references_refused(self):
        for change in ("account", "asset", "missing"):
            original = self.facts()
            reference = original["authorizations"][0]
            if change == "account": original["authorizations"] = (replace(reference, account=B),)
            if change == "asset":
                original["authorizations"] = (replace(reference, asset=replace(reference.asset, token_id=999)),)
            if change == "missing": original["authorizations"] = ()
            with self.subTest(change=change), self.assertRaises(WalletFactsRefused):
                encode_wallet_facts(original)

    def test_duplicate_reference_ids_and_missing_groups_refused(self):
        original = self.facts()
        original["intents"] = original["intents"] * 2
        with self.assertRaises(WalletFactsRefused): encode_wallet_facts(original)
        original = self.facts(); del original["usedNonces"]
        with self.assertRaises(WalletFactsRefused): encode_wallet_facts(original)

    def test_boolean_negative_and_mutable_consumed_nonce_sets_refused(self):
        for nonces in (frozenset(((A, True),)), frozenset(((A, -1),)), {(A, 7)}):
            original = self.facts(); original["usedNonces"] = nonces
            with self.subTest(nonces=nonces), self.assertRaises(WalletFactsRefused):
                encode_wallet_facts(original)

    def test_unknown_versions_fields_and_malformed_bytes_refused(self):
        raw = encode_wallet_facts(self.facts())
        for kind in ("version", "field"):
            value = decode_operational_facts(raw).value
            if kind == "version": value["schema"] = "future-version"
            else: value["authorizations"][0]["future_field"] = "unapproved"
            with self.subTest(kind=kind), self.assertRaises(WalletFactsRefused):
                decode_wallet_facts(encode_operational_facts(value))
        with self.assertRaises(WalletFactsRefused): decode_wallet_facts(raw[:-1])
