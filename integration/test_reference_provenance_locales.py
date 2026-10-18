"""Approved Linux source definitions; no actual data provider is contacted."""
from copy import deepcopy
from html.parser import HTMLParser
import unittest

from exchange.market_page import render_market
from exchange.reference_provenance_page import render_reference_fields


def reference():
    return dict(status="unavailable", price="987.65", provider="Original provider",
        sourceURL="https://example.invalid/original-series", series="SERIES-7",
        commodity="soy", spec="GRADE-3", market="PORT-2", priceType="spot-reference",
        currency="CNY", unit="t", sourceAsOf="2026-10-16", sourcePrecision="date",
        sourceTimezone="Asia/Shanghai", fetchedAt="2026-10-18T00:00:00Z",
        sourceDelay={"minimumSeconds": 43200, "maximumSeconds": 129600},
        lastSuccessful="2026-10-18T00:00:00Z")


class Terms(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.labels = []
        self.in_label = False
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        self.in_label = tag == "dt"

    def handle_endtag(self, tag):
        if tag == "dt":
            self.in_label = False

    def handle_data(self, data):
        if self.in_label:
            self.labels.append(data)


class ReferenceProvenanceLocalesTests(unittest.TestCase):
    def test_market_provenance_has_six_locales_and_preserves_original_values(self):
        expected = {
            "en": ("Data provider", "Source time zone", "Source age range"),
            "zh-Hans": ("数据提供方", "来源时区", "来源延迟范围"),
            "zh-Hant": ("資料提供方", "來源時區", "來源延遲範圍"),
            "fr": ("Fournisseur de données", "Fuseau horaire de la source", "Plage d’âge de la source"),
            "es": ("Proveedor de datos", "Zona horaria de origen", "Intervalo de antigüedad"),
            "ja": ("データ提供元", "出典のタイムゾーン", "出典の経過時間範囲"),
        }
        observation = reference()
        before = deepcopy(observation)
        for locale, labels in expected.items():
            with self.subTest(locale=locale):
                body = render_market([], observation, locale)
                rendered = Terms(body).labels
                self.assertEqual(len(rendered), 15)
                for label in labels:
                    self.assertIn(label, rendered)
                for value in ("987.65", "GRADE-3", "PORT-2", "SERIES-7", "Asia/Shanghai", "2026-10-16"):
                    self.assertIn(value, body)
                self.assertIn("43200 – 129600", body)
                self.assertNotIn("minimumSeconds", body)
                self.assertNotIn("sourcePrecision", rendered)
        self.assertEqual(observation, before)

    def test_invalid_delay_is_missing_without_zero_or_nested_diagnostic_echo(self):
        for delay in (None, [], {"minimumSeconds": True, "maximumSeconds": 100},
                      {"minimumSeconds": 100, "maximumSeconds": 99},
                      {"minimumSeconds": -1, "maximumSeconds": 100},
                      {"minimumSeconds": "private-diagnostic", "maximumSeconds": 100}):
            with self.subTest(delay=delay):
                fields = render_reference_fields(dict(reference(), sourceDelay=delay), "zh-Hans")
                self.assertIn('<dt>来源延迟范围</dt><dd>未提供</dd>', fields)
                self.assertNotIn("private-diagnostic", fields)
                self.assertNotIn("0 – 0", fields)

    def test_unknown_metadata_is_not_stringified_and_source_text_is_escaped(self):
        observation = dict(reference(), sourcePrecision={"private": "secret-diagnostic"},
                           spec={"private": "secret-diagnostic"}, extra="secret-diagnostic")
        observation["provider"] = "Original <provider>"
        fields = render_reference_fields(observation, "fr")
        self.assertIn("Original &lt;provider&gt;", fields)
        self.assertNotIn("secret-diagnostic", fields)
        self.assertIn('<dt>Spécification</dt><dd>Non fourni</dd>', fields)

    def test_date_and_instant_precision_are_distinct_without_changing_source_date(self):
        observation = reference()
        self.assertIn('<dd>Date only</dd>', render_reference_fields(observation))
        self.assertIn('<dd>Timestamp provided</dd>', render_reference_fields(
            dict(observation, sourcePrecision="instant", sourceAsOf="2026-10-16T14:00:00Z")))
        self.assertEqual(observation["sourceAsOf"], "2026-10-16")
        self.assertNotIn("2026-10-16T00:00:00", render_reference_fields(observation))
