"""Public terminal book uses original admission/revalidation, never identities or writes."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.priority_exchange import PriorityRefused
from integration.test_canonical_priority_exchange import CanonicalPriority


class PublicOrderBook(unittest.TestCase):
    def setUp(self):
        self.case = CanonicalPriority()
        self.case.setUp()
        self.exchange = self.case.exchange
        self.receipt = "rcpt-8415-0001"
        self.currency = self.exchange.receipt(self.receipt).allowed_price_currencies[0]

    def read(self, **kwargs):
        return self.exchange.order_book_view(self.receipt, self.currency, **kwargs)

    def test_empty_read_does_not_create_book_or_mutate_receipt(self):
        before = deepcopy(self.exchange.receipt_view(self.receipt))
        for _ in range(2):
            row = self.read()
            self.assertEqual(row["asks"]["rows"], [])
            self.assertEqual(row["bids"]["rows"], [])
            self.assertEqual(row["execution"], "NOT_RUN")
        self.assertEqual(self.exchange._order_books, {})
        self.assertEqual(self.exchange.receipt_view(self.receipt), before)

    def test_original_price_time_order_without_private_identity(self):
        self.case.order("private-ask-later", "sell", F.A, 110, nonce=1)
        self.case.order("private-ask-best", "sell", F.A, 100, nonce=2)
        self.case.order("private-bid-first", "buy", F.B, 120)
        self.case.order("private-bid-second", "buy", F.C, 120)
        before = deepcopy(self.exchange.receipt_view(self.receipt))
        row = self.read()
        self.assertEqual([x["priceBaseUnits"] for x in row["asks"]["rows"]], ["100", "110"])
        self.assertEqual([x["priority"] for x in row["bids"]["rows"]], [1, 2])
        self.assertEqual(row["currency"], self.currency)
        self.assertFalse(row["conversionPerformed"])
        raw = json.dumps(row)
        for secret in ("private-", "auth-", "session-", F.A, F.B, F.C,
                       "receiptId", "intentId", "signer", "nonce", "Digest"):
            self.assertNotIn(secret, raw)
        self.assertEqual(self.exchange.receipt_view(self.receipt), before)

    def test_revoked_order_is_revalidated_without_execution(self):
        self.case.order("ask", "sell", F.A, 100)
        self.case.order("bid", "buy", F.B, 120)
        self.assertEqual(self.read()["bids"]["total"], 1)
        self.exchange.revoke_authorization("auth-bid")
        self.assertEqual(self.read()["bids"]["total"], 0)
        self.assertEqual(self.exchange.recorded_legs(self.receipt), 0)

    def test_truncation_reports_counts_without_conflating_orders(self):
        self.case.order("ask1", "sell", F.A, 100, nonce=1)
        self.case.order("ask2", "sell", F.A, 100, nonce=2)
        row = self.read(limit=1)
        self.assertEqual(row["asks"], {"rows": [{"priority": 1, "priceBaseUnits": "100",
            "wholeNFTs": "1"}], "total": 2, "hasMore": True})

    def test_invalid_currency_and_limits_do_not_create_book(self):
        for currency in ("", "eth", "0x" + "a" * 40, "UNKNOWN", None):
            with self.assertRaises(DomainError):
                self.exchange.order_book_view(self.receipt, currency)
        for limit in (0, 101, True, 1.5, "20"):
            with self.assertRaises(DomainError):
                self.read(limit=limit)
        self.assertEqual(self.exchange._order_books, {})

    def test_unresolved_original_book_is_unavailable_never_empty_success(self):
        self.case.order("ask", "sell", F.A, 100)
        book = self.exchange._order_books[(self.receipt, self.currency)]
        with patch.object(book, "proposal", side_effect=PriorityRefused("unresolved original")):
            with self.assertRaises(DomainError) as raised:
                self.read()
        self.assertEqual(raised.exception.code, "EX_PUBLIC_BOOK_UNAVAILABLE")
