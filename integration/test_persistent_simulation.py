"""Durable existing simulation profile, not native authority acceptance."""
from copy import deepcopy
import hashlib
import http.client
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlencode, urlsplit, parse_qs

from exchange.persistent_simulation import SQLiteSimulationHistory, SimulationStateUnavailable
from exchange.persistent_simulation_serve import create_simulation_server, configured_reference
from exchange.eia_wti_spot_table import SCOPE, SOURCE_URL


def record(number, commit='a'*40):
    return {'schema':'8415ex-demo-ui/1','runId':'demo-'+format(number,'032x'),
        'evidenceKind':'LOCAL_SIMULATION','source':{'commit':commit,'tree':'b'*40},
        'scope':'synthetic unit record only','report':{'scenarios':[], 'allPassed':False},
        'realEvidence':dict.fromkeys(('deployment','provider','signatures','chain','transactions'),'NOT_RUN')}


class PersistentSimulationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.path = self.directory/'history.sqlite'

    def start(self, commit='a'*40):
        server = create_simulation_server(state_path=self.path, port=0,
            commit=commit, tree='b'*40, registration_path='REG_DIRECT')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def close():
            server.shutdown();thread.join(3);server.server_close();server.history.close()
        return server, close

    def request(self, server, method, path, body=None, headers=None):
        c = http.client.HTTPConnection(*server.server_address, timeout=5)
        try:
            c.request(method,path,body,headers or {})
            r=c.getresponse();return r.status,dict(r.getheaders()),r.read()
        finally:c.close()

    def simulate(self, server, **extra):
        status,_,html=self.request(server,'GET','/demo');self.assertEqual(status,200)
        token=re.search(rb'name="csrf" value="([A-Za-z0-9_-]+)"',html).group(1).decode()
        form={'csrf':token,'scenario':'DEMO-01'};form.update(extra)
        return self.request(server,'POST','/simulate',urlencode(form),
            {'Origin':server.origin,'Content-Type':'application/x-www-form-urlencoded'})

    def test_actual_http_scenario_survives_restart_with_original_projection(self):
        server,close=self.start()
        try:
            status,headers,_=self.simulate(server);self.assertEqual(status,303)
            run=parse_qs(urlsplit(headers['Location']).query)['id'][0]
            status,_,before=self.request(server,'GET','/evidence?id='+run)
            self.assertEqual(status,200)
            self.assertEqual(json.loads(before)['realEvidence']['signatures'],'NOT_RUN')
        finally:close()
        server,close=self.start(commit='c'*40)
        try:
            status,_,after=self.request(server,'GET','/evidence?id='+run)
            self.assertEqual(status,200);self.assertEqual(after,before)
            _,_,home=self.request(server,'GET','/demo')
            self.assertIn(b'retained across process restarts',home)
            self.assertNotIn(b'Shutting down discards',home)
            _,_,health=self.request(server,'GET','/healthz')
            self.assertFalse(json.loads(health)['configuredComponents']['commandGateway'])
        finally:close()

    def test_failed_durable_commit_never_redirects_success_or_publishes_cache(self):
        server,close=self.start()
        try:
            with patch.object(server.history,'put',side_effect=SimulationStateUnavailable()):
                status,_,body=self.simulate(server)
            self.assertEqual(status,503);self.assertIn(b'no durable success',body)
            self.assertEqual(len(server.runs),0);self.assertEqual(server.history.recent(),[])
        finally:close()

    def test_original_host_origin_csrf_and_no_outcome_controls_remain(self):
        server,close=self.start()
        try:
            status,_,_=self.request(server,'GET','/healthz',headers={'Host':'unapproved.invalid'})
            self.assertEqual(status,421)
            status,_,_=self.request(server,'POST','/simulate','csrf=bad&scenario=DEMO-01',
                {'Origin':'https://unapproved.invalid','Content-Type':'application/x-www-form-urlencoded'})
            self.assertEqual(status,403)
            status,_,_=self.simulate(server,outcome='passed');self.assertEqual(status,400)
            self.assertEqual(server.history.recent(),[])
        finally:close()

    def test_old_run_ids_remain_durable_beyond_the_original_cache_bound(self):
        history=SQLiteSimulationHistory(self.path)
        try:
            for i in range(1,19):history.put(record(i))
            self.assertEqual(len(history.recent()),16)
            self.assertEqual(history.get(record(1)['runId']),record(1))
        finally:history.close()
        history=SQLiteSimulationHistory(self.path)
        try:self.assertEqual(history.get(record(1)['runId']),record(1))
        finally:history.close()

    def test_native_acceptance_claims_and_duplicate_history_rewrites_are_refused(self):
        history=SQLiteSimulationHistory(self.path)
        try:
            history.put(record(1))
            changed=record(2);changed['realEvidence']['chain']='PASS'
            with self.assertRaises(SimulationStateUnavailable):history.put(changed)
            changed=record(1);changed['report']={'invented':'replacement'}
            with self.assertRaises(SimulationStateUnavailable):history.put(changed)
            self.assertEqual(history.get(record(1)['runId']),record(1))
        finally:history.close()

    def test_corrupt_records_are_not_returned_as_recovered_success(self):
        history=SQLiteSimulationHistory(self.path)
        try:
            history.put(record(1))
            with history.connection:history.connection.execute('UPDATE simulation_runs SET record=?',(b'{}',))
            with self.assertRaises(SimulationStateUnavailable):history.get(record(1)['runId'])
        finally:history.close()

    def test_unrelated_existing_database_and_non_database_are_never_initialized(self):
        connection=sqlite3.connect(self.path);connection.execute('CREATE TABLE original(x)');connection.close()
        self.path.chmod(0o600)
        before=self.path.read_bytes()
        connect=sqlite3.connect
        with patch('exchange.persistent_simulation.sqlite3.connect',wraps=connect) as opened:
            with self.assertRaises(SimulationStateUnavailable):SQLiteSimulationHistory(self.path)
        self.assertEqual(opened.call_count,1)
        self.assertIn('?mode=ro',opened.call_args.args[0])
        self.assertEqual(self.path.read_bytes(),before)
        other=self.directory/'unknown.dat';other.write_bytes(b'original unique non-database bytes')
        other.chmod(0o600)
        with self.assertRaises(SimulationStateUnavailable):SQLiteSimulationHistory(other)
        self.assertEqual(other.read_bytes(),b'original unique non-database bytes')

    def test_unsafe_file_symlink_and_replaced_inode_are_refused_without_repair(self):
        history=SQLiteSimulationHistory(self.path);history.put(record(1))
        original=self.directory/'preserved.sqlite';self.path.rename(original)
        self.path.write_bytes(b'foreign replacement');self.path.chmod(0o600)
        try:
            with self.assertRaises(SimulationStateUnavailable):history.get(record(1)['runId'])
            self.assertEqual(self.path.read_bytes(),b'foreign replacement')
        finally:history.close()
        link=self.directory/'link.sqlite';link.symlink_to(original)
        with self.assertRaises(SimulationStateUnavailable):SQLiteSimulationHistory(link)
        original.chmod(0o644)
        with self.assertRaises(SimulationStateUnavailable):SQLiteSimulationHistory(original)
        self.assertEqual(original.stat().st_mode&0o777,0o644)

    def test_existing_source_record_is_not_relabelled_as_new_running_source(self):
        history=SQLiteSimulationHistory(self.path)
        try:history.put(record(1,commit='a'*40))
        finally:history.close()
        history=SQLiteSimulationHistory(self.path)
        try:
            value=history.get(record(1)['runId'])
            self.assertEqual(value['source']['commit'],'a'*40)
            self.assertEqual(value['realEvidence'],record(1)['realEvidence'])
        finally:history.close()

    def test_original_reference_decoder_is_pinned_and_does_not_fetch_on_composition(self):
        config={'version':1,'policy':{**SCOPE,'sourceURL':SOURCE_URL,'sourceTimezone':'unknown',
            'pollSeconds':3600,'maxSourceAgeSeconds':86400,'maxClockSkewSeconds':0},
            'reader':{'timeout_seconds':1,'user_agent':'simulation-unit-test',
                'minimum_fetch_seconds':3600,'failure_backoff_seconds':3600}}
        path=self.directory/'reference.json';path.write_text(json.dumps(config))
        with self.assertRaises(ValueError):configured_reference(path,'0'*64)
        with patch('socket.create_connection',side_effect=AssertionError('no construction fetch')):
            feed=configured_reference(path,hashlib.sha256(path.read_bytes()).hexdigest())
        try:
            observation=feed.snapshot();self.assertEqual(observation['status'],'unavailable')
            self.assertFalse(observation['executableOrder'])
        finally:feed.close()


if __name__=='__main__':unittest.main()
