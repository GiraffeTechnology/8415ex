"""T-01, T-02, T-26: whole-receipt scope and the owner/holder dual track."""
import unittest

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.ledger import Exchange
from exchange.model import WHOLE_RECEIPT_UNITS, Asset, WarehouseReceipt


class WholeReceiptScope(unittest.TestCase):
    """T-01: one NFT is one whole receipt; the goods quantity inside it survives."""

    def test_tradeable_units_are_one_while_commodity_quantity_is_preserved(self):
        receipt = F.receipt()
        self.assertEqual(receipt.tradeable_units, WHOLE_RECEIPT_UNITS)
        self.assertEqual(receipt.commodity_quantity, 1)
        bulk = WarehouseReceipt(receipt_id="rcpt-bulk", asset=Asset(F.CHAIN_ID, F.CONTRACT, 99),
                                commodity_name="Grain lot", commodity_quantity=25_000,
                                commodity_unit="kg", receipt_number="WR-BULK-1",
                                registration_path="REG_DIRECT", trade_stop_at=1_700_900_000,
                                origin_account=F.A, minted_at=1_699_000_000)
        self.assertEqual(bulk.commodity_quantity, 25_000)
        self.assertEqual(bulk.tradeable_units, 1, "the tradeable quantity is the whole receipt, not the goods")

    def test_fractional_and_multi_unit_intents_are_refused(self):
        for units in (0, 2, 10):
            with self.assertRaises(DomainError) as caught:
                F.intent("sell-x", "sell", F.A, "auth-1", F.B, 1, units=units)
            self.assertEqual(caught.exception.code, "EX_WHOLE_RECEIPT_REFUSED")

    def test_a_non_integer_share_cannot_even_be_expressed(self):
        with self.assertRaises(DomainError) as caught:
            F.intent("sell-x", "sell", F.A, "auth-1", F.B, 1, units=0.5)
        self.assertEqual(caught.exception.code, "EX_WHOLE_RECEIPT_REFUSED")

    def test_duplicate_receipt_to_nft_mapping_is_refused(self):
        exchange, _ = F.minted()
        duplicate = WarehouseReceipt(receipt_id="rcpt-second", asset=F.asset(),
                                     commodity_name="Second claim", commodity_quantity=1,
                                     commodity_unit="piece", receipt_number="WR-8415-0002",
                                     registration_path="REG_DIRECT", trade_stop_at=1_700_900_000,
                                     origin_account=F.B, minted_at=1_699_000_000,
                                     allowed_price_currencies=(F.QUOTE_ASSET,),
                                     nft0_currency_reference=F.NFT0_CURRENCY_SET_REF)
        with self.assertRaises(DomainError) as caught:
            exchange.mint(duplicate, specification=F.mint_specification(duplicate))
        self.assertEqual(caught.exception.code, "EX_ASSET_DUPLICATE_REFUSED")

    def test_the_same_receipt_id_cannot_be_minted_twice(self):
        exchange, _ = F.minted()
        with self.assertRaises(DomainError) as caught:
            exchange.mint(F.receipt(), specification=F.mint_specification(F.receipt()))
        self.assertEqual(caught.exception.code, "EX_RECEIPT_DUPLICATE_REFUSED")


