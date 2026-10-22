"""Synthetic HTTP-to-original-Oracle as-of composition; no live source."""
from copy import deepcopy
from email.message import Message
import json
import unittest
from unittest.mock import patch

from exchange.errors import DomainError
from exchange.oracle_http_transport import OracleHTTPTransport
from exchange.oracle_projection_join import OracleProjectionJoin
from integration import test_oracle_as_of_join as original


class OracleAsOfHTTPCompositionContracts(unittest.TestCase):
    def setUp(self):
        self.fixture = original.OracleAsOfJoinTests("runTest")
        self.fixture.setUp()
        self.requests, self.verified = [], []
        port, requests = self.fixture.port, self.requests
        class Socket:
            def settimeout(self, timeout):
                pass
        class Response:
            def __init__(self, status, body):
                self.status = status
                self.raw = json.dumps(body).encode()
                self.offset = 0
                self.headers = Message()
                self.headers["Content-Type"] = "application/json"
                self.headers["Content-Length"] = str(len(self.raw))
            def getheader(self, key, default=None):
                return self.headers.get(key, default)
            def read1(self, count):
                value = self.raw[self.offset:self.offset+count]
                self.offset += len(value)
                return value
            def close(self):
                pass
        class Connection:
            def __init__(self, *args, **kwargs):
                self.sock = Socket()
            def connect(self):
                pass
            def request(self, method, path, headers):
                requests.append((method,path,deepcopy(headers)))
                self.method, self.path = method,path
            def getresponse(self):
                status, body = port(self.method,self.path)
                return Response(status,body)
            def close(self):
                pass
        self.connection = Connection
        self.transport = OracleHTTPTransport("http://127.0.0.1:12345")
        self.join = OracleProjectionJoin(original.SOURCE,self.transport,
            lambda binding,facts:self.verified.append(deepcopy(facts)) or True)

    def inspect(self, as_of="110", cutoff="105"):
        with patch("exchange.oracle_http_transport.http.client.HTTPConnection",
                   side_effect=self.connection):
            return self.join.inspect_as_of(self.fixture.binding,as_of,cutoff)

    def test_original_http_as_of_selection_and_canonical_join_preserve_six_read_identity(self):
        facts = self.inspect()
        self.assertEqual(len(self.requests),6)
        self.assertEqual(self.requests[0][:2],
            ("GET",original.PREFIX+"/19/entry/as-of/110"))
        self.assertEqual([row[:2] for row in self.requests],self.fixture.port.calls)
        self.assertEqual(len(self.verified),1)
        self.assertEqual(facts["bindingDigest"],self.fixture.binding.binding_digest)
        self.assertEqual(facts["entry"]["version"],"2")
        self.assertEqual(facts["asOf"],"110")
        self.assertFalse(facts["atomicSettlementAuthority"])
        self.assertFalse(facts["fundsDispatched"])
        self.assertFalse(facts["holderWritten"])
        self.assertFalse(facts["finalityWritten"])
        for method,path,headers in self.requests:
            self.assertEqual(method,"GET")
            self.assertEqual(headers,{"Accept":"application/json","Accept-Encoding":"identity"})

    def test_finality_cutoff_and_holder_observations_are_independent_after_transport(self):
        facts = self.inspect(cutoff="99")
        self.assertFalse(facts["withinCutoff"])
        self.assertFalse(facts["finalAsOf"])
        self.assertEqual(facts["entry"]["effectiveAt"],"100")
        self.assertEqual(facts["holderAsOf"],self.fixture.port.entry["holder"])
        self.assertEqual(len(self.verified),1)
        self.assertFalse(facts["atomicSettlementAuthority"])
        self.assertFalse(facts["fundsDispatched"])

    def test_refused_as_of_http_selection_never_falls_back_to_latest_or_version(self):
        self.fixture.port.as_of_status = 404
        with self.assertRaises(DomainError):
            self.inspect()
        self.assertEqual(len(self.requests),1)
        self.assertEqual(self.requests[0][:2],
            ("GET",original.PREFIX+"/19/entry/as-of/110"))
        self.assertEqual(self.verified,[])

    def test_inconsistent_holder_and_invalid_instant_cannot_reach_mapping_or_writes(self):
        def different_holder(path,body):
            if "/holder/as-of/" in path:
                body["holder"] = original.B
            return body
        self.fixture.port.mutate = different_holder
        with self.assertRaises(DomainError):
            self.inspect()
        self.assertEqual(self.verified,[])
        self.assertTrue(all(method=="GET" for method,_,_ in self.requests))
        self.requests.clear()
        with self.assertRaises(DomainError):
            self.inspect(as_of="0110")
        self.assertEqual(self.requests,[])
