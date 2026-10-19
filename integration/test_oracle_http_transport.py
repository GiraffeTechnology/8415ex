"""Mock socket regressions; no real HTTP, DNS or deployed service."""
import json
from email.message import Message
import ssl
import unittest
from unittest.mock import patch

from exchange.oracle_http_transport import OracleHTTPRefused, OracleHTTPTransport
from exchange.oracle_projection_join import OracleProjectionJoin
from exchange.principal_journal_contract import PrincipalBinding
from exchange.model import Asset
from exchange.settlement import EscrowPosition

PATH = "/v1/oracle/projection/19"
ORIGIN = "https://oracle.invalid"
SOURCE = {"chainId": "11155111", "contract": "0x" + "5" * 40,
          "registerId": "0x" + "6" * 64}
COMMITMENT = "0x" + "7" * 64


class FakeSocket:
    def __init__(self):
        self.timeouts = []

    def settimeout(self, value):
        self.timeouts.append(value)


class FakeResponse:
    def __init__(self, data=b'{"tokenId":"19"}', status=200, headers=None):
        self.data, self.offset, self.status, self.closed = data, 0, status, False
        self.headers = Message()
        for key, value in headers or [("Content-Type", "application/json"),
                                     ("Content-Length", str(len(data)))]:
            self.headers[key] = value

    def getheader(self, key, default=None):
        return self.headers.get(key, default)

    def read1(self, size):
        value = self.data[self.offset:self.offset + size]
        self.offset += len(value)
        return value

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, response):
        self.response, self.sock, self.closed = response, FakeSocket(), False
        self.requests, self.connects = [], 0

    def connect(self):
        self.connects += 1

    def request(self, method, path, headers):
        self.requests.append((method, path, dict(headers)))

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class OracleHTTPTransportTests(unittest.TestCase):
    def run_fake(self, response, path=PATH, origin=ORIGIN, timeout=5000):
        connection = FakeConnection(response)
        with patch("exchange.oracle_http_transport.http.client.HTTPSConnection", return_value=connection) as factory:
            result = OracleHTTPTransport(origin, timeout)("GET", path)
        return result, connection, factory

    def test_constructor_has_no_network_and_tls_checks_remain(self):
        with patch("exchange.oracle_http_transport.http.client.HTTPSConnection") as factory:
            transport = OracleHTTPTransport(ORIGIN)
            factory.assert_not_called()
        result, connection, factory = self.run_fake(FakeResponse())
        context = factory.call_args.kwargs["context"]
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertEqual(result, (200, {"tokenId": "19"}))
        self.assertTrue(connection.closed)

    def test_get_path_prefix_and_identity_encoding(self):
        result, connection, _ = self.run_fake(FakeResponse(), origin=ORIGIN + "/original-api/")
        method, path, headers = connection.requests[0]
        self.assertEqual(method, "GET")
        self.assertEqual(path, "/original-api" + PATH)
        self.assertEqual(headers, {"Accept": "application/json", "Accept-Encoding": "identity"})

    def test_origin_credentials_cleartext_and_traversal_refused(self):
        for origin in ("https://user:pass@oracle.invalid", "http://oracle.invalid",
                       ORIGIN + "?secret=x", ORIGIN + "#fragment",
                       ORIGIN + "/../escape", ORIGIN + "//double",
                       ORIGIN + "/%2e%2e", ORIGIN + "\n", ORIGIN + ":0"):
            with self.assertRaises(OracleHTTPRefused):
                OracleHTTPTransport(origin)
        OracleHTTPTransport("http://127.0.0.1:8080")
        OracleHTTPTransport("http://[::1]:8080")

    def test_write_and_non_projection_routes_refused_before_connect(self):
        with patch("exchange.oracle_http_transport.http.client.HTTPSConnection") as factory:
            transport = OracleHTTPTransport(ORIGIN)
            for method, path in (("POST", PATH), ("GET", PATH + "/position"),
                                 ("GET", PATH + "?x=1"), ("GET", "/projection/19"),
                                 ("GET", PATH + "/entry/version/0"),
                                 ("GET", "/v1/oracle/projection/019"),
                                 ("GET", "/v1/oracle/projection/" + str(2 ** 256))):
                with self.assertRaises(OracleHTTPRefused):
                    transport(method, path)
            factory.assert_not_called()

    def test_redirect_refused_and_resources_closed(self):
        response = FakeResponse(status=302, headers=[("Location", "https://elsewhere.invalid")])
        connection = FakeConnection(response)
        with patch("exchange.oracle_http_transport.http.client.HTTPSConnection", return_value=connection):
            with self.assertRaisesRegex(OracleHTTPRefused, "REDIRECT_REFUSED"):
                OracleHTTPTransport(ORIGIN)("GET", PATH)
        self.assertTrue(response.closed)
        self.assertTrue(connection.closed)
        self.assertEqual(connection.connects, 1)

    def test_content_type_encoding_and_framing_refused(self):
        for extra in (
            [("Content-Type", "text/html")],
            [("Content-Type", "application/json; charset=latin-1")],
            [("Content-Type", "application/json"), ("Content-Encoding", "gzip")],
            [("Content-Type", "application/json"), ("Content-Length", "1"), ("Content-Length", "2")],
            [("Content-Type", "application/json"), ("Content-Length", "17"), ("Transfer-Encoding", "chunked")],
            [("Content-Type", "application/json"), ("Transfer-Encoding", "gzip")],
        ):
            with self.assertRaises(OracleHTTPRefused):
                self.run_fake(FakeResponse(headers=extra))

    def test_declared_and_streamed_body_limit(self):
        for response in (
            FakeResponse(headers=[("Content-Type", "application/json"), ("Content-Length", "65537")]),
            FakeResponse(b"x" * 65537, headers=[("Content-Type", "application/json")]),
        ):
            with self.assertRaises(OracleHTTPRefused):
                self.run_fake(response)

    def test_truncated_body_refused(self):
        response = FakeResponse(b"{}", headers=[("Content-Type", "application/json"), ("Content-Length", "3")])
        with self.assertRaisesRegex(OracleHTTPRefused, "TRUNCATED_BODY"):
            self.run_fake(response)

    def test_duplicate_keys_noninteger_numbers_and_utf8_refused(self):
        for data in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1.5}',
                     b'{"x":"\xff"}', b"[]", b"not-json"):
            with self.assertRaises(OracleHTTPRefused):
                self.run_fake(FakeResponse(data))

    def test_deadline_and_invalid_timeout(self):
        for value in (True, 0, 30001, 1.5):
            with self.assertRaises(OracleHTTPRefused):
                OracleHTTPTransport(ORIGIN, value)
        response = FakeResponse()
        connection = FakeConnection(response)
        with patch("exchange.oracle_http_transport.http.client.HTTPSConnection", return_value=connection):
            with patch("exchange.oracle_http_transport.time.monotonic", side_effect=[0, 0, 2]):
                with self.assertRaisesRegex(OracleHTTPRefused, "DEADLINE"):
                    OracleHTTPTransport(ORIGIN, 1000)("GET", PATH)
        self.assertTrue(connection.closed)

    def test_http_error_is_preserved_and_exception_detail_sanitized(self):
        result, _, _ = self.run_fake(FakeResponse(b'{"ok":false,"errorCode":"UNAVAILABLE"}', status=503))
        self.assertEqual(result[0], 503)
        connection = FakeConnection(FakeResponse())
        connection.connect = lambda: (_ for _ in ()).throw(OSError("sensitive-runtime-value"))
        with patch("exchange.oracle_http_transport.http.client.HTTPSConnection", return_value=connection):
            with self.assertRaises(OracleHTTPRefused) as caught:
                OracleHTTPTransport(ORIGIN)("GET", PATH)
        self.assertEqual(str(caught.exception), "ORACLE_HTTP_UNAVAILABLE_OR_MALFORMED")

    def test_existing_projection_join_consumes_http_transport(self):
        buyer, seller = "0x" + "1" * 40, "0x" + "2" * 40
        token, nft = "0x" + "3" * 40, "0x" + "4" * 40
        binding = PrincipalBinding(EscrowPosition("escrow-3", "receipt-1", 3, buyer, seller, token, 10),
            Asset(11155111, nft, 19), "transfer-3", token, 6, "native-op-3", "journal-3")
        base = {"tokenId": "19", "source": SOURCE}
        entry = dict(version="2", holder=buyer, effectiveAt="100", supersededAt="0",
                     recordCommitment=COMMITMENT, previousCommitment="0x" + "8" * 64,
                     registryReference="0x" + "9" * 64)
        bodies = [dict(base, registerId=SOURCE["registerId"], entryCount="3"),
                  dict(base, entry=entry), dict(base, instant="110", holder=buyer),
                  dict(base, instant="110", final=False),
                  dict(base, registerId=SOURCE["registerId"], entryCount="3")]
        connections = [FakeConnection(FakeResponse(json.dumps(body).encode())) for body in bodies]
        with patch("exchange.oracle_http_transport.http.client.HTTPSConnection", side_effect=connections):
            joined = OracleProjectionJoin(SOURCE, OracleHTTPTransport(ORIGIN), lambda b, f: True)
            result = joined.inspect(binding, "2", COMMITMENT, "110", "105")
        self.assertTrue(result["withinCutoff"])
        self.assertFalse(result["atomicSettlementAuthority"])
        self.assertTrue(all(c.closed and c.response.closed for c in connections))
