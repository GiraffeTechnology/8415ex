"""Approved-Linux definitions: file history durability, synthetic remint ports.

No actual burn/mint, financial execution or power-loss recovery is asserted.
"""
import sqlite3
from pathlib import Path
import tempfile
import unittest

from exchange import fixtures as F
from exchange.durable_operation import DurableNativeOutcomeUnknown
from exchange.remint_history import RemintHistoryStore
from exchange.remint_terms import prepare_remint_terms, RemintTermsRefused
from integration import test_remint_execution as remint_fixtures


class RemintHistoryDurabilityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = remint_fixtures.RemintExecutionTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.history = prepare_remint_terms(self.fixture.old, self.fixture.new,
            F.verify_fixture_mint, remint_fixtures.bill)["history"]

    def test_constructor_refuses_memory_or_disabled_journal_with_full_sync(self):
        connection = self.fixture.connection
        for setting in ("PRAGMA journal_mode=OFF", "PRAGMA journal_mode=MEMORY"):
            with self.subTest(setting=setting):
                connection.execute(setting)
                self.assertEqual(connection.execute("PRAGMA synchronous").fetchone()[0], 2)
                with self.assertRaisesRegex(RemintTermsRefused, "Persistent SQLite history journal"):
                    RemintHistoryStore(connection)
                self.assertFalse(connection.in_transaction)

    def test_changed_settings_refuse_before_history_write_without_changing_host_policy(self):
        connection, store = self.fixture.connection, self.fixture.history_store
        for setting in ("PRAGMA synchronous=OFF", "PRAGMA synchronous=NORMAL",
                        "PRAGMA journal_mode=OFF", "PRAGMA journal_mode=MEMORY"):
            with self.subTest(setting=setting):
                connection.execute("PRAGMA journal_mode=DELETE")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute(setting)
                before = (connection.execute("PRAGMA synchronous").fetchone()[0],
                          connection.execute("PRAGMA journal_mode").fetchone()[0])
                with self.assertRaises(RemintTermsRefused):
                    store.save(self.fixture.scope, self.history)
                self.assertIsNone(store.read(self.fixture.scope))
                self.assertEqual(connection.execute("SELECT count(*) FROM ex_remint_histories").fetchone()[0], 0)
                after = (connection.execute("PRAGMA synchronous").fetchone()[0],
                         connection.execute("PRAGMA journal_mode").fetchone()[0])
                self.assertEqual(after, before)
                self.assertFalse(connection.in_transaction)

    def test_previously_saved_history_remains_readable_without_new_write_authority(self):
        store, connection = self.fixture.history_store, self.fixture.connection
        before = store.save(self.fixture.scope, self.history)
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA journal_mode=MEMORY")
        after = store.read(self.fixture.scope)
        self.assertEqual(after, before)
        self.assertEqual(after["businessAcceptance"], "NOT_ESTABLISHED")
        self.assertFalse(after["replayAllowed"])
        with self.assertRaises(RemintTermsRefused):
            store.save(self.fixture.scope, self.history)

    def test_separate_history_connection_refusal_keeps_claim_unknown_without_remint(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        history_connection = sqlite3.connect(str(Path(directory.name) / "history.sqlite"))
        self.addCleanup(history_connection.close)
        RemintHistoryStore.initialize(history_connection)
        self.fixture.history_store = RemintHistoryStore(history_connection)
        history_connection.execute("PRAGMA journal_mode=MEMORY")
        calls = []
        with self.assertRaises(DurableNativeOutcomeUnknown):
            self.fixture.invoke(lambda *args: calls.append(args))
        self.assertEqual(calls, [])
        claim = self.fixture.journal.lookup(self.fixture.scope["nativeOperationId"])
        self.assertEqual(claim["status"], "UNKNOWN")
        self.assertFalse(claim["replayAllowed"])
        self.assertIsNone(self.fixture.history_store.read(self.fixture.scope))
