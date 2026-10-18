"""Remote-only domain clock/original authority separation definitions."""
from copy import deepcopy
import unittest
from exchange.nft_detail import receipt_detail
from exchange import views
from integration.test_nft_detail import OriginalReadOnlyDomain
from integration.test_register_projection import observation


class TimeBoundDomain(OriginalReadOnlyDomain):
    def __init__(self):
        self.calls = []

    def receipt_view(self, receipt_id, *args):
        self.calls.append((receipt_id, args))
        row = deepcopy(super().receipt_view(receipt_id))
        if args:
            row["owner"]["position"] = 2 if args[0] == 10 else 4
        return row


class DetailDomainTime(unittest.TestCase):
    def test_default_read_keeps_existing_one_argument_domain_contract(self):
        domain = TimeBoundDomain()
        receipt_detail(domain, "one")
        self.assertEqual(domain.calls, [("one", ())])

    def test_explicit_domain_time_reaches_original_view_without_cached_position(self):
        domain = TimeBoundDomain()
        self.assertEqual(receipt_detail(domain, "one", now=10)["positions"]["owner"], 2)
        self.assertEqual(receipt_detail(domain, "one", now=20)["positions"]["owner"], 4)
        self.assertEqual(domain.calls, [("one", (10,)), ("one", (20,))])

    def test_legacy_rendering_entry_forwards_its_original_domain_timestamp(self):
        domain = TimeBoundDomain()
        html = views.page(domain, "one", "receipt", now=10)
        self.assertEqual(domain.calls, [("one", (10,))])
        self.assertIn('class="position">2', html)
        self.assertNotIn("private-owner-name", html)

    def test_domain_clock_never_rewrites_original_chain_query_or_finality(self):
        domain = TimeBoundDomain()
        source = {"receiptId": "one", "registerObservation": observation()}
        before = deepcopy(source)
        reads, verified = [], []
        def read(receipt_id):
            reads.append(receipt_id)
            return source
        def verify(receipt_id, row):
            verified.append((receipt_id, deepcopy(row)))
            return True
        public = receipt_detail(domain, "one", now=10, read_details=read, verify_details=verify)
        self.assertEqual(public["positions"]["owner"], 2)
        self.assertEqual(public["registerProjection"]["queryTime"], 150)
        self.assertEqual(public["registerProjection"]["observedBlock"]["timestamp"], 150)
        self.assertTrue(public["registerProjection"]["isFinalAsOf"])
        self.assertEqual(reads, ["one"])
        self.assertEqual(verified, [("one", before)])
        self.assertEqual(source, before)
