"""Synthetic explicit host-to-provenance composition; no live reference source."""
from copy import deepcopy
from html import escape
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen

from exchange import eia_bulk_reference_serve as host
from exchange.reference_provenance_page import BULK_WORDS
from integration import test_eia_bulk_reference_catalogue as catalogue
from integration import test_eia_bulk_reference_serve as configuration


class ExplicitBulkHostProvenanceContracts(unittest.TestCase):
    def setUp(self):
        self.fixture = catalogue.EIABulkCatalogueContracts("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.config = configuration.EIABulkHostContracts("runTest")
        self.config.setUp()

    def compose_host(self):
        def bind(**options):
            options["reader_options"] = dict(options["reader_options"],
                open_response=self.fixture.open, monotonic=lambda:self.fixture.now,
                wall_clock=lambda:1000)
            return self.fixture.compose(**options)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"synthetic-reference.json"
            raw = self.config.raw()
            path.write_bytes(raw)
            with patch.object(host, "compose_eia_bulk_reference_catalogue", side_effect=bind), \
                 patch.object(host, "serve_reference_catalogue") as serve:
                self.assertEqual(host.main(self.config.arguments(path,
                    hashlib.sha256(raw).hexdigest())), 0)
            serve.assert_called_once_with(self.fixture.server)
        return self.fixture.server

    def start(self, server):
        worker = threading.Thread(target=server.serve_forever,
            kwargs={"poll_interval":0.02}, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 3)
        self.addCleanup(server.shutdown)

    def page(self, server, locale):
        with urlopen(server.origin+"/market?reference=1&lang="+locale, timeout=3) as response:
            return response.read().decode()

    def test_explicit_host_composes_latest_bulk_feed_without_eager_reads_or_workers(self):
        server = self.compose_host()
        self.assertEqual(self.fixture.calls, [])
        self.assertIsNone(server.reference_feed._thread)
        self.assertEqual(server.reference_feed.snapshot()["status"], "unavailable")
        self.assertEqual(self.fixture.calls, [])
        self.assertTrue(hasattr(server.reference_feed._bulk_reader, "cached_source_evidence"))

    def test_original_archive_metadata_reaches_six_http_views_without_new_source_reads(self):
        server = self.compose_host()
        value = self.fixture.initial()
        before = deepcopy(value)
        calls = list(self.fixture.calls)
        self.start(server)
        for locale, words in BULK_WORDS.items():
            with self.subTest(locale=locale):
                body = self.page(server, locale)
                for label in words[:8]:
                    self.assertIn(escape(label), body)
                self.assertIn("Synthetic upstream", body)
                self.assertIn("Synthetic attribution", body)
                for key in ("sha256", "selectedLineSHA256", "manifestSHA256"):
                    self.assertIn(value["sourceEvidence"]["bulkSource"][key], body)
                self.assertIn(escape(words[8]), body)
        self.assertEqual(self.fixture.calls, calls)
        self.assertEqual(value, before)

    def test_unchanged_manifest_retains_original_attribution_without_archive_or_page_refetch(self):
        server = self.compose_host()
        first = self.fixture.initial()
        self.fixture.now += self.config.config["reader"]["minimum_fetch_seconds"]
        self.fixture.queue.append(self.fixture.manifest())
        current = server.reference_feed.refresh()
        self.assertEqual(current["sourceEvidence"], first["sourceEvidence"])
        self.assertEqual(len(self.fixture.calls), 3)
        self.start(server)
        before = list(self.fixture.calls)
        body = self.page(server, "en")
        self.assertIn("Synthetic attribution", body)
        self.assertEqual(self.fixture.calls, before)

    def test_conflicting_cache_metadata_cannot_be_shown_as_another_archives_attribution(self):
        server = self.compose_host()
        self.fixture.initial()
        reader = server.reference_feed._bulk_reader
        wrong = deepcopy(reader.cached_source_evidence())
        wrong["sha256"] = "f"*64
        self.start(server)
        before = list(self.fixture.calls)
        with patch.object(reader, "cached_source_evidence", return_value=wrong):
            for locale in BULK_WORDS:
                body = self.page(server, locale)
                self.assertNotIn("Synthetic upstream", body)
                self.assertNotIn("Synthetic attribution", body)
        self.assertEqual(self.fixture.calls, before)
