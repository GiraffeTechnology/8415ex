"""Synthetic definitions only; run solely on an approved remote Linux target."""
from copy import deepcopy
from dataclasses import replace
import unittest

from exchange import fixtures as F
from exchange.remint_terms import prepare_remint_terms, RemintTermsRefused


def original_bill(binding):
    return {"billKey": "0x" + "1" * 64,
            "sourceReference": "synthetic-original-bill", "binding": binding}


class RemintTermsTests(unittest.TestCase):
    def setUp(self):
        self.old = F.mint_specification(F.receipt())
        receipt = replace(self.old.receipt,
                          asset=replace(self.old.receipt.asset, token_id=8416),
                          receipt_id="synthetic-replacement-receipt",
                          allowed_price_currencies=("ETH", "synthetic-token"),
                          nft0_currency_reference="synthetic-replacement-set")
        self.new = replace(self.old, receipt=receipt, bill_terms="Replacement terms")

    def prepare(self, **kwargs):
        return prepare_remint_terms(kwargs.get("old", self.old),
                                    kwargs.get("replacement", self.new),
                                    kwargs.get("verify", F.verify_fixture_mint),
                                    kwargs.get("resolve", original_bill))

    def test_complete_old_and_new_terms_and_currency_changes_are_retained(self):
        result = self.prepare()
        history = result["history"]
        self.assertEqual(history["oldDeclaration"]["billTerms"], F.FIXTURE_BILL_TERMS)
        self.assertEqual(history["newDeclaration"]["billTerms"], "Replacement terms")
        changes = {item["path"]: item for item in history["changes"]}
        self.assertEqual(changes["/receipt/allowed_price_currencies"]["new"],
                         ["ETH", "synthetic-token"])
        self.assertEqual(changes["/billTerms"]["category"], "terms")
        self.assertEqual(changes["/receipt/asset/token_id"]["category"], "nft-identity")
        self.assertEqual(result["authorization"], "NOT_PERFORMED")
        self.assertEqual(result["oldBurn"], "NOT_RUN")
        self.assertEqual(result["newMint"], "NOT_RUN")

    def test_added_and_removed_optional_attributes_are_explicit(self):
        template = replace(self.old.template,
                           applicable_fields=("condition", "color", "grade"))
        old = replace(self.old, template=template,
                      public_attributes=(("condition", "fixture-only"), ("color", "blue")))
        new = replace(self.new, template=template,
                      public_attributes=(("condition", "fixture-only"), ("grade", "A")))
        changes = {item["path"]: item for item in self.prepare(old=old, replacement=new)
                   ["history"]["changes"]}
        self.assertEqual(changes["/commodityAttributes/color"]["kind"], "removed")
        self.assertEqual(changes["/commodityAttributes/grade"]["kind"], "added")

    def test_history_is_detached_and_digest_is_deterministic(self):
        result = self.prepare()
        digest = result["historyDigest"]
        self.assertEqual(self.prepare()["historyDigest"], digest)
        result["history"]["oldDeclaration"]["receipt"]["allowed_price_currencies"].append("bad")
        self.assertEqual(self.old.receipt.allowed_price_currencies, (F.QUOTE_ASSET,))
        self.assertEqual(self.prepare()["historyDigest"], digest)
        changed = replace(self.new, bill_terms="Another replacement")
        self.assertNotEqual(self.prepare(replacement=changed)["historyDigest"], digest)

    def test_required_original_verification_failure_stops_before_bill_lookup(self):
        for refused in ("existing-nft0-currency-schema", "existing-asset-template-schema",
                        "controlled-encrypted-access-mapping", "non-secret-metadata-scan"):
            calls = []
            with self.subTest(refused=refused), self.assertRaises(RemintTermsRefused):
                self.prepare(verify=lambda kind, evidence: kind != refused,
                             resolve=lambda binding: calls.append(binding))
            self.assertEqual(calls, [])

    def test_same_nft_and_other_chain_are_refused(self):
        with self.assertRaises(RemintTermsRefused):
            self.prepare(replacement=replace(self.new, receipt=self.old.receipt))
        other = replace(self.new.receipt, asset=replace(self.new.receipt.asset, chain_id=560048))
        with self.assertRaises(RemintTermsRefused):
            self.prepare(replacement=replace(self.new, receipt=other))

    def test_bill_mapping_requires_exact_declarations_and_nonzero_identity(self):
        def mismatch(binding):
            row = original_bill(deepcopy(binding))
            row["binding"]["newDeclarationDigest"] = "0" * 64
            return row
        def zero(binding):
            return dict(original_bill(binding), billKey="0x" + "0" * 64)
        def missing(binding):
            raise ConnectionError("synthetic unavailable source")
        for resolver in (mismatch, zero, missing):
            with self.subTest(resolver=resolver.__name__), self.assertRaises(RemintTermsRefused):
                self.prepare(resolve=resolver)

    def test_verifier_mutation_cannot_rewrite_the_declaration(self):
        def mutate(kind, evidence):
            evidence["billTerms"] = "Injected terms"
            return True
        with self.assertRaises(RemintTermsRefused):
            self.prepare(verify=mutate)
        self.assertEqual(self.old.bill_terms, F.FIXTURE_BILL_TERMS)

    def test_numerically_equal_float_cannot_replace_exact_integer_asset_identity(self):
        def coerce(binding):
            row = original_bill(deepcopy(binding))
            row["binding"]["oldAsset"]["token_id"] = float(binding["oldAsset"]["token_id"])
            return row
        with self.assertRaises(RemintTermsRefused):
            self.prepare(resolve=coerce)


if __name__ == "__main__":
    unittest.main()
