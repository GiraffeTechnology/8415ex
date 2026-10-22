"""Synthetic bulk provenance display, with no source reads or native effects."""
from copy import deepcopy
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from exchange.eia_wti_bulk_series import BULK_URL
from exchange.reference_provenance_page import (
    BULK_WORDS, VALUES, render_reference_fields,
)
from integration.test_reference_provenance_locales import reference, Terms
from scenarios.observations import secret_scan


def bulk_reference():
    value = reference()
    value.update(sourceURL=BULK_URL, provider="Synthetic distribution",
                 sourcePrecision="date", sourceTimezone=None, sourceAttributionStatus="recorded",
                 sourceEvidence={"rawResponseSHA256": "a"*64,
                    "responseDigestScope": "complete-petroleum-archive",
                    "bulkSource": {"sha256": "a"*64, "selectedLineSHA256": "b"*64,
                        "manifestSHA256": "c"*64, "sourceUpdatedAt": "2026-10-15T18:43:40-04:00",
                        "datasetUpdatedAt": "2026-10-15T19:00:00-04:00",
                        "upstreamSource": "Synthetic upstream",
                        "sourceCopyright": "Synthetic attribution"}})
    return value


class BulkReferenceProvenanceContracts(unittest.TestCase):
    def test_all_six_locales_show_bound_source_and_distinct_digest_scopes(self):
        value = bulk_reference()
        for locale, words in BULK_WORDS.items():
            body = render_reference_fields(value, locale)
            self.assertEqual(len(Terms(body).labels), 25)
            for label in words[:8]:
                self.assertIn(escape(label), body)
            for text in ("Synthetic upstream", "Synthetic attribution",
                         "2026-10-15T18:43:40-04:00", "2026-10-15T19:00:00-04:00",
                         "a"*64, "b"*64, "c"*64):
                self.assertIn(text, body)
            self.assertIn(escape(words[8]), body)

    def test_original_html_contract_keeps_exact_seventeen_fields(self):
        value = reference()
        value["sourceEvidence"] = bulk_reference()["sourceEvidence"]
        for locale, words in BULK_WORDS.items():
            body = render_reference_fields(value, locale)
            self.assertEqual(len(Terms(body).labels), 17)
            self.assertNotIn(escape(words[0]), body)
            self.assertNotIn("Synthetic upstream", body)

    def test_mismatched_missing_or_unrecorded_archive_cannot_echo_attribution(self):
        for change in ("digest", "scope", "status", "missing"):
            value = bulk_reference()
            if change == "digest":
                value["sourceEvidence"]["bulkSource"]["sha256"] = "d"*64
            elif change == "scope":
                value["sourceEvidence"]["responseDigestScope"] = "selected-series-line"
            elif change == "status":
                value["sourceAttributionStatus"] = "unavailable"
            else:
                del value["sourceEvidence"]["bulkSource"]
            body = render_reference_fields(value)
            self.assertNotIn("Synthetic upstream", body)
            self.assertNotIn("Synthetic attribution", body)
            self.assertIn('<dt>'+BULK_WORDS["en"][0]+'</dt><dd>Not provided</dd>', body)

    def test_failure_retains_only_matching_original_metadata_without_claiming_freshness(self):
        value = bulk_reference()
        before = deepcopy(value)
        body = render_reference_fields(value)
        self.assertIn("Synthetic attribution", body)
        self.assertEqual(value, before)
        self.assertEqual(value["status"], "unavailable")
        self.assertNotIn("<dd>fresh</dd>", body)

    def test_original_offset_times_do_not_become_observation_or_publication_dates(self):
        value = bulk_reference()
        body = render_reference_fields(value)
        self.assertIn("<dd>2026-10-16</dd>", body)
        self.assertIn("<dd>Date only</dd>", body)
        self.assertIn("2026-10-15T18:43:40-04:00", body)
        self.assertNotIn("2026-10-16T00:00:00", body)
        self.assertNotIn("publicationDate", body)
        self.assertNotIn("2026-10-15T22:43:40", body)

    def test_malformed_times_hashes_nested_fields_and_wallet_identity_are_not_rendered(self):
        value = bulk_reference()
        value["sourceEvidence"]["bulkSource"].update(
            upstreamSource={"private": "PRIVATE_SENTINEL"},
            sourceCopyright="0x"+"1"*40, sourceUpdatedAt="2026-10-15",
            datasetUpdatedAt="2026-10-15T19:00:00", selectedLineSHA256="<script>bad</script>",
            manifestSHA256="G"*64, privateLog="PRIVATE_SENTINEL")
        body = render_reference_fields(value)
        for text in ("PRIVATE_SENTINEL", "0x"+"1"*40, "<script>", "G"*64):
            self.assertNotIn(text, body)
        self.assertIn('<dt>'+BULK_WORDS["en"][2]+'</dt><dd>Not provided</dd>', body)
        self.assertIn('<dt>'+BULK_WORDS["en"][3]+'</dt><dd>Not provided</dd>', body)

    def test_attribution_is_escaped_and_rendering_never_mutates_original_observation(self):
        value = bulk_reference()
        value["sourceEvidence"]["bulkSource"]["upstreamSource"] = "Source <em>A & B</em>"
        before = deepcopy(value)
        body = render_reference_fields(value, "fr")
        self.assertIn("Source &lt;em&gt;A &amp; B&lt;/em&gt;", body)
        self.assertNotIn("<em>", body)
        self.assertEqual(value, before)

    def test_only_fixed_translations_are_classified_and_private_prose_checks_remain(self):
        name = "exchange/reference_provenance_page.py"
        source = (Path(__file__).resolve().parents[1]/name).read_text(encoding="utf-8")
        enumeration = {"ok": True, "state": "complete", "files": [name]}
        with TemporaryDirectory() as directory:
            target = Path(directory)/name
            target.parent.mkdir()
            target.write_text(source, encoding="utf-8")
            with patch("scenarios.observations.tracked_files", return_value=enumeration):
                self.assertTrue(secret_scan(directory)["clean"])
                private = secret_scan(directory, private_markers=["Upstream source attribution"])
                self.assertFalse(private["clean"])
                target.write_text(source+"\n# "+chr(0x4E2D)+"\n", encoding="utf-8")
                prose = secret_scan(directory)
                self.assertFalse(prose["clean"])
                self.assertTrue(any(row["kind"] == "non-english" for row in prose["findings"]))
