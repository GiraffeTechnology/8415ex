"""Isolated SQLite reference adapter for EX gas replay metadata only.

No connection, schema, wallet operation or network call is created on import.
"""
from hashlib import sha256
import json
import sqlite3
from .gas_budget import GasQuote, FeeSample, BuyerConfirmation, GasFreeze, GasConsumption
from .gas_reconfirmation import RevisableGasBudgetBook, GasAdjustment


CONTRACT = 'gas-projection-48f8ffe6-894b83b4/1'
EMPTY_HEAD = '0' * 64


class GasJournalRefused(ValueError):
    pass


class GasJournalCorrupt(GasJournalRefused):
    pass


class GasJournalCommitUnknown(RuntimeError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _quote(value):
    data = dict(value)
    data['actions'] = tuple(data['actions'])
    data['samples'] = tuple(FeeSample(**sample) for sample in data['samples'])
    return GasQuote(**data)


def _apply(book, command):
    if type(command) is not dict:
        raise GasJournalRefused('command object required')
    operation = command.get('operation')
    fields = {'open': {'quote', 'confirmation', 'frozen', 'now'},
              'reserve': {'budget_id', 'attempt_id', 'action', 'maximum_wei', 'now'},
              'reconcile': {'budget_id', 'consumption'},
              'revise': {'budget_id', 'quote', 'confirmation', 'adjustment', 'now'},
              'close': {'budget_id'}}
    if operation not in fields or set(command) != fields[operation] | {'operation'}:
        raise GasJournalRefused('unknown operation or unexpected command fields')
    if operation == 'open':
        return book.open(_quote(command['quote']), BuyerConfirmation(**command['confirmation']),
                         GasFreeze(**command['frozen']), command['now'])
    if operation == 'reserve':
        return book.reserve(command['budget_id'], command['attempt_id'], command['action'],
                            command['maximum_wei'], command['now'])
    if operation == 'reconcile':
        return book.reconcile(command['budget_id'], GasConsumption(**command['consumption']))
    if operation == 'revise':
        return book.revise(command['budget_id'], _quote(command['quote']),
            BuyerConfirmation(**command['confirmation']), GasAdjustment(**command['adjustment']),
            command['now'])
    return book.close(command['budget_id'])


def _event_hash(sequence, identity, command, result, previous):
    return sha256(_canonical([CONTRACT, sequence, identity, command, result, previous]).encode('utf-8')).hexdigest()


class IsolatedSQLiteGasJournal:
    """Own this connection exclusively. Verification callbacks must be read-only.

    verify(mode, kind, evidence): mode is history or current. Historical proof
    validation is distinct from fresh grant, balance and send-bound validation.
    The journal never dispatches any financial effect, including during replay.
    """
    def __init__(self, connection, verify):
        if not isinstance(connection, sqlite3.Connection) or not callable(verify):
            raise GasJournalRefused('explicit isolated test connection and verifier required')
        self.connection = connection
        self.verify = verify
        self._clean()

    def _clean(self):
        if self.connection.in_transaction:
            raise GasJournalRefused('connection already has an active transaction')

    @staticmethod
    def initialize(connection):
        """Explicit schema initialization for an isolated reference/test connection only."""
        if not isinstance(connection, sqlite3.Connection) or connection.in_transaction:
            raise GasJournalRefused('clean existing dedicated connection required')
        connection.execute('CREATE TABLE ex_gas_projection_fixture_events ('
            'sequence INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE, '
            'command TEXT NOT NULL, result TEXT NOT NULL, previous_hash TEXT NOT NULL, '
            'event_hash TEXT NOT NULL, contract TEXT NOT NULL)')
        connection.commit()

    def _rows(self):
        rows = self.connection.execute('SELECT sequence,event_id,command,result,previous_hash,'
            'event_hash,contract FROM ex_gas_projection_fixture_events ORDER BY sequence').fetchall()
        previous = EMPTY_HEAD
        for expected, row in enumerate(rows, 1):
            sequence, identity, command, result, before, after, contract = row
            if (sequence != expected or contract != CONTRACT or before != previous
                    or after != _event_hash(sequence, identity, command, result, before)):
                raise GasJournalCorrupt('journal sequence, contract or hash chain mismatch')
            previous = after
        return rows

    def _project(self, rows):
        book = RevisableGasBudgetBook(lambda kind, evidence: self.verify('history', kind, evidence))
        for row in rows:
            try:
                result = _apply(book, json.loads(row[2]))
                if _canonical(result) != row[3]:
                    raise GasJournalCorrupt('stored result differs from replay')
            except Exception as error:
                raise GasJournalCorrupt('historical event ' + str(row[0])
                    + ' refused: ' + type(error).__name__) from None
        return book

    def head(self):
        self._clean()
        rows = self._rows()
        return rows[-1][5] if rows else EMPTY_HEAD

    def recover(self, budget_id):
        self._clean()
        self.connection.execute('BEGIN')
        try:
            rows = self._rows()
            result = self._project(rows).snapshot(budget_id)
            return {'head': rows[-1][5] if rows else EMPTY_HEAD, 'projection': result,
                    'financialEffectsDispatched': False}
        finally:
            self.connection.rollback()

    def lookup(self, event_id):
        """Reconcile an outcome-unknown append by its original event ID."""
        self._clean()
        self.connection.execute('BEGIN')
        try:
            rows = self._rows()
            self._project(rows)
            matches = [row for row in rows if row[1] == event_id]
            if not matches:
                return None
            row = matches[0]
            return {'eventId': event_id, 'acceptedResult': json.loads(row[3]),
                    'acceptedHead': row[5], 'financialEffectsDispatched': False}
        finally:
            self.connection.rollback()

    def submit(self, event_id, command, expected_head):
        self._clean()
        if (type(event_id) is not str or not event_id.strip() or len(event_id) > 256
                or any(ord(c) < 32 for c in event_id)):
            raise GasJournalRefused('stable bounded event ID required')
        payload = _canonical(command)
        if len(payload.encode('utf-8')) > 1048576:
            raise GasJournalRefused('isolated reference command size limit exceeded')
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            rows = self._rows()
            book = self._project(rows)
            for row in rows:
                if row[1] == event_id:
                    if row[2] != payload:
                        raise GasJournalRefused('same event ID with different content')
                    receipt = {'eventId': event_id, 'acceptedResult': json.loads(row[3]),
                               'acceptedHead': row[5], 'duplicate': True,
                               'financialEffectsDispatched': False}
                    self.connection.rollback()
                    return receipt
            current_head = rows[-1][5] if rows else EMPTY_HEAD
            if expected_head != current_head:
                raise GasJournalRefused('projection head changed; reread original state')
            book.verify = lambda kind, evidence: self.verify('current', kind, evidence)
            result = _canonical(_apply(book, json.loads(payload)))
            sequence = len(rows) + 1
            after = _event_hash(sequence, event_id, payload, result, current_head)
            self.connection.execute('INSERT INTO ex_gas_projection_fixture_events '
                '(sequence,event_id,command,result,previous_hash,event_hash,contract) '
                'VALUES (?,?,?,?,?,?,?)',
                (sequence, event_id, payload, result, current_head, after, CONTRACT))
        except BaseException:
            self.connection.rollback()
            raise
        try:
            self.connection.commit()
        except Exception:
            raise GasJournalCommitUnknown('append outcome unknown; query original event ID') from None
        return {'eventId': event_id, 'acceptedResult': json.loads(result),
                'acceptedHead': after, 'duplicate': False, 'financialEffectsDispatched': False}
