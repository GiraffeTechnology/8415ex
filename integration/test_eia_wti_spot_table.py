"""Synthetic fixed-source decoder regressions; no transport or live prices."""
import unittest

from exchange.eia_wti_spot_table import SOURCE_URL, TITLE, parse_eia_wti_spot_table


def page(rows, publication="10/15/2026", title=TITLE, header=None):
    header = header or ["Week Of", "Mon", "Tue", "Wed", "Thu", "Fri"]
    cells = lambda tag, values: "<tr>" + "".join(
        "<" + tag + ">" + value + "</" + tag + ">" for value in values) + "</tr>"
    return ("<html><table><tr><td><table summary='" + title + "'>"
            + cells("th", header) + "".join(cells("td", row) for row in rows)
            + "</table></td></tr></table><p>Release Date: " + publication
            + "</p></html>").encode()


class EIAWTISpotTableTests(unittest.TestCase):
    def test_partial_week_keeps_original_date_and_decimal(self):
        raw = page([["2026 Oct-12 to Oct-16", "1.10", "2.20", "3.300", "", ""]])
        row = parse_eia_wti_spot_table(raw)
        self.assertEqual((row["price"], row["sourceAsOf"], row["sourcePrecision"]),
                         ("3.300", "2026-10-14", "date"))
        self.assertEqual((row["currency"], row["unit"], row["priceType"]),
                         ("USD", "barrel", "spot-reference"))
        self.assertEqual(row["series"], "PET.RWTC.D")
        self.assertEqual(row["sourceURL"], SOURCE_URL)
        self.assertEqual(len(row["rawResponseSHA256"]), 64)

    def test_declared_missing_values_are_not_zero_or_newer_prices(self):
        row = parse_eia_wti_spot_table(page([
            ["2026 Oct- 5 to Oct- 9", "1", "2", "3", "4", "5"],
            ["", "", "", "", "", ""],
            ["2026 Oct-12 to Oct-16", "-", "--", "NA", "W", ""],
        ]))
        self.assertEqual((row["price"], row["sourceAsOf"]), ("5", "2026-10-09"))

    def test_year_boundary_binds_each_weekday(self):
        row = parse_eia_wti_spot_table(page([
            ["1985 Dec-30 to Jan- 3", "", "", "", "25.56", "26.00"],
        ], publication="1/6/1986"))
        self.assertEqual(row["sourceAsOf"], "1986-01-03")

    def test_historical_negative_price_is_preserved_as_history_not_latest(self):
        row = parse_eia_wti_spot_table(page([
            ["2020 Apr-20 to Apr-24", "-36.98", "8.91", "", "", ""],
            ["2026 Oct-12 to Oct-16", "1", "", "", "", ""],
        ]))
        self.assertEqual(row["sourceAsOf"], "2026-10-12")

    def test_latest_nonpositive_never_falls_back_to_older_positive(self):
        for value in ("-1.20", "0", "0.000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_eia_wti_spot_table(page([
                    ["2026 Oct-12 to Oct-16", "2", value, "", "", ""],
                ]))

    def test_wrong_series_or_weekday_columns_refused(self):
        rows = [["2026 Oct-12 to Oct-16", "1", "", "", "", ""]]
        with self.assertRaises(ValueError):
            parse_eia_wti_spot_table(page(rows, title="Another futures or spot series"))
        with self.assertRaises(ValueError):
            parse_eia_wti_spot_table(page(rows,
                header=["Week Of", "Tue", "Mon", "Wed", "Thu", "Fri"]))

    def test_duplicate_or_reversed_weeks_refused(self):
        a = ["2026 Oct- 5 to Oct- 9", "1", "", "", "", ""]
        b = ["2026 Oct-12 to Oct-16", "2", "", "", "", ""]
        for rows in ([a, a], [b, a]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                parse_eia_wti_spot_table(page(rows))

    def test_malformed_decimal_and_row_width_refused(self):
        for value in ("NaN", "Infinity", "1,000", "1e2", "USD 1.20"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_eia_wti_spot_table(page([
                    ["2026 Oct-12 to Oct-16", value, "", "", "", ""],
                ]))
        with self.assertRaises(ValueError):
            parse_eia_wti_spot_table(page([["2026 Oct-12 to Oct-16", "1"]]))

    def test_calendar_and_publication_boundaries_refused(self):
        for week in ("2026 Oct-13 to Oct-17", "2026 Oct-12 to Oct-15",
                     "2026 Xxx-12 to Oct-16", "2026 Feb-30 to Mar- 6"):
            with self.subTest(week=week), self.assertRaises(ValueError):
                parse_eia_wti_spot_table(page([[week, "1", "", "", "", ""]]))
        with self.assertRaises(ValueError):
            parse_eia_wti_spot_table(page([
                ["2026 Oct-12 to Oct-16", "", "", "", "", "1"],
            ], publication="10/15/2026"))

    def test_absent_duplicate_or_incomplete_source_refused(self):
        with self.assertRaises(ValueError):
            parse_eia_wti_spot_table(page([
                ["2026 Oct-12 to Oct-16", "", "", "", "", ""],
            ]))
        one = page([["2026 Oct-12 to Oct-16", "1", "", "", "", ""]])
        with self.assertRaises(ValueError):
            parse_eia_wti_spot_table(one + one)
        with self.assertRaises(ValueError):
            parse_eia_wti_spot_table(one.replace(b"</table>", b"", 1))

    def test_bounded_utf8_bytes_only(self):
        for raw in ("not bytes", b"", b"\xff", b"x" * (2 * 1024 * 1024 + 1)):
            with self.subTest(kind=type(raw).__name__), self.assertRaises((ValueError, UnicodeError)):
                parse_eia_wti_spot_table(raw)


if __name__ == "__main__":
    unittest.main()
