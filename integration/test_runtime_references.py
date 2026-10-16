"""Authored descriptor contracts for the independent Linux QA owner."""
import unittest
from exchange.runtime_references import RuntimeReferences

class RuntimeReferenceContracts(unittest.TestCase):
    def descriptor(self):
        return {"chain_id":11155111,"test_token":"0x"+"1"*40,"token_decimals":6,
                "wallet_ref":"fixture-wallet","journal_ref":"fixture-journal",
                "oracle_ref":"fixture-oracle","settlement_ref":"fixture-settlement",
                "asset_control_ref":"fixture-asset-control"}
    def test_presence_never_means_ready_or_executed(self):
        ref=RuntimeReferences.from_mapping(self.descriptor())
        identity=ref.identity()
        self.assertEqual(identity["configuration"],"PRESENT_UNVERIFIED")
        self.assertEqual(identity["operationsREADY"],"NOT_VERIFIED")
        self.assertEqual(identity["providerExecution"],"NOT_RUN")
    def test_wrong_or_boolean_chain_refused(self):
        for chain in (1,17000,True,"11155111"):
            data=self.descriptor(); data["chain_id"]=chain
            with self.assertRaises(ValueError): RuntimeReferences.from_mapping(data)
    def test_unknown_or_secret_fields_refused(self):
        data=self.descriptor(); data["private_key"]="synthetic-never-load"
        with self.assertRaises(ValueError): RuntimeReferences.from_mapping(data)
    def test_asset_match_is_specific_and_case_insensitive(self):
        ref=RuntimeReferences.from_mapping(self.descriptor())
        ref.guard_asset(11155111,ref.test_token)
        with self.assertRaises(ValueError): ref.guard_asset(11155111,"0x"+"2"*40)
        with self.assertRaises(ValueError): ref.guard_asset(1,ref.test_token)
    def test_no_default_token_or_precision(self):
        for name in ("test_token","token_decimals"):
            data=self.descriptor(); del data[name]
            with self.assertRaises(ValueError): RuntimeReferences.from_mapping(data)
