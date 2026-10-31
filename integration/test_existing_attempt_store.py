"""Existing-only local attempt binding; no host initialization or Wallet calls."""
import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase
from exchange.wallet_execution_attempts import WalletExecutionAttempts

class ExistingAttemptStoreTests(TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'original.sqlite'
        self.binding={'origin':'https://wallet.invalid','tenant':'original','account':'a','chainId':11155111}
        self.request={'taskDigest':'original-task','operationId':'original-operation','nonce':1}
    def test_missing_path_refused_without_creation(self):
        with self.assertRaises(ValueError):WalletExecutionAttempts.open_existing(str(self.path))
        self.assertFalse(self.path.exists())
    def test_wrong_existing_schema_refused_without_initialization(self):
        with sqlite3.connect(self.path) as db:db.execute('CREATE TABLE unrelated (value TEXT)')
        before=self.path.read_bytes()
        with self.assertRaises(ValueError):WalletExecutionAttempts.open_existing(str(self.path))
        self.assertEqual(self.path.read_bytes(),before)
    def test_original_claim_barrier_survives_existing_open_and_restart(self):
        original=WalletExecutionAttempts(str(self.path))
        self.assertTrue(original.claim(self.binding,self.request));before=self.path.read_bytes()
        existing=WalletExecutionAttempts.open_existing(str(self.path))
        self.assertEqual(self.path.read_bytes(),before)
        self.assertFalse(existing.claim(self.binding,self.request))
        self.assertFalse(WalletExecutionAttempts.open_existing(str(self.path)).claim(self.binding,{**self.request,'nonce':2}))
        self.assertTrue(existing.claim(self.binding,{**self.request,'operationId':'new-original-operation'}))
    def test_removed_store_is_not_recreated_by_claim(self):
        WalletExecutionAttempts(str(self.path));existing=WalletExecutionAttempts.open_existing(str(self.path));self.path.unlink()
        with self.assertRaises(ValueError):existing.claim(self.binding,self.request)
        self.assertFalse(self.path.exists())
    def test_replaced_store_refused_even_when_schema_matches(self):
        WalletExecutionAttempts(str(self.path));existing=WalletExecutionAttempts.open_existing(str(self.path))
        replacement=self.path.with_name('replacement.sqlite');WalletExecutionAttempts(str(replacement));replacement.replace(self.path)
        before=self.path.read_bytes()
        with self.assertRaises(ValueError):existing.claim(self.binding,self.request)
        self.assertEqual(self.path.read_bytes(),before)
    def test_symlink_refused(self):
        WalletExecutionAttempts(str(self.path));link=self.path.with_name('alias.sqlite');link.symlink_to(self.path)
        with self.assertRaises(ValueError):WalletExecutionAttempts.open_existing(str(link))
    def test_uri_metacharacters_are_literal_path_not_connection_options(self):
        path=self.path.with_name('attempts?mode=memory#x.sqlite');WalletExecutionAttempts(str(path))
        existing=WalletExecutionAttempts.open_existing(str(path))
        self.assertTrue(existing.claim(self.binding,self.request))
        self.assertFalse(WalletExecutionAttempts.open_existing(str(path)).claim(self.binding,self.request))
    def test_existing_store_trigger_is_refused_without_mutation(self):
        WalletExecutionAttempts(str(self.path))
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TRIGGER suppress_attempt BEFORE INSERT ON ex_wallet_execution_attempts BEGIN SELECT RAISE(IGNORE); END')
        before=self.path.read_bytes()
        with self.assertRaises(ValueError):WalletExecutionAttempts.open_existing(str(self.path))
        self.assertEqual(self.path.read_bytes(),before)
    def test_legacy_claim_cannot_report_success_when_trigger_discards_barrier(self):
        attempts=WalletExecutionAttempts(str(self.path))
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TRIGGER suppress_attempt BEFORE INSERT ON ex_wallet_execution_attempts BEGIN SELECT RAISE(IGNORE); END')
        with self.assertRaises(ValueError):attempts.claim(self.binding,self.request)
