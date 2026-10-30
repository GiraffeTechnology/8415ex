"""Durable history for the existing, explicitly local simulation workbench.

This stores the original canonical scenario records. It does not supply native
authority, wallet sessions, signatures, registrations or a command gateway.
"""
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import threading

from exchange.demo_ui import MAX_RUNS
from exchange.workbench import WorkbenchHandler, WorkbenchServer
from exchange.simulation_origin import canonical_public_origin
from urllib.parse import urlsplit


MAX_RECORD = 2 * 1024 * 1024
APPLICATION_ID = 0x4558534D
SCHEMA = '8415ex-local-simulation-history/1'
REAL_FIELDS = frozenset(('deployment', 'provider', 'signatures', 'chain', 'transactions'))


class SimulationStateUnavailable(OSError):
    def __init__(self):
        super().__init__('EX_SIMULATION_STATE_UNAVAILABLE')


def canonical_record(record):
    if (type(record) is not dict or record.get('schema') != '8415ex-demo-ui/1'
            or record.get('evidenceKind') != 'LOCAL_SIMULATION'
            or type(record.get('runId')) is not str
            or re.fullmatch(r'demo-[0-9a-f]{32}', record['runId']) is None
            or type(record.get('source')) is not dict
            or any(type(record['source'].get(k)) is not str
                   or re.fullmatch('[0-9a-f]{40}', record['source'][k]) is None
                   for k in ('commit', 'tree'))
            or type(record.get('realEvidence')) is not dict
            or set(record['realEvidence']) != REAL_FIELDS
            or any(v != 'NOT_RUN' for v in record['realEvidence'].values())
            or type(record.get('report')) is not dict):
        raise SimulationStateUnavailable()
    try:
        raw = json.dumps(record, ensure_ascii=True, allow_nan=False,
                         sort_keys=True, separators=(',', ':')).encode()
    except (TypeError, ValueError, RecursionError):
        raise SimulationStateUnavailable() from None
    if len(raw) > MAX_RECORD:
        raise SimulationStateUnavailable()
    return raw


class SQLiteSimulationHistory:
    """Private, existing-file-safe history; no credential or authority content."""
    def __init__(self, path):
        self.path = Path(path)
        self.connection = None
        self.fd = None
        self.lock = threading.RLock()
        try:
            if (not self.path.is_absolute() or self.path.resolve() != self.path
                    or self.path.parent.is_symlink()):
                raise SimulationStateUnavailable()
            parent = self.path.parent.stat()
            if (parent.st_uid != os.geteuid() or parent.st_mode & 0o077
                    or not stat.S_ISDIR(parent.st_mode)):
                raise SimulationStateUnavailable()
            created = False
            try:
                self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                created = True
            except FileExistsError:
                self.fd = os.open(self.path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
            self.identity = os.fstat(self.fd)
            self._check_file()
            if not created:
                # Read-only recognition first: opening an unrelated database
                # must not trigger a writable hot-journal recovery.
                probe = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=2)
                try:
                    self._verify_schema(probe)
                finally:
                    probe.close()
                self._check_file()
            self.connection = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True,
                                             timeout=2, check_same_thread=False)
            self.connection.execute('PRAGMA synchronous=FULL')
            self.connection.execute('PRAGMA busy_timeout=2000')
            if created:
                with self.connection:
                    self.connection.execute('PRAGMA application_id=' + str(APPLICATION_ID))
                    self.connection.execute('PRAGMA user_version=1')
                    self.connection.execute('CREATE TABLE simulation_meta (name TEXT PRIMARY KEY, value TEXT NOT NULL)')
                    self.connection.execute('INSERT INTO simulation_meta VALUES (?,?)', ('schema', SCHEMA))
                    self.connection.execute('CREATE TABLE simulation_runs (sequence INTEGER PRIMARY KEY, run_id TEXT NOT NULL UNIQUE, record BLOB NOT NULL, sha256 TEXT NOT NULL)')
            self._verify_schema(self.connection)
            # Do not change even a storage pragma on an unrelated existing DB.
            self.connection.execute('PRAGMA max_page_count=16384')
            self._check_file()
        except Exception:
            self.close()
            raise SimulationStateUnavailable() from None

    @staticmethod
    def _verify_schema(connection):
        if (connection.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID
                or connection.execute('PRAGMA user_version').fetchone()[0] != 1
                or connection.execute('SELECT value FROM simulation_meta WHERE name=?', ('schema',)).fetchone() != (SCHEMA,)):
            raise SimulationStateUnavailable()

    def _check_file(self):
        s = self.path.lstat()
        if (not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid != os.geteuid()
                or stat.S_IMODE(s.st_mode) != 0o600 or (s.st_dev, s.st_ino) != (self.identity.st_dev, self.identity.st_ino)):
            raise SimulationStateUnavailable()

    def _decode(self, row):
        if row is None:
            return None
        key, raw, digest = row
        if type(raw) is not bytes or len(raw) > MAX_RECORD or hashlib.sha256(raw).hexdigest() != digest:
            raise SimulationStateUnavailable()
        value = json.loads(raw)
        if canonical_record(value) != raw or value['runId'] != key:
            raise SimulationStateUnavailable()
        return value

    def put(self, record):
        raw = canonical_record(record)
        try:
            with self.lock:
                self._check_file()
                with self.connection:
                    self.connection.execute('INSERT INTO simulation_runs(run_id,record,sha256) VALUES (?,?,?)',
                        (record['runId'], raw, hashlib.sha256(raw).hexdigest()))
                self._check_file()
        except Exception:
            raise SimulationStateUnavailable() from None

    def get(self, key):
        if type(key) is not str or re.fullmatch(r'demo-[0-9a-f]{32}', key) is None:
            return None
        try:
            with self.lock:
                self._check_file()
                row = self.connection.execute('SELECT run_id,record,sha256 FROM simulation_runs WHERE run_id=?', (key,)).fetchone()
                return self._decode(row)
        except Exception:
            raise SimulationStateUnavailable() from None

    def recent(self):
        try:
            with self.lock:
                self._check_file()
                rows = self.connection.execute('SELECT run_id,record,sha256 FROM simulation_runs ORDER BY sequence DESC LIMIT ?', (MAX_RUNS,)).fetchall()
                return [self._decode(row) for row in reversed(rows)]
        except Exception:
            raise SimulationStateUnavailable() from None

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