class DualTrack(unittest.TestCase):
    """T-02: owner0 equals holder0, and the two tracks stay separate afterwards."""

    def test_origin_is_both_owner_and_holder(self):
        exchange, _ = F.minted()
        view = exchange.receipt_view("rcpt-8415-0001")
        self.assertEqual(view["owner"]["account"], F.A)
        self.assertEqual(view["holder"]["account"], F.A)
        self.assertEqual((view["owner"]["position"], view["holder"]["position"]), (0, 0))
        self.assertTrue(view["ownerEqualsHolder"])

    def test_owner_runs_ahead_of_holder_and_both_stay_readable(self):
        exchange, _ = F.chain_to_d()
        view = exchange.receipt_view("rcpt-8415-0001")
        self.assertEqual(view["owner"]["account"], F.D)
        self.assertEqual(view["owner"]["position"], 3)
        self.assertEqual(view["holder"]["account"], F.A)
        self.assertEqual(view["holder"]["position"], 0)
        self.assertFalse(view["ownerEqualsHolder"])
        self.assertEqual(view["outstandingLegs"], 3)

    def test_equal_tracks_do_not_reactivate_retired_physical_fulfillment(self):
        exchange, _ = F.minted()
        receipt_id = "rcpt-8415-0001"
        before = exchange.receipt_timeline(receipt_id)
        view = exchange.receipt_view(receipt_id)
        self.assertTrue(view["ownerEqualsHolder"])
        self.assertEqual(view["owner"]["account"], F.A)
        self.assertEqual(view["holder"]["account"], F.A)
        readiness = exchange.redemption_readiness(receipt_id, F.A)
        self.assertFalse(readiness["eligible"])
        self.assertEqual(readiness["reasons"], ("EX_PHYSICAL_FULFILLMENT_RETIRED",))
        self.assertEqual(readiness["physicalActions"], ())
        self.assertNotIn("necessaryConditionMet", readiness)
        self.assertNotIn("furtherChecksNotPerformedHere", readiness)
        self.assertEqual(exchange.receipt_timeline(receipt_id), before)
        self.assertIsNone(exchange._exits[receipt_id])

    def test_divergent_tracks_remain_readable_without_a_physical_checklist(self):
        exchange, _ = F.chain_to_d()
        receipt_id = "rcpt-8415-0001"
        before = exchange.receipt_timeline(receipt_id)
        view = exchange.receipt_view(receipt_id)
        self.assertFalse(view["ownerEqualsHolder"])
        self.assertEqual(view["owner"]["account"], F.D)
        self.assertEqual(view["holder"]["account"], F.A)
        for requester in (F.A, F.D):
            with self.subTest(requester=requester):
                readiness = exchange.redemption_readiness(receipt_id, requester)
                self.assertFalse(readiness["eligible"])
                self.assertEqual(readiness["reasons"], ("EX_PHYSICAL_FULFILLMENT_RETIRED",))
                self.assertEqual(readiness["physicalActions"], ())
                self.assertNotIn("necessaryConditionMet", readiness)
                self.assertNotIn("furtherChecksNotPerformedHere", readiness)
        self.assertEqual(exchange.receipt_timeline(receipt_id), before)
        self.assertIsNone(exchange._exits[receipt_id])

class NoCollapsedStatus(unittest.TestCase):
    """T-26: simulated vs real, pending vs complete, owner vs holder stay distinct."""

    def test_the_view_separates_every_axis(self):
        exchange, _ = F.chain_to_d()
        F.submit_all(exchange)
        view = exchange.receipt_view("rcpt-8415-0001")
        self.assertTrue(view["simulatedRegistration"])
        self.assertIn("simulated", view["registrationPathLabel"])
        self.assertFalse(view["fundingModelled"], "Stage 1 models no funding")
        self.assertNotEqual(view["owner"]["account"], view["holder"]["account"])
        for leg in view["legs"]:
            self.assertEqual(leg["registrationStatus"], "pending")
            self.assertEqual(leg["executionStatus"], "executed")
            self.assertEqual(leg["fundingStatus"], "not-modelled")
            self.assertNotIn("success", leg)

    def test_a_submitted_leg_is_never_reported_as_settled(self):
        exchange, _ = F.chain_to_d()
        requests = F.submit_all(exchange)
        F.confirm(exchange, requests[0], "res-0")
        view = exchange.receipt_view("rcpt-8415-0001")
        self.assertEqual(view["legs"][0]["registrationStatus"], "confirmed")
        self.assertEqual(view["legs"][0]["fundingStatus"], "not-modelled")
        self.assertEqual(view["registeredPrefixLegs"], 1)
        self.assertEqual(view["outstandingLegs"], 2)


if __name__ == "__main__":
    unittest.main()
