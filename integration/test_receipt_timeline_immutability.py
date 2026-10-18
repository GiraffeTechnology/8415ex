"""History object-isolation regressions using explicit synthetic domain fixtures."""
from copy import deepcopy
import unittest

from exchange import fixtures as F


class ReceiptTimelineIsolation(unittest.TestCase):
    def setUp(self):
        self.exchange, self.clock = F.minted()
        self.receipt_id = F.receipt().receipt_id

    def test_reader_cannot_rewrite_stored_event_or_nested_detail(self):
        before = deepcopy(self.exchange.receipt_timeline(self.receipt_id))
        exposed = self.exchange.receipt_timeline(self.receipt_id)
        exposed[0]["kind"] = "rollback-complete"
        exposed[0]["sequence"] = 999
        exposed[0]["receiptId"] = "another-receipt"
        exposed[0]["detail"]["asset"][0] = 1
        exposed[0]["detail"]["inventedOutcome"] = "settled"
        self.assertEqual(self.exchange.receipt_timeline(self.receipt_id), before)

    def test_recording_captures_detail_instead_of_retaining_caller_reference(self):
        detail = {"nativeOperationId": "synthetic-original-op",
                  "steps": [{"status": "unknown", "amounts": [1, 2]}]}
        expected = deepcopy(detail)
        self.exchange._record(self.receipt_id, "synthetic-operation-observation", detail)
        detail["steps"][0]["status"] = "complete"
        detail["steps"][0]["amounts"].append(999)
        detail["nativeOperationId"] = "substitute-op"
        stored = self.exchange.receipt_timeline(self.receipt_id)[-1]
        self.assertEqual(stored["detail"], expected)
        self.assertEqual(stored["sequence"], 1)

    def test_earlier_read_is_stable_when_later_events_are_appended(self):
        earlier = self.exchange.receipt_timeline(self.receipt_id)
        expected = deepcopy(earlier)
        self.exchange._record(self.receipt_id, "synthetic-later-observation", {"status": "unknown"})
        later = self.exchange.receipt_timeline(self.receipt_id)
        self.assertEqual(earlier, expected)
        self.assertEqual(len(later), len(earlier) + 1)
        self.assertEqual(tuple(event["sequence"] for event in later), tuple(range(len(later))))
        later[0]["detail"].clear()
        self.assertEqual(earlier, expected)
        self.assertEqual(self.exchange.receipt_timeline(self.receipt_id)[0], expected[0])
