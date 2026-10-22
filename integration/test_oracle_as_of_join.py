"""Synthetic existing Oracle as-of route and canonical join definitions."""
from copy import deepcopy
from email.message import Message
import json
import unittest
from unittest.mock import patch

from exchange.errors import DomainError
from exchange.model import Asset
from exchange.settlement import EscrowPosition
from exchange.principal_journal_contract import PrincipalBinding
from exchange.oracle_projection_join import OracleProjectionJoin, PREFIX
from exchange.oracle_http_transport import OracleHTTPTransport, OracleHTTPRefused

A, B = "0x" + "1" * 40, "0x" + "2" * 40
TOKEN, NFT = "0x" + "3" * 40, "0x" + "4" * 40
SOURCE = {"chainId": "11155111", "contract": "0x" + "5" * 40,
          "registerId": "0x" + "6" * 64}


class OriginalReadPort:
    def __init__(self):
        self.calls = []
        self.entry = dict(version="2", holder=A, effectiveAt="100", supersededAt="120",
                          recordCommitment="0x" + "7" * 64,
                          previousCommitment="0x" + "8" * 64,
                          registryReference="0x" + "9" * 64)
        self.mutate = lambda path, body: body
        self.counts = ["3", "3"]
        self.as_of_status = 200

    def __call__(self, method, path):
        self.calls.append((method, path))
        body = {"tokenId": "19", "source": deepcopy(SOURCE)}
        status = 200
        if path == PREFIX + "/19":
            body.update(registerId=SOURCE["registerId"], entryCount=self.counts.pop(0))
        elif "/entry/as-of/" in path:
            body.update(instant=path.rsplit("/", 1)[1], entry=deepcopy(self.entry))
            status = self.as_of_status
        elif path == PREFIX + "/19/entry/version/2":
            body["entry"] = deepcopy(self.entry)
        elif "/holder/as-of/" in path:
            body.update(instant=path.rsplit("/", 1)[1], holder=self.entry["holder"])
        elif "/finality/as-of/" in path:
            body.update(instant=path.rsplit("/", 1)[1], final=False)
        else:
            raise AssertionError("unexpected original route")
        return status, self.mutate(path, body)


class OracleAsOfJoinTests(unittest.TestCase):
    def setUp(self):
        self.binding = PrincipalBinding(
            EscrowPosition("escrow-3", "receipt-1", 3, A, B, TOKEN, 10),
            Asset(11155111, NFT, 19), "transfer-3", TOKEN, 6, "native-op-3", "journal-3")
        self.port = OriginalReadPort()
        self.verified = []
        self.join = OracleProjectionJoin(SOURCE, self.port, self.verify)

    def verify(self, binding, facts):
        self.verified.append(deepcopy(facts))
        return True

    def inspect(self, **changes):
        values = dict(as_of="110", cutoff="105")
        values.update(changes)
        return self.join.inspect_as_of(self.binding, **values)

    def test_original_as_of_selection_then_bounded_canonical_join(self):
        facts = self.inspect()
        self.assertEqual(self.port.calls[0], ("GET", PREFIX + "/19/entry/as-of/110"))
        self.assertEqual(len(self.port.calls), 6)
        self.assertEqual(facts["entry"]["version"], "2")
        self.assertEqual(len(self.verified), 1)
        self.assertFalse(facts["atomicSettlementAuthority"])
        self.assertFalse(facts["fundsDispatched"])
        self.assertFalse(facts["holderWritten"])
        self.assertFalse(facts["finalityWritten"])

    def test_as_of_and_cutoff_are_separate_facts(self):
        facts = self.inspect(cutoff="99")
        self.assertEqual(facts["asOf"], "110")
        self.assertFalse(facts["withinCutoff"])
        self.assertFalse(facts["finalAsOf"])

    def test_refused_selection_never_becomes_empty_or_newest_record(self):
        self.port.as_of_status = 404
        with self.assertRaises(DomainError):
            self.inspect()
        self.assertEqual(len(self.port.calls), 1)
        self.assertEqual(self.verified, [])

    def test_wrong_source_instant_and_interval_refused_before_canonical_callback(self):
        for field, value in (("instant", "111"), ("tokenId", "20")):
            self.setUp()
            def mutate(path, body, field=field, value=value):
                if "/entry/as-of/" in path:
                    body[field] = value
                return body
            self.port.mutate = mutate
            with self.assertRaises(DomainError):
                self.inspect()
            self.assertEqual(self.verified, [])
        self.setUp()
        self.port.entry["supersededAt"] = "110"
        with self.assertRaises(DomainError):
            self.inspect()
        self.assertEqual(self.verified, [])

    def test_selection_version_record_fields_cannot_drift_before_verification(self):
        for field, value in (("registryReference", "0x" + "a" * 64),
                             ("previousCommitment", "0x" + "a" * 64)):
            self.setUp()
            def mutate(path, body, field=field, value=value):
                if "/entry/version/" in path:
                    body["entry"][field] = value
                return body
            self.port.mutate = mutate
            with self.assertRaises(DomainError):
                self.inspect()
            self.assertEqual(self.verified, [])

    def test_existing_append_churn_bound_is_preserved(self):
        self.port.counts = ["3", "4", "4", "5"]
        with self.assertRaises(DomainError):
            self.inspect()
        self.assertEqual(len(self.port.calls), 11)
        self.assertEqual(self.verified, [])

    def test_canonical_mapping_is_still_required(self):
        self.join = OracleProjectionJoin(SOURCE, self.port, lambda binding, facts: False)
        with self.assertRaises(DomainError):
            self.inspect()

    def test_transport_admits_only_existing_bounded_as_of_read(self):
        body = json.dumps({"tokenId": "19"}).encode()
        headers = Message()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
        class Sock:
            def settimeout(self, value):
                pass
        class Response:
            status = 200
            def __init__(self):
                self.headers = headers
                self.done = False
            def getheader(self, key, default=None):
                return self.headers.get(key, default)
            def read1(self, count):
                if self.done:
                    return b""
                self.done = True
                return body
            def close(self):
                pass
        class Connection:
            sock = Sock()
            def connect(self):
                pass
            def request(self, method, path, headers):
                self.sent = (method, path)
            def getresponse(self):
                return Response()
            def close(self):
                pass
        connection = Connection()
        with patch("exchange.oracle_http_transport.http.client.HTTPConnection",
                   return_value=connection):
            transport = OracleHTTPTransport("http://127.0.0.1:12345")
            self.assertEqual(transport("GET", PREFIX + "/19/entry/as-of/0"),
                             (200, {"tokenId": "19"}))
            self.assertEqual(connection.sent, ("GET", PREFIX + "/19/entry/as-of/0"))

    def test_transport_rejects_write_query_and_uint64_overflow_before_connect(self):
        transport = OracleHTTPTransport("http://127.0.0.1:12345")
        with patch("exchange.oracle_http_transport.http.client.HTTPConnection") as connect:
            for method, tail in (("POST", "/19/entry/as-of/1"),
                                 ("GET", "/19/entry/as-of/1?latest=1"),
                                 ("GET", "/19/entry/as-of/18446744073709551616"),
                                 ("GET", "/19/entry/as-of/01")):
                with self.assertRaises(OracleHTTPRefused):
                    transport(method, PREFIX + tail)
            connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
