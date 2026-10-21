"""Synthetic response identity checks; no live source or product execution."""
import unittest

from exchange.eia_wti_spot_reader import (
    EIAWTISpotReader, SpotSourceUnavailable, SpotSourceDeferred, LIMIT)
from exchange.eia_wti_spot_table import SOURCE_URL, SCOPE
from integration.test_eia_wti_spot_reader import Response
from integration.test_eia_wti_spot_table import page


class SourceRepresentationIdentity(unittest.TestCase):
    def setUp(self):
        self.now, self.calls, self.queue = 0, [], []
        self.raw = page([["2026 Oct-12 to Oct-16", "1.10", "", "", "", ""]])
        self.policy = dict(SCOPE, sourceURL=SOURCE_URL)

        def transport(request, timeout):
            self.calls.append((request, timeout))
            return self.queue.pop(0)

        self.reader = EIAWTISpotReader(timeout_seconds=7, user_agent="EX-test",
            minimum_fetch_seconds=10, failure_backoff_seconds=20,
            open_response=transport, monotonic=lambda: self.now,
            wall_clock=lambda: 0)

    def test_complete_fixed_length_and_chunked_representations(self):
        for index, headers in enumerate((
            {"Content-Length": str(len(self.raw))},
            {"Transfer-Encoding": "chunked"}, {})):
            self.now = index * 10
            self.queue.append(Response(self.raw, headers=headers))
            result = self.reader(self.policy)
            self.assertEqual(result["sourceAsOf"], "2026-10-12")
            self.assertEqual(self.reader.transport_observation()["bytes"], len(self.raw))
            self.assertEqual(self.reader.transport_observation()["rawResponseSHA256"],
                             result["rawResponseSHA256"])

    def test_parseable_short_or_excess_body_is_not_complete(self):
        for index, declared in enumerate((len(self.raw) - 1, len(self.raw) + 1)):
            self.now = index * 30
            response = Response(self.raw, headers={"Content-Length": str(declared)})
            self.queue.append(response)
            with self.assertRaisesRegex(SpotSourceUnavailable, "^SPOT_SOURCE_LENGTH_DIFFERS$"):
                self.reader(self.policy)
            self.assertTrue(response.closed)
            self.assertFalse(self.reader.transport_observation()["retainedSource"])

    def test_duplicate_length_or_transfer_headers_are_not_accepted(self):
        for index, header in enumerate(("Content-Length", "Transfer-Encoding")):
            self.now = index * 30
            response = Response(self.raw)
            value = str(len(self.raw)) if header == "Content-Length" else "chunked"
            response.headers[header] = value
            response.headers[header] = value
            self.queue.append(response)
            with self.assertRaisesRegex(SpotSourceUnavailable, "^SPOT_SOURCE_FRAMING_REFUSED$"):
                self.reader(self.policy)
            self.assertTrue(response.closed)

    def test_ambiguous_unsupported_or_malformed_framing(self):
        headers = (
            {"Content-Length": str(len(self.raw)), "Transfer-Encoding": "chunked"},
            {"Content-Length": "-1"}, {"Content-Length": "1, 1"},
            {"Transfer-Encoding": "gzip"}, {"Content-Length": ""})
        for index, value in enumerate(headers):
            self.now = index * 30
            self.queue.append(Response(self.raw, headers=value))
            with self.subTest(headers=value), self.assertRaisesRegex(
                    SpotSourceUnavailable, "^SPOT_SOURCE_FRAMING_REFUSED$"):
                self.reader(self.policy)

    def test_declared_oversize_is_refused_before_body_read(self):
        response = Response(self.raw, headers={"Content-Length": str(LIMIT + 1)})
        response.read = lambda count: self.fail("oversize representation was read")
        self.queue.append(response)
        with self.assertRaisesRegex(SpotSourceUnavailable, "^SPOT_SOURCE_RESPONSE_TOO_LARGE$"):
            self.reader(self.policy)
        self.assertTrue(response.closed)

    def test_failed_representation_retains_old_cache_and_backoff_then_recovers(self):
        self.queue.extend([
            Response(self.raw, headers={"ETag": '"old"'}),
            Response(page([["2026 Oct-12 to Oct-16", "", "2.20", "", "", ""]]),
                     headers={"Content-Length": "1", "ETag": '"new"'}),
            Response(code=304),
            Response(page([["2026 Oct-12 to Oct-16", "", "", "3.30", "", ""]]),
                     headers={"ETag": '"recovered"'})])
        first = self.reader(self.policy)
        self.now = 10
        with self.assertRaisesRegex(SpotSourceUnavailable, "LENGTH_DIFFERS"):
            self.reader(self.policy)
        self.assertTrue(self.reader.transport_observation()["retainedSource"])
        self.now = 29
        with self.assertRaises(SpotSourceDeferred):
            self.reader(self.policy)
        self.assertEqual(len(self.calls), 2)
        self.now = 30
        unchanged = self.reader(self.policy)
        self.assertEqual(unchanged["price"], first["price"])
        self.assertEqual(unchanged["rawResponseSHA256"], first["rawResponseSHA256"])
        self.assertEqual(self.calls[2][0].get_header("If-none-match"), '"old"')
        self.now = 40
        self.assertEqual(self.reader(self.policy)["sourceAsOf"], "2026-10-14")
