"""Locale classification must preserve the original quote and full secret scan."""
from pathlib import Path
import unittest
from exchange.gas_disclosure_locales import WORDS, BUDGET_OBSERVATION
from exchange.gas_budget_observation_page import WORDS as PAGE_WORDS
from scenarios import observations


class BudgetObservationLocaleContracts(unittest.TestCase):
    def test_budget_table_is_distinct_from_existing_quote_vocabulary(self):
        self.assertIs(PAGE_WORDS, BUDGET_OBSERVATION)
        self.assertEqual(set(BUDGET_OBSERVATION), set(WORDS))
        self.assertTrue(all("policy" in v for v in BUDGET_OBSERVATION.values()))
        self.assertTrue(all("budget_heading" not in v for v in WORDS.values()))

    def test_only_literal_display_values_are_classified_as_language_data(self):
        path = "exchange/gas_disclosure_locales.py"
        source = (Path(__file__).resolve().parents[1] / path).read_text(encoding="utf-8")
        self.assertIsNotNone(observations.NON_ENGLISH_PROSE.search(source))
        view = observations._localized_language_view(path, source)
        self.assertIsNone(observations.NON_ENGLISH_PROSE.search(view))
        technical = source + "\n# " + chr(0x4e2d) + "\n"
        self.assertIsNotNone(observations.NON_ENGLISH_PROSE.search(
            observations._localized_language_view(path, technical)))
