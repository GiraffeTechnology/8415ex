"""Authored isolated SQLite replay fixtures; not the authoritative wallet journal."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from dataclasses import asdict, replace
from exchange.gas_budget import GasBudgetRefused
from exchange.gas_reconfirmation import GasAdjustment
from exchange.gas_budget_journal import (IsolatedSQLiteGasJournal, GasJournalRefused,
    GasJournalCorrupt, GasJournalCommitUnknown, EMPTY_HEAD)
from integration.test_gas_budget import quote, facts, used


class CommitFaultConnection(sqlite3.Connection):
    fail_after_commit = False
    def commit(self):
        super().commit()
        if self.fail_after_commit:
            self.fail_after_commit = False
            raise sqlite3.OperationalError('isolated after-commit acknowledgement fault')


class GasJournalContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'isolated-gas-projection.sqlite'
        self.connection = sqlite3.connect(self.path, factory=CommitFaultConnection)
        IsolatedSQLiteGasJournal.initialize(self.connection)
        self.modes = []
        def verify(mode, kind, evidence):
            self.modes.append((mode, kind))
            return True
        self.verify = verify
        self.journal = IsolatedSQLiteGasJournal(self.connection, verify)
        self.q = quote()
        c, f = facts(self.q)
        self.open_command = {'operation': 'open', 'quote': asdict(self.q),
            'confirmation': asdict(c), 'frozen': asdict(f), 'now': 102}
        self.open_receipt = self.journal.submit('open-1', self.open_command, EMPTY_HEAD)

    def tearDown(self):
        self.connection.close()
        self.temp.cleanup()

    def append(self, identity, command):
        return self.journal.submit(identity, command, self.journal.head())

    def reserve(self, identity='reserve-1', attempt='attempt-1', bound=60):
        return self.append(identity, {'operation': 'reserve', 'budget_id': 'budget-1',
            'attempt_id': attempt, 'action': 'transfer', 'maximum_wei': bound, 'now': 110})

    def consume_failed(self):
        return self.append('consume-1', {'operation': 'reconcile', 'budget_id': 'budget-1',
            'consumption': asdict(used(amount=40, outcome='FAILED'))})

    def reopen(self):
        self.connection.close()
        self.connection = sqlite3.connect(self.path, factory=CommitFaultConnection)
        self.journal = IsolatedSQLiteGasJournal(self.connection, self.verify)

    def test_disk_reopen_preserves_consumption_and_unknown_reservation(self):
        self.reserve()
        self.consume_failed()
        self.reserve('reserve-2', 'unknown-attempt', 50)
        head = self.journal.head()
        self.reopen()
        restored = self.journal.recover('budget-1')
        self.assertEqual(restored['head'], head)
        self.assertEqual(restored['projection']['actualConsumedWei'], 40)
        self.assertEqual(restored['projection']['pendingBoundWei'], 50)
        self.assertIsNone(restored['projection']['unfreezeProposalWei'])
        self.assertFalse(restored['financialEffectsDispatched'])
        with self.assertRaises(GasBudgetRefused):
            self.append('close-unknown', {'operation': 'close', 'budget_id': 'budget-1'})
        self.assertEqual(self.journal.head(), head)

    def test_duplicate_event_returns_original_result_without_reexecution(self):
        self.reserve()
        self.modes.clear()
        repeated = self.journal.submit('open-1', self.open_command, EMPTY_HEAD)
        self.assertTrue(repeated['duplicate'])
        self.assertEqual(repeated['acceptedResult'], self.open_receipt['acceptedResult'])
        self.assertNotIn('current', [mode for mode, kind in self.modes])
        self.assertEqual(self.journal.recover('budget-1')['projection']['pendingBoundWei'], 60)

    def test_same_event_different_content_is_refused_without_append(self):
        before = self.journal.head()
        changed = dict(self.open_command, now=103)
        with self.assertRaises(GasJournalRefused):
            self.journal.submit('open-1', changed, before)
        self.assertEqual(self.journal.head(), before)

    def test_stale_head_does_not_run_current_verifier_or_append(self):
        self.reserve()
        self.modes.clear()
        command = {'operation': 'close', 'budget_id': 'budget-1'}
        before = self.journal.head()
        with self.assertRaises(GasJournalRefused):
            self.journal.submit('close-stale', command, EMPTY_HEAD)
        self.assertEqual(self.journal.head(), before)
        self.assertNotIn('current', [mode for mode, kind in self.modes])

    def test_current_bound_refusal_keeps_previous_success(self):
        before = self.journal.head()
        self.journal.verify = lambda mode, kind, evidence: mode == 'history'
        with self.assertRaises(GasBudgetRefused):
            self.reserve()
        self.assertEqual(self.journal.head(), before)
        self.assertIsNone(self.journal.lookup('reserve-1'))

    def test_commit_acknowledgement_unknown_is_looked_up_by_original_id(self):
        self.connection.fail_after_commit = True
        with self.assertRaises(GasJournalCommitUnknown):
            self.reserve()
        original = self.journal.lookup('reserve-1')
        self.assertIsNotNone(original)
        command = {'operation': 'reserve', 'budget_id': 'budget-1', 'attempt_id': 'attempt-1',
            'action': 'transfer', 'maximum_wei': 60, 'now': 110}
        repeated = self.journal.submit('reserve-1', command, EMPTY_HEAD)
        self.assertTrue(repeated['duplicate'])
        self.assertEqual(repeated['acceptedHead'], original['acceptedHead'])
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM '
            'ex_gas_projection_fixture_events WHERE event_id=?', ('reserve-1',)).fetchone()[0], 1)

    def test_corrupt_hash_or_contract_refuses_recovery(self):
        self.connection.execute('UPDATE ex_gas_projection_fixture_events SET result=? WHERE sequence=1',
                                ('{}',))
        self.connection.commit()
        with self.assertRaises(GasJournalCorrupt):
            self.journal.recover('budget-1')
        with self.assertRaises(GasJournalCorrupt):
            self.journal.lookup('open-1')

    def test_historical_proof_refusal_is_not_a_current_success(self):
        self.journal.verify = lambda mode, kind, evidence: False
        with self.assertRaises(GasJournalCorrupt):
            self.journal.recover('budget-1')

    def test_active_foreign_transaction_is_not_committed_or_rolled_back(self):
        self.connection.execute('BEGIN')
        with self.assertRaises(GasJournalRefused):
            self.journal.recover('budget-1')
        self.assertTrue(self.connection.in_transaction)
        self.connection.rollback()

    def test_quote_revision_replays_without_resetting_failed_gas(self):
        self.reserve()
        self.consume_failed()
        new = replace(self.q, quote_id='quote-2', version=2, cap_wei=160,
                      quoted_at=120, rate_observed_at=120, valid_until=220)
        confirmation, unused = facts(new)
        confirmation = replace(confirmation, confirmed_at=121)
        adjustment = GasAdjustment('adjust-1', 'budget-1', self.q.digest, new.digest,
            'buyer-1', 11155111, 40, 120, 'wallet-freeze-1', 'wallet-freeze-2', 'APPLIED')
        self.append('revise-1', {'operation': 'revise', 'budget_id': 'budget-1',
            'quote': asdict(new), 'confirmation': asdict(confirmation),
            'adjustment': asdict(adjustment), 'now': 122})
        self.reopen()
        restored = self.journal.recover('budget-1')['projection']
        self.assertEqual(restored['quoteDigest'], new.digest)
        self.assertEqual(restored['actualConsumedWei'], 40)
        self.assertEqual(restored['capWei'], 160)
        self.assertEqual(restored['unusedWei'], 120)
        self.assertEqual(restored['walletDebit'], 'NOT_RUN')
