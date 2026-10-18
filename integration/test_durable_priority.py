"""Restart FIFO definitions with real temporary SQLite and synthetic domain orders."""
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest

from exchange import fixtures as F
from exchange.ledger import Exchange
from exchange.priority_exchange import PriorityBook, PriorityRefused
from exchange.priority_journal import DurablePriorityStore, PriorityPersistenceRefused, PriorityCommitUnknown


class LostPriorityCommitAck(sqlite3.Connection):
    lose_ack = False

    def commit(self):
        super().commit()
        if self.lose_ack:
            self.lose_ack = False
            raise sqlite3.OperationalError("synthetic committed acknowledgement lost")


class DurablePriorityContracts(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = str(Path(directory.name) / "priority.sqlite")
        self.connection = self.connect()
        DurablePriorityStore.initialize(self.connection)
        self.store = DurablePriorityStore(self.connection)

    def connect(self, factory=sqlite3.Connection):
        connection = sqlite3.connect(self.path, factory=factory)
        self.addCleanup(connection.close)
        return connection

    def exchange(self, store):
        clock = F.ManualClock()
        exchange = Exchange(clock, priority_store=store,
            mint_verifier=F.verify_fixture_mint, eth_gas_gate=F.fixture_eth_gas_gate(),
            price_balance_gate=F.fixture_price_balance_gate())
        receipt = F.receipt()
        exchange.mint(receipt, specification=F.mint_specification(receipt))
        return exchange

    def submit(self, exchange, label, signer, nonce, side="buy"):
        session = "session-" + label
        grant = "grant-" + label
        exchange.connect_wallet(signer, session)
        exchange.register_authorization(F.authorization(signer, grant, session))
        return exchange.submit_intent(F.intent("intent-" + label, side, signer, grant, None, nonce))

    def test_fresh_exchange_and_reopened_store_keep_original_fifo_despite_reverse_restore(self):
        first = self.exchange(self.store)
        self.submit(first, "b", F.B, 1)
        self.submit(first, "c", F.C, 2)
        self.submit(first, "ask", F.A, 3, "sell")
        original = first._order_books[(F.receipt().receipt_id, F.QUOTE_ASSET)].proposal()
        self.connection.close()
        second = self.exchange(DurablePriorityStore(self.connect()))
        self.submit(second, "c", F.C, 2)
        self.submit(second, "ask", F.A, 3, "sell")
        self.submit(second, "b", F.B, 1)
        restored = second._order_books[(F.receipt().receipt_id, F.QUOTE_ASSET)].proposal()
        self.assertEqual(restored["bidPriority"], original["bidPriority"])
        self.assertEqual(restored["bidPriority"], ["intent-b", "intent-c"])
        self.assertEqual(second.enter_order("intent-b"), 1)
        self.assertEqual(second.enter_order("intent-c"), 2)
        self.assertEqual(restored["selected"]["buyIntentId"], "intent-b")

    def test_missing_original_terms_block_matching_instead_of_renumbering_orders(self):
        first = self.exchange(self.store)
        self.submit(first, "b", F.B, 1)
        other = self.exchange(DurablePriorityStore(self.connect()))
        self.submit(other, "c", F.C, 2)
        book = other._order_books[(F.receipt().receipt_id, F.QUOTE_ASSET)]
        with self.assertRaisesRegex(PriorityRefused, "terms must be restored"):
            book.proposal()
        self.assertEqual(other.enter_order("intent-c"), 2)
        self.submit(other, "b", F.B, 1)
        self.assertEqual(book.proposal()["bidPriority"], ["intent-b", "intent-c"])

    def test_independent_connections_serialize_server_admission_order(self):
        first = self.exchange(self.store)
        b = self.submit(first, "b", F.B, 1)
        book = first._order_books[(F.receipt().receipt_id, F.QUOTE_ASSET)]
        second = DurablePriorityStore(self.connect())
        c = F.intent("intent-c", "buy", F.C, "grant-c", None, 2)
        self.assertEqual(second.admit(book._book_scope, c), 2)
        self.assertEqual(second.admit(book._book_scope, b), 1)
        self.assertEqual([row["sequence"] for row in self.store.read(book._book_scope)], [1, 2])

    def test_existing_identity_or_nonce_cannot_be_rebound(self):
        exchange = self.exchange(self.store)
        intent = self.submit(exchange, "b", F.B, 1)
        scope = exchange._order_books[(F.receipt().receipt_id, F.QUOTE_ASSET)]._book_scope
        with self.assertRaisesRegex(PriorityPersistenceRefused, "identity conflict"):
            self.store.admit(scope, replace(intent, limit_price=intent.limit_price + 1))
        with self.assertRaisesRegex(PriorityPersistenceRefused, "Nonce already"):
            self.store.admit(scope, replace(intent, intent_id="another-order"))
        self.assertEqual(len(self.store.read(scope)), 1)

    def test_new_generation_has_distinct_sequences_and_retains_old_book(self):
        exchange = self.exchange(self.store)
        intent = self.submit(exchange, "b", F.B, 1)
        old = exchange._order_books[(F.receipt().receipt_id, F.QUOTE_ASSET)]._book_scope
        newer = dict(old, generation=1)
        self.assertEqual(self.store.admit(newer, intent), 1)
        self.assertEqual(self.store.read(old)[0]["intentDigest"], intent.digest)
        self.assertEqual(len(self.store.read(newer)), 1)
        self.assertNotEqual(old, newer)

    def test_lost_commit_acknowledgement_recovers_same_original_sequence(self):
        lost = self.connect(factory=LostPriorityCommitAck)
        store = DurablePriorityStore(lost)
        exchange = self.exchange(store)
        lost.lose_ack = True
        with self.assertRaises(PriorityCommitUnknown):
            self.submit(exchange, "b", F.B, 1)
        self.assertEqual(exchange.enter_order("intent-b"), 1)
        scope = exchange._order_books[(F.receipt().receipt_id, F.QUOTE_ASSET)]._book_scope
        self.assertEqual(len(store.read(scope)), 1)

    def test_unsafe_storage_or_another_owners_transaction_is_not_accepted(self):
        memory = sqlite3.connect(":memory:")
        self.addCleanup(memory.close)
        with self.assertRaises(PriorityPersistenceRefused):
            DurablePriorityStore(memory)
        self.connection.execute("PRAGMA synchronous=OFF")
        with self.assertRaises(PriorityPersistenceRefused):
            DurablePriorityStore(self.connection)
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("PRAGMA journal_mode=MEMORY")
        with self.assertRaises(PriorityPersistenceRefused):
            DurablePriorityStore(self.connection)
        self.connection.execute("PRAGMA journal_mode=DELETE")
        self.connection.execute("BEGIN")
        try:
            with self.assertRaises(PriorityPersistenceRefused):
                DurablePriorityStore.initialize(self.connection)
            self.assertTrue(self.connection.in_transaction)
        finally:
            self.connection.rollback()
