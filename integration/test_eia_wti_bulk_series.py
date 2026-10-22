"""Synthetic contract definitions for the explicitly selected bulk series."""
import hashlib
import json
import unittest

from exchange.eia_wti_bulk_series import parse_eia_wti_bulk_series


class WTIBulkSeriesTests(unittest.TestCase):
    def row(self):
        return {
            "series_id": "PET.RWTC.D", "f": "D",
            "name": "Cushing, OK WTI Spot Price FOB, Daily",
            "units": "Dollars per Barrel", "unitsshort": "$/bbl",
            "geography": "USA-OK", "iso3166": "USA-OK",
            "source": "Synthetic attribution", "copyright": "Synthetic rights",
            "last_updated": "2026-10-15T18:43:40-04:00",
            "start": "20261012", "end": "20261014",
            "data": [["20261014", 81.25], ["20261013", 80], ["20261012", 79]],
        }

    def raw(self, row):
        return json.dumps(row, separators=(",", ":")).encode()

    def test_fixed_scope_precision_and_line_identity(self):
        raw = self.raw(self.row())
        result = parse_eia_wti_bulk_series(raw)
        self.assertEqual(result["series"], "PET.RWTC.D")
        self.assertEqual(result["price"], "81.25")
        self.assertEqual(result["sourceAsOf"], "2026-10-14")
        self.assertEqual(result["sourcePrecision"], "date")
        self.assertEqual(result["sourceCopyright"], "Synthetic rights")
        self.assertEqual(result["sourceUpdatedAt"], "2026-10-15T18:43:40-04:00")
        self.assertEqual(result["rawResponseSHA256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["responseDigestScope"], "selected-series-line")
        self.assertNotIn("publicationDate", result)

    def test_wrong_series_frequency_unit_and_market(self):
        for key, value in (("series_id", "PET.RWTC.M"), ("f", "M"),
                           ("units", "Dollars per Gallon"), ("geography", "USA-TX")):
            with self.subTest(key=key):
                row = self.row()
                row[key] = value
                with self.assertRaises(ValueError):
                    parse_eia_wti_bulk_series(self.raw(row))

    def test_null_is_missing_and_historical_negative_is_preserved_in_input(self):
        row = self.row()
        row["data"][0][1] = None
        row["data"][2][1] = -37.63
        result = parse_eia_wti_bulk_series(self.raw(row))
        self.assertEqual(result["price"], "80")
        self.assertEqual(result["sourceAsOf"], "2026-10-13")

    def test_nonpositive_latest_does_not_fall_back(self):
        for value in (0, -37.63):
            row = self.row()
            row["data"][0][1] = value
            with self.assertRaises(ValueError):
                parse_eia_wti_bulk_series(self.raw(row))

    def test_duplicate_reversed_and_outside_dates(self):
        for value in ("20261014", "20261015", "20261011"):
            row = self.row()
            row["data"][1][0] = value
            with self.assertRaises(ValueError):
                parse_eia_wti_bulk_series(self.raw(row))

    def test_incomplete_range_and_invalid_calendar(self):
        for key, value in (("start", "20261011"), ("end", "20261013"),
                           ("start", "20260230")):
            row = self.row()
            row[key] = value
            with self.assertRaises(ValueError):
                parse_eia_wti_bulk_series(self.raw(row))

    def test_attribution_and_update_offset_required(self):
        for key, value in (("copyright", ""), ("source", None),
                           ("last_updated", "2026-10-15T18:43:40"),
                           ("last_updated", "2026-10-13T18:43:40-04:00")):
            row = self.row()
            row[key] = value
            with self.assertRaises(ValueError):
                parse_eia_wti_bulk_series(self.raw(row))

    def test_non_numeric_and_nonfinite_prices(self):
        for value in ("81.25", True, float("inf"), float("nan")):
            row = self.row()
            row["data"][0][1] = value
            with self.assertRaises(ValueError):
                parse_eia_wti_bulk_series(self.raw(row))

    def test_extreme_decimal_exponents_are_bounded(self):
        raw = self.raw(self.row())
        for number in (b"1e1000000000", b"1e-1000000000"):
            with self.assertRaises(ValueError):
                parse_eia_wti_bulk_series(raw.replace(b"81.25", number))

    def test_duplicate_fields_and_multiple_lines(self):
        raw = self.raw(self.row())
        for malformed in (raw[:-1] + b',"f":"D"}', raw + b"\n" + raw):
            with self.assertRaises(ValueError):
                parse_eia_wti_bulk_series(malformed)

    def test_empty_and_oversized_input(self):
        for raw in (b"", b" " * (4 * 1024 * 1024 + 1), "not bytes"):
            with self.assertRaises(ValueError):
                parse_eia_wti_bulk_series(raw)


if __name__ == "__main__":
    unittest.main()
