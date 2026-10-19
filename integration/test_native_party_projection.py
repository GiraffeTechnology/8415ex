"""Remote-only definitions for position-based native HTML projections."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from exchange import views
from exchange.nft_detail import receipt_detail
from exchange.workbench import WorkbenchHandler
from integration.test_nft_detail import OriginalReadOnlyDomain


PRIVATE = "private-wallet-session-identity"


class NativePartyProjection(unittest.TestCase):
    def test_native_receipt_uses_verified_detail_instead_of_raw_mint_document(self):
        original = {"receiptId": "one", "businessTerms": {
            "coverageVerified": True, "identityExcluded": True, "clauses": [
                {"label": "All obligations", "text": "First obligation.\nSecond obligation unchanged."}]}}
        detail = receipt_detail(OriginalReadOnlyDomain(), "one",
            read_details=lambda receipt_id: deepcopy(original),
            verify_details=lambda receipt_id, row: receipt_id == "one" and row == original)
        binding = SimpleNamespace(public_detail=lambda: detail)
        handler = SimpleNamespace(server=SimpleNamespace(binding=binding, default_nft_key="a" * 64,
            nft_directory=SimpleNamespace(choices=lambda: [])),
            native_navigation=WorkbenchHandler.native_navigation)
        html = WorkbenchHandler.native_page(handler, "receipt")
        self.assertIn("First obligation.\nSecond obligation unchanged.", html)
        self.assertNotIn("private-owner-name", html)
        self.assertIn("/nft?", html)
        self.assertIn('data-native-navigation="1"', html)

    def test_authorization_page_keeps_eligibility_limits_without_identity_or_session(self):
        auth = {"authorizationId": PRIVATE, "account": PRIVATE, "applies": False, "reasons": [PRIVATE],
                "activeSession": PRIVATE, "boundSession": PRIVATE}
        grant = SimpleNamespace(allowed_actions=("trade",), counterparties=(PRIVATE,), max_amount=123,
            quote_asset="USDC", chain_id=11155111, asset=SimpleNamespace(token_id=7), not_before=10, expires_at=20, revoked=False)
        domain = SimpleNamespace(receipt_view=lambda *args: {"asset": {"chainId": 11155111}},
            authorization_state=lambda *args: auth, authorization=lambda *args: grant)
        before = deepcopy(auth)
        html = views.authorization_page(domain, "one", ["private-authorization"])
        self.assertNotIn(PRIVATE, html)
        self.assertNotIn("private-authorization", html)
        self.assertIn("123 (smallest units of USDC)", html)
        self.assertIn("no - original authorization checks did not pass", html)
        self.assertIn("restricted by original grant", html)
        self.assertEqual(auth, before)

    def test_timeline_keeps_order_amount_and_status_with_party_positions(self):
        originals = tuple(SimpleNamespace(receipt_id="one", transfer_id="transfer-" + str(index),
            leg_index=index, predecessor_transfer_id=None if index == 0 else "transfer-" + str(index - 1),
            seller=PRIVATE, buyer=PRIVATE) for index in range(4))
        row = {"receiptId": "one", "observedAt": 100,
               "activeLegIndices": list(range(4)), "historicalWithdrawnLegIndices": [],
               "legs": [{"legIndex": index, "transferId": "transfer-" + str(index),
                         "seller": PRIVATE, "buyer": PRIVATE, "price": "999", "quoteAsset": "USDC",
                         "registrationStatus": "pending", "fundingStatus": "release-outcome-unknown",
                         "rollbackStatus": "available"} for index in range(4)],
               "tradingOpen": False, "tradeStopAt": 100, "owner": {"position": 4}, "holder": {"position": 1}}
        domain = SimpleNamespace(receipt_view=lambda *args: row, legs=lambda *args: originals,
            evaluate_deadline=lambda *args: {"pastDeadline": True, "unfinishedSuffixReturnsTo": PRIVATE, "undefinedOrdering": []})
        before = deepcopy(row)
        html = views.timeline_page(domain, "one")
        self.assertNotIn(PRIVATE, html)
        for text in ("position 3", "position 4", "position 1", "999 USDC", "submitted, awaiting registrar", "payment outcome unknown"):
            self.assertIn(text, html)
        self.assertEqual(html.count("999 USDC"), 4)
        self.assertEqual(row, before)

    def test_rollback_keeps_boundary_and_separate_eth_units_without_accounts(self):
        view = {"registeredPrefixLegs": 1, "outstandingLegs": 2, "rejectedLegs": [2], "fundingModelled": True}
        rollback = {"open": True, "state": "blocked", "complete": False, "trigger": "registrar-refusal", "refusedLegIndex": 2,
                    "affectedLegs": [2, 3], "lastFinalizedPosition": 1, "returnBoundaryAccount": PRIVATE,
                    "assetControl": {"returned": False}, "outstandingSteps": [], "safeRetryCondition": "enquire first",
                    "withdrawnMechanismsNotUsed": [], "conflicts": []}
        segment = {"legIndex": 3, "principal": "999", "quoteAsset": "USDC", "escrowStatus": "locked", "paymentStatus": "unknown",
                   "netToPayee": "0", "netToPayer": "0", "gasTotal": "7001", "gasBorneBy": PRIVATE, "rollbackStatus": "in-progress"}
        domain = SimpleNamespace(receipt_view=lambda *args: view, rollback_report=lambda *args: rollback,
            reconciliation=lambda *args: {"segments": [segment]})
        before = deepcopy((rollback, segment))
        html = views.rollback_page(domain, "one")
        self.assertNotIn(PRIVATE, html)
        self.assertIn("position 1", html)
        self.assertIn("999 USDC", html)
        self.assertIn("7001 ETH wei (buyer at position 4)", html)
        self.assertIn("unknown", html)
        self.assertEqual((rollback, segment), before)
