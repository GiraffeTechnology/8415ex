"""Approved-Linux SQLite definitions; no native financial execution."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.priority_journal import (
    DurablePriorityStore, PriorityPersistenceRefused, PriorityCommitUnknown,
)


class AdmissionFailureStore(DurablePriorityStore):
    def __init__(self, connection, after_commit=False):
        super().__init__(connection)
        self.after_commit = after_commit
        self.fail_once = True

    def admit(self, scope, intent):
        if self.fail_once:
            self.fail_once = False
            if self.after_commit:
                super().admit(scope, intent)
                raise PriorityCommitUnknown("synthetic acknowledgement lost")
            raise PriorityPersistenceRefused("synthetic pre-commit refusal")
        return super().admit(scope, intent)


class IntentAdmissionRecoveryTests(unittest.TestCase):
    def fixture(self, after_commit=False):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        connection = sqlite3.connect(str(Path(directory.name) / "priority.sqlite"))
        self.addCleanup(connection.close)
        connection.execute("PRAGMA synchronous=FULL")
        DurablePriorityStore.initialize(connection)
        store = AdmissionFailureStore(connection, after_commit)
        exchange, clock = F.minted()
        exchange._priority_store = store  # Synthetic binding before any admission.
        exchange.connect_wallet(F.B, "fixture-buyer")
        exchange.register_authorization(F.authorization(
            F.B, "fixture-buy-grant", "fixture-buyer"))
        intent = F.intent("buy-original", "buy", F.B, "fixture-buy-grant", None, 1)
        return exchange, clock, connection, intent

    def rows(self, connection):
        return connection.execute(
            "SELECT intent_id,sequence FROM ex_priority_entries ORDER BY sequence").fetchall()

    def test_same_submission_recovers_a_pre_commit_refusal_once(self):
        exchange, _, connection, intent = self.fixture()
        with self.assertRaises(DomainError) as raised:
            exchange.submit_intent(intent)
        self.assertEqual(raised.exception.code, "EX_ORDER_REFUSED")
        self.assertEqual(self.rows(connection), [])
        event_count = len(exchange.receipt_timeline("rcpt-8415-0001"))
        self.assertEqual(exchange.submit_intent(intent), intent)
        self.assertEqual(exchange.submit_intent(intent), intent)
        self.assertEqual(self.rows(connection), [("buy-original", 1)])
        self.assertEqual(len(exchange.receipt_timeline("rcpt-8415-0001")), event_count)
        self.assertEqual(exchange.legs("rcpt-8415-0001"), ())

    def test_unknown_commit_reads_existing_sequence_without_duplicate_admission(self):
        exchange, _, connection, intent = self.fixture(after_commit=True)
        with self.assertRaises(PriorityCommitUnknown):
            exchange.submit_intent(intent)
        self.assertEqual(self.rows(connection), [("buy-original", 1)])
        exchange.submit_intent(intent)
        exchange.submit_intent(intent)
        self.assertEqual(self.rows(connection), [("buy-original", 1)])
        book = exchange._order_books[("rcpt-8415-0001", F.QUOTE_ASSET)]
        self.assertEqual(book._entries[intent.intent_id][1], 1)

    def test_uncommitted_order_retries_at_actual_server_admission_order(self):
        exchange, clock, connection, intent = self.fixture()
        with self.assertRaises(DomainError):
            exchange.submit_intent(intent)
        clock.advance(1)
        other = F.intent("buy-admitted-first", "buy", F.B, "fixture-buy-grant", None, 2)
        exchange.submit_intent(other)
        clock.advance(1)
        exchange.submit_intent(intent)
        self.assertEqual(self.rows(connection), [
            ("buy-admitted-first", 1), ("buy-original", 2)])
        self.assertEqual(exchange.intent(intent.intent_id).digest, intent.digest)

    def test_revoked_or_expired_original_is_not_newly_admitted_on_retry(self):
        for revoked in (False, True):
            with self.subTest(revoked=revoked):
                exchange, clock, connection, intent = self.fixture()
                with self.assertRaises(DomainError):
                    exchange.submit_intent(intent)
                if revoked:
                    exchange.revoke_authorization("fixture-buy-grant")
                else:
                    clock.now = intent.expires_at
                exchange.submit_intent(intent)
                self.assertEqual(self.rows(connection), [])
                self.assertFalse(exchange.validate_intent(intent.intent_id)["executable"])