class DurableRunView(OrderedDict):
    def __init__(self, history):
        self.history = history
        super().__init__((r['runId'], r) for r in history.recent())

    def get(self, key, default=None):
        value = super().get(key)
        if value is None:
            value = self.history.get(key)
        return default if value is None else value


class PersistentSimulationHandler(WorkbenchHandler):
    def host_ok(self):
        if self.server.public_origin is None:
            return super().host_ok()
        return self.headers.get_all('Host', []) == [urlsplit(self.server.public_origin).netloc]

    def shell(self, content):
        html = super().shell(content)
        before = 'State exists in this process only. Shutting down discards these runs.'
        if before not in html:
            raise SimulationStateUnavailable()
        return html.replace(before, 'Simulation run history is stored locally and retained across process restarts.', 1)

    def do_GET(self):
        try:
            return super().do_GET()
        except SimulationStateUnavailable:
            self.send_body(503, 'Local simulation history is unavailable; no successful recovery is asserted.')

    def do_POST(self):
        if (self.server.public_origin is not None
                and self.headers.get_all('Origin', []) != [self.server.public_origin]):
            self.send_body(403, 'Configured HTTPS origin required.')
            return
        try:
            return super().do_POST()
        except SimulationStateUnavailable:
            self.send_body(503, 'Local simulation history could not be saved; no durable success is asserted.')


class PersistentSimulationWorkbench(WorkbenchServer):
    """Same local simulation and checked HTTP controls, with durable run history."""
    def __init__(self, binding, *, history, port, commit, tree, reference_feed=None,
                 public_origin=None):
        self.public_origin = canonical_public_origin(public_origin)
        if type(history) is not SQLiteSimulationHistory:
            raise SimulationStateUnavailable()
        self.history = history
        cache = DurableRunView(history)
        super().__init__(binding, port=port, commit=commit, tree=tree, reference_feed=reference_feed)
        self.runs = cache
        self.RequestHandlerClass = PersistentSimulationHandler

    @property
    def origin(self):
        return self.public_origin if self.public_origin is not None else super().origin

    def simulate(self, scenario_id):
        previous = OrderedDict(self.runs)
        record = super().simulate(scenario_id)
        try:
            self.history.put(record)
        except SimulationStateUnavailable:
            self.runs.clear()
            self.runs.update(previous)
            raise
        return record
