"""Changed UI contracts; source fixtures only, no live or chain authority."""
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
from exchange.nft_detail import receipt_detail
from exchange.nft_detail_page import LOCALES, render_detail
from exchange.market_page import render_market
from exchange.persistent_simulation_serve import create_simulation_server
from integration.test_nft_detail import OriginalReadOnlyDomain

class ProductLanguageAndSimulationMode(unittest.TestCase):
    def test_detail_menu_keeps_all_original_languages_and_selected_context(self):
        detail = receipt_detail(OriginalReadOnlyDomain(), "r")
        key = "1" * 64
        for locale in LOCALES:
            with self.subTest(locale=locale):
                body = render_detail(detail, locale, nft_key=key, market_query="soy <x>",
                                     evidence_kind="LOCAL_SIMULATION")
                self.assertIn('<details class="locale-menu"><summary', body)
                self.assertIn('LOCAL_SIMULATION / ' + locale, body)
                for target in LOCALES:
                    self.assertIn('lang="' + target + '" href="/nft?', body)
                self.assertIn('nft=' + key, body)
                self.assertIn('q=soy+%3Cx%3E', body)
                self.assertNotIn('<script>', body)
                self.assertEqual(detail["terms"]["clauses"], [])
        self.assertNotIn('class="detail-mode"', render_detail(detail))
        for value in ("REAL", True, ""):
            with self.assertRaises(ValueError):
                render_detail(detail, evidence_kind=value)

    def test_market_menu_retains_search_without_promoting_external_source_to_simulation(self):
        reference = {"status": "unavailable", "price": None}
        for locale in LOCALES:
            page = render_market([], reference, locale, "soy",
                                 evidence_kind="LOCAL_SIMULATION")
            self.assertIn('class="locale-menu"', page)
            self.assertIn('class="badge">LOCAL_SIMULATION', page)
            self.assertIn('q=soy', page)
        self.assertEqual(reference, {"status": "unavailable", "price": None})

    def test_actual_simulation_composition_marks_mode_and_retains_native_audit_routes_at_footer(self):
        with TemporaryDirectory() as directory:
            Path(directory).chmod(0o700)
            server = create_simulation_server(state_path=Path(directory) / "history.sqlite",
                port=0, commit="a" * 40, tree="b" * 40, registration_path="REG_DIRECT")
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                key = server.default_nft_key
                for path in ("/?lang=fr", "/nft?lang=fr&nft=" + key + "&q=soy", "/receipt?lang=fr"):
                    with self.subTest(path=path), urlopen(server.origin + path, timeout=3) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.headers["X-EX-Runtime-Mode"], "LOCAL_SIMULATION")
                        page = response.read().decode()
                        self.assertIn("LOCAL_SIMULATION", page)
                        self.assertLess(page.index("<header"), page.index('data-native-navigation="1"'))
                        for route in ("receipt", "market", "evidence", "queue", "authorization", "timeline", "rollback"):
                            self.assertIn('href="/' + route + '?lang=fr"', page)
                with urlopen(server.origin + "/api/reference", timeout=3) as response:
                    import json
                    reference = json.load(response)
                    self.assertEqual(reference["kind"], "external-spot-reference")
                    self.assertEqual(reference["status"], "not-connected")
                    self.assertIsNone(reference["price"])
                with self.assertRaises(HTTPError) as error:
                    urlopen(server.origin + "/?lang=fr&evidence_kind=REAL", timeout=3)
                self.assertEqual(error.exception.code, 400)
                self.assertEqual(server.history.recent(), [])
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=2)
