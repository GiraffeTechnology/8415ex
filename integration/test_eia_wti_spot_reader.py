"""Synthetic bounded-response ports, no live HTTP requests."""
from email.message import Message
import unittest

from exchange.eia_wti_spot_reader import EIAWTISpotReader, SpotSourceDeferred, SpotSourceUnavailable, LIMIT
from exchange.eia_wti_spot_table import SOURCE_URL, SCOPE
from integration.test_eia_wti_spot_table import page


class Response:
    def __init__(self, raw=b"", code=200, headers=None, url=SOURCE_URL):
        self.raw, self.code, self.url = raw, code, url
        self.headers = Message()
        self.headers["Content-Type"] = "text/html"
        for key, value in (headers or {}).items():
            if key == "Content-Type":
                self.headers.replace_header(key, value)
            else:
                self.headers[key] = value
        self.closed = False

    def read(self, count):
        return self.raw[:count]

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


class EIAWTISpotReaderTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.queue, self.calls = [], []
        self.policy = dict(SCOPE, sourceURL=SOURCE_URL)
        self.raw = page([["2026 Oct-12 to Oct-16", "1.10", "", "", "", ""]])
        def transport(request, timeout):
            self.calls.append((request, timeout))
            response = self.queue.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        self.reader = EIAWTISpotReader(timeout_seconds=7, user_agent="EX-source-test",
            minimum_fetch_seconds=10, failure_backoff_seconds=20,
            open_response=transport, monotonic=lambda: self.now, wall_clock=lambda: 0)

    def test_exact_get_and_explicit_timeout_without_credentials(self):
        response = Response(self.raw)
        self.queue.append(response)
        value = self.reader(self.policy)
        request, timeout = self.calls[0]
        self.assertEqual((request.full_url, request.get_method(), request.data),
                         (SOURCE_URL, "GET", None))
        self.assertEqual(timeout, 7)
        self.assertFalse(any(key.lower() in ("authorization", "cookie") for key in request.headers))
        self.assertEqual(value["sourceAsOf"], "2026-10-12")
        self.assertTrue(response.closed)

    def test_conditional_304_preserves_date_digest_and_detaches_cache(self):
        self.queue.extend([Response(self.raw, headers={"ETag": '"one"'}),
                           Response(code=304)])
        first = self.reader(self.policy)
        digest = first["rawResponseSHA256"]
        first["price"] = "999"
        self.now = 10
        second = self.reader(self.policy)
        self.assertEqual(second["price"], "1.10")
        self.assertEqual(second["rawResponseSHA256"], digest)
        self.assertEqual(second["sourceAsOf"], "2026-10-12")
        self.assertNotIn("fetchedAt", second)
        self.assertEqual(self.calls[1][0].get_header("If-none-match"), '"one"')
        self.assertEqual(self.reader.transport_observation()["httpStatus"], 304)

    def test_304_without_validated_cache_refused(self):
        self.queue.append(Response(code=304))
        with self.assertRaises(SpotSourceUnavailable):
            self.reader(self.policy)
        self.assertFalse(self.reader.transport_observation()["retainedSource"])

    def test_spacing_defers_without_opening_transport(self):
        self.queue.append(Response(self.raw))
        self.reader(self.policy)
        self.now = 9
        with self.assertRaises(SpotSourceDeferred):
            self.reader(self.policy)
        self.assertEqual(len(self.calls), 1)

    def test_retry_after_seconds_not_shortened_to_host_spacing(self):
        self.queue.extend([Response(code=429, headers={"Retry-After": "60"}), Response(self.raw)])
        with self.assertRaises(SpotSourceUnavailable):
            self.reader(self.policy)
        self.now = 59
        with self.assertRaises(SpotSourceDeferred):
            self.reader(self.policy)
        self.assertEqual(len(self.calls), 1)
        self.now = 60
        self.assertEqual(self.reader(self.policy)["price"], "1.10")

    def test_retry_after_http_date_and_large_value(self):
        self.queue.extend([Response(code=503, headers={"Retry-After": "Thu, 01 Jan 1970 00:02:00 GMT"}),
                           Response(code=429, headers={"Retry-After": "9999999999999999"})])
        with self.assertRaises(SpotSourceUnavailable):
            self.reader(self.policy)
        self.now = 119
        with self.assertRaises(SpotSourceDeferred):
            self.reader(self.policy)
        self.now = 120
        with self.assertRaises(SpotSourceUnavailable):
            self.reader(self.policy)
        self.now = 10**15
        with self.assertRaises(SpotSourceDeferred):
            self.reader(self.policy)
        self.assertEqual(len(self.calls), 2)

    def test_network_error_is_sanitized_and_backed_off(self):
        self.queue.append(OSError("private transport detail"))
        with self.assertRaisesRegex(SpotSourceUnavailable, "^SPOT_SOURCE_READ_UNAVAILABLE$"):
            self.reader(self.policy)
        self.now = 19
        with self.assertRaises(SpotSourceDeferred):
            self.reader(self.policy)
        self.assertNotIn("private", str(self.reader.transport_observation()))

    def test_invalid_response_never_replaces_previous_source(self):
        self.queue.extend([Response(self.raw), Response(b"<html>broken</html>"), Response(code=304)])
        self.reader(self.policy)
        self.now = 10
        with self.assertRaises(SpotSourceUnavailable):
            self.reader(self.policy)
        self.assertTrue(self.reader.transport_observation()["retainedSource"])
        self.now = 30
        self.assertEqual(self.reader(self.policy)["price"], "1.10")

    def test_redirect_type_encoding_and_size_refused(self):
        responses = [
            Response(self.raw, url="https://example.invalid/other"),
            Response(code=302, headers={"Location": "https://example.invalid/other"}),
            Response(self.raw, headers={"Content-Type": "application/json"}),
            Response(self.raw, headers={"Content-Encoding": "gzip"}),
            Response(b"x" * (LIMIT + 1)),
        ]
        for number, response in enumerate(responses):
            self.now = number * 30
            self.queue.append(response)
            with self.subTest(number=number), self.assertRaises(SpotSourceUnavailable):
                self.reader(self.policy)
        self.assertEqual(len(self.calls), len(responses))

    def test_policy_drift_refused_before_transport(self):
        for field in (*SCOPE, "sourceURL"):
            changed = dict(self.policy, **{field: "different"})
            with self.subTest(field=field), self.assertRaises(SpotSourceUnavailable):
                self.reader(changed)
        self.assertEqual(self.calls, [])

    def test_explicit_host_options_validators_and_recovery(self):
        for args in ({}, {"timeout_seconds": 0}, {"user_agent": "bad\r\nheader"},
                     {"minimum_fetch_seconds": False}, {"failure_backoff_seconds": -1}):
            options = dict(timeout_seconds=7, user_agent="EX-test",
                           minimum_fetch_seconds=10, failure_backoff_seconds=20)
            options.update(args)
            if not args:
                options.pop("minimum_fetch_seconds")
            with self.subTest(args=args), self.assertRaises((ValueError, TypeError)):
                EIAWTISpotReader(**options)
        self.queue.extend([Response(self.raw, headers={"ETag": "x" * 513}),
                           Response(page([["2026 Oct-12 to Oct-16", "", "", "", "2.20", ""]]))])
        with self.assertRaises(SpotSourceUnavailable):
            self.reader(self.policy)
        self.now = 20
        self.assertEqual(self.reader(self.policy)["sourceAsOf"], "2026-10-15")


if __name__ == "__main__":
    unittest.main()
