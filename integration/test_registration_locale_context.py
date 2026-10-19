"""Approved Linux definitions for language navigation over one original source."""
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urlsplit
import unittest

from integration.test_integrated_workbench_http import IntegratedWorkbenchHTTPTests


LANGUAGES = ("en", "zh-Hans", "zh-Hant", "fr", "es", "ja")
SOURCES = ("REG-DIRECT", "REG-ELECTRONIC", "REG-INTERMEDIARY")


class LanguageLinks(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.links = {}
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "a" and fields.get("lang") in LANGUAGES:
            language = fields["lang"]
            if language in self.links:
                raise AssertionError("duplicate page language link")
            self.links[language] = fields["href"]


class RegistrationLocaleContextTests(unittest.TestCase):
    def setUp(self):
        self.fixture = IntegratedWorkbenchHTTPTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def get(self, path):
        return self.fixture.request("GET", path)

    def test_all_three_selected_sources_survive_every_language_switch(self):
        for source in SOURCES:
            for language in LANGUAGES:
                with self.subTest(source=source, language=language):
                    query = urlencode(dict(lang=language, receipt="receipt-1", source=source))
                    status, _, body = self.get("/registration-source?" + query)
                    self.assertEqual(status, 200)
                    links = LanguageLinks(body).links
                    self.assertEqual(set(links), set(LANGUAGES))
                    for target_language, href in links.items():
                        target = urlsplit(href)
                        self.assertEqual(target.path, "/registration-source")
                        self.assertEqual(target.netloc, "")
                        self.assertEqual(parse_qs(target.query), {
                            "lang": [target_language], "receipt": ["receipt-1"], "source": [source]})
                    status, _, translated = self.get(links["fr"])
                    self.assertEqual(status, 200)
                    self.assertIn('<section lang="fr">', translated)
                    self.assertIn(source, translated)
        self.assertEqual(self.fixture.wallet_calls, [])

    def test_source_selection_page_does_not_invent_a_selected_task(self):
        status, _, body = self.get("/registration-source?lang=ja")
        self.assertEqual(status, 200)
        for language, href in LanguageLinks(body).links.items():
            self.assertEqual(parse_qs(urlsplit(href).query), {"lang": [language]})
        self.assertEqual(self.fixture.sources.calls, [])
        self.assertEqual(self.fixture.wallet_calls, [])

    def test_gas_page_does_not_inherit_registration_context(self):
        selected = urlencode(dict(receipt="receipt-1", source="REG-ELECTRONIC", lang="es"))
        self.assertEqual(self.get("/registration-source?" + selected)[0], 200)
        status, _, body = self.get("/gas?lang=es")
        self.assertEqual(status, 200)
        for language, href in LanguageLinks(body).links.items():
            self.assertEqual(urlsplit(href).path, "/gas")
            self.assertEqual(parse_qs(urlsplit(href).query), {"lang": [language]})
        self.assertEqual(self.fixture.wallet_calls, [])

    def test_refused_source_fields_never_become_navigation_context(self):
        queries = (
            "receipt=foreign&source=REG-DIRECT&lang=fr",
            "receipt=receipt-1&source=unknown-private-value&lang=fr",
            "receipt=receipt-1&source=REG-DIRECT&source=REG-ELECTRONIC&lang=fr",
            "receipt=receipt-1&source=REG-DIRECT&account=private-value",
        )
        for query in queries:
            with self.subTest(query=query):
                status, _, body = self.get("/registration-source?" + query)
                self.assertEqual(status, 400)
                self.assertEqual(LanguageLinks(body).links, {})
                self.assertNotIn("private-value", body)
        self.assertEqual(self.fixture.sources.calls, [])
        self.assertEqual(self.fixture.wallet_calls, [])
