"""Authored contract cases; execution belongs to independent QA."""
import copy
import unittest
from exchange.receipt_task_projection import project_receipt_task


def snapshot(chain="560048"):
    h="0x"+"1"*64
    return {"digest":h,"policy":{"schema":"8415-agent-task/1","taskId":"task-1",
        "chainId":chain,"actor":"0x"+"2"*40,"intent":{"kind":"artfi-receipt",
        "handlerId":"artfi:whole-receipt:v1","segmentId":h,
        "sale":{"collection":"0x"+"3"*40,"tokenId":"1"},
        "phases":[{"phase":"funded","nonce":"0","planDigest":h,"journalBindingHash":h}]}}}


class ReceiptTaskProjectionTests(unittest.TestCase):
    def test_original_hoodi_snapshot_is_readable_but_never_ex_ready(self):
        result=project_receipt_task(snapshot())
        self.assertEqual(result["chainId"],"560048")
        self.assertIn("EX_SEPOLIA_CHAIN_MISMATCH",result["gaps"])
        self.assertFalse(result["canExecute"])
        self.assertEqual(result["state"],"NOT_VERIFIED")

    def test_sepolia_literal_does_not_expand_the_original_wallet_contract(self):
        result=project_receipt_task(snapshot("11155111"))
        self.assertIn("PINNED_WALLET_RECEIPT_CONTRACT_HAS_NO_SEPOLIA_SUPPORT",result["gaps"])
        self.assertEqual(result["digestVerification"],"NOT_RUN")
        self.assertFalse(result["canExecute"])

    def test_caller_verified_flag_and_secret_are_not_projected(self):
        value=snapshot(); value["verified"]=True; value["secret"]="never expose"
        before=copy.deepcopy(value)
        result=project_receipt_task(value)
        self.assertEqual(value,before)
        self.assertNotIn("secret",str(result)); self.assertNotIn("verified",result)
        self.assertEqual(result["authorization"],"NOT_VERIFIED")

    def test_unknown_or_duplicate_phase_is_refused(self):
        for phase in ("advance-rollback","funded"):
            value=snapshot(); second=dict(value["policy"]["intent"]["phases"][0],phase=phase)
            value["policy"]["intent"]["phases"].append(second)
            with self.assertRaises(ValueError): project_receipt_task(value)

    def test_numeric_nonce_is_not_coerced_and_zero_digest_is_refused(self):
        value=snapshot(); value["policy"]["intent"]["phases"][0]["nonce"]=0
        with self.assertRaises(ValueError): project_receipt_task(value)
        value=snapshot(); value["digest"]="0x"+"0"*64
        with self.assertRaises(ValueError): project_receipt_task(value)
