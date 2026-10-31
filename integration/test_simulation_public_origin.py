"""Focused HTTP binding checks; no proxy activation or native acceptance."""
import http.client
import json
from pathlib import Path
import re
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from exchange.persistent_simulation_serve import create_simulation_server
from exchange.simulation_origin import canonical_public_origin


class SimulationPublicOrigin(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.servers = []

    def tearDown(self):
        for server, thread in reversed(self.servers):
            server.shutdown();thread.join(3);server.server_close();server.history.close()
        self.temp.cleanup()

    def start(self, origin=None):
        server=create_simulation_server(state_path=self.directory/('history'+str(len(self.servers))+'.sqlite'),
            port=0,commit='a'*40,tree='b'*40,registration_path='REG_DIRECT',public_origin=origin)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.servers.append((server,thread));return server

    def request(self,server,method,path,headers=(),body=None):
        conn=http.client.HTTPConnection(*server.server_address,timeout=3)
        conn.putrequest(method,path,skip_host=True,skip_accept_encoding=True)
        for name,value in headers:conn.putheader(name,value)
        if body is not None:conn.putheader('Content-Length',str(len(body.encode())))
        conn.endheaders(body.encode() if body is not None else None)
        response=conn.getresponse();data=response.read();status=response.status
        result_headers=dict(response.getheaders());conn.close();return status,result_headers,data

    def test_only_explicit_canonical_https_dns_origins_are_accepted(self):
        self.assertIsNone(canonical_public_origin(None))
        self.assertEqual(canonical_public_origin('https://8415ex.com'),'https://8415ex.com')
        for value in ('http://8415ex.com','https://8415ex.com:443','https://8415ex.com/',
                      'https://user@8415ex.com','https://8415ex.com?q=1','https://8415ex.com#x',
                      'https://127.0.0.1','https://[::1]','https://localhost','https://x.localhost',
                      'https://8415ex.com.','https://8415EX.com','https://bad-.com',
                      'https://8415ex.com\n',{},False):
            with self.subTest(value=value),self.assertRaises(ValueError):canonical_public_origin(value)

    def test_default_profile_keeps_original_loopback_host_binding(self):
        server=self.start();host=server.origin.removeprefix('http://')
        self.assertEqual(self.request(server,'GET','/demo',[('Host',host)])[0],200)
        self.assertEqual(self.request(server,'GET','/demo',[('Host','8415ex.com')])[0],421)
        self.assertTrue(server.origin.startswith('http://127.0.0.1:'))

    def test_explicit_https_origin_keeps_tcp_loopback_and_commits_original_scenario(self):
        server=self.start('https://8415ex.com')
        self.assertEqual(server.server_address[0],'127.0.0.1')
        self.assertIsNone(server.binding.gateway)
        status,_,page=self.request(server,'GET','/demo',[('Host','8415ex.com')]);self.assertEqual(status,200)
        csrf=re.search(rb'name="csrf" value="([A-Za-z0-9_-]+)"',page).group(1).decode()
        body=urlencode({'csrf':csrf,'scenario':'DEMO-01'})
        status,headers,_=self.request(server,'POST','/simulate',[
            ('Host','8415ex.com'),('Origin','https://8415ex.com'),
            ('Content-Type','application/x-www-form-urlencoded')],body)
        self.assertEqual(status,303)
        run=headers['Location'].split('id=',1)[1]
        status,_,raw=self.request(server,'GET','/evidence?id='+run,[('Host','8415ex.com')])
        self.assertEqual(status,200);value=json.loads(raw)
        self.assertTrue(value['report']['allPassed'])
        self.assertEqual(set(value['realEvidence'].values()),{'NOT_RUN'})
        self.assertIsNotNone(server.history.get(run))

    def test_host_and_origin_mismatch_duplicates_and_forwarded_values_are_refused(self):
        server=self.start('https://8415ex.com')
        for headers in ([('Host','127.0.0.1')],[('Host','evil.example')],
                        [('Host','8415ex.com'),('Host','evil.example')],
                        [('Host','evil.example'),('X-Forwarded-Host','8415ex.com')]):
            self.assertEqual(self.request(server,'GET','/demo',headers)[0],421)
        status,_,page=self.request(server,'GET','/demo',[('Host','8415ex.com')])
        csrf=re.search(rb'name="csrf" value="([A-Za-z0-9_-]+)"',page).group(1).decode()
        body=urlencode({'csrf':csrf,'scenario':'DEMO-01'})
        for origins in ([],[('Origin','https://evil.example')],[('Origin','http://8415ex.com')],
                        [('Origin','https://8415ex.com'),('Origin','https://evil.example')],
                        [('X-Forwarded-Proto','https'),('X-Forwarded-Host','8415ex.com'),('Forwarded','host=8415ex.com;proto=https')]):
            headers=[('Host','8415ex.com'),('Content-Type','application/x-www-form-urlencoded')]+origins
            self.assertEqual(self.request(server,'POST','/simulate',headers,body)[0],403)
        self.assertEqual(server.history.recent(),[])

    def test_correct_origin_does_not_replace_csrf_or_select_native_authority(self):
        server=self.start('https://8415ex.com')
        headers=[('Host','8415ex.com'),('Origin','https://8415ex.com'),('Content-Type','application/x-www-form-urlencoded')]
        status,_,_=self.request(server,'POST','/simulate',headers,urlencode({'csrf':'invalid','scenario':'DEMO-01'}))
        self.assertEqual(status,403);self.assertEqual(server.history.recent(),[])
        status,_,raw=self.request(server,'GET','/healthz',[('Host','8415ex.com')])
        self.assertEqual(status,200)
        self.assertFalse(json.loads(raw)['configuredComponents']['commandGateway'])


if __name__=='__main__':unittest.main()
