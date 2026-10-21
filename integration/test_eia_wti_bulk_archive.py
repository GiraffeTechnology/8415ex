"""Synthetic definitions; no network, source downloads or service startup."""
import hashlib
import io
import json
import stat
import struct
import unittest
import zipfile

from exchange.eia_wti_bulk_archive import select_eia_wti_bulk_archive


class WTIBulkArchiveTests(unittest.TestCase):
    def line(self):
        row = {
            "series_id": "PET.RWTC.D", "f": "D",
            "name": "Cushing, OK WTI Spot Price FOB, Daily",
            "units": "Dollars per Barrel", "unitsshort": "$/bbl",
            "geography": "USA-OK", "iso3166": "USA-OK",
            "source": "Synthetic source", "copyright": "Synthetic rights",
            "last_updated": "2026-10-15T18:43:40-04:00",
            "start": "20261014", "end": "20261014",
            "data": [["20261014", 81.25]],
        }
        return json.dumps(row).encode() + b"\n"

    def archive(self, members, compression=zipfile.ZIP_DEFLATED):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", compression=compression) as archive:
            for name, raw in members:
                archive.writestr(name, raw)
        return out.getvalue()

    def test_selected_line_and_archive_have_separate_identities(self):
        line = self.line()
        member = b'{"category_id":1}\n' + line + b'{"series_id":"OTHER","data":[]}\n'
        raw = self.archive([("PET.txt", member)])
        result = select_eia_wti_bulk_archive(raw)
        self.assertEqual(result["observation"]["series"], "PET.RWTC.D")
        self.assertEqual(result["observation"]["rawResponseSHA256"],
                         hashlib.sha256(line).hexdigest())
        evidence = result["archiveEvidence"]
        self.assertEqual(evidence["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(evidence["memberSHA256"], hashlib.sha256(member).hexdigest())
        self.assertEqual(evidence["memberBytes"], len(member))
        self.assertEqual(evidence["lineCount"], 3)

    def test_stored_and_deflated_formats(self):
        for compression in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raw = self.archive([("PET.txt", self.line())], compression)
            self.assertEqual(select_eia_wti_bulk_archive(raw)["observation"]["price"], "81.25")

    def test_wrong_nested_and_multiple_members(self):
        for members in ([("OTHER.txt", self.line())],
                        [("../PET.txt", self.line())],
                        [("PET.txt", self.line()), ("extra", b"{}")]):
            with self.assertRaises(ValueError):
                select_eia_wti_bulk_archive(self.archive(members))

    def test_duplicate_and_missing_fixed_series(self):
        for member in (self.line() * 2, b'{"series_id":"PET.RWTC.M"}\n'):
            with self.assertRaises(ValueError):
                select_eia_wti_bulk_archive(self.archive([("PET.txt", member)]))

    def test_malformed_trailing_content_is_not_ignored(self):
        for suffix in (b"broken", b"[]\n", b'{"series_id":"OTHER","series_id":"PET.RWTC.D"}\n'):
            with self.assertRaises(ValueError):
                select_eia_wti_bulk_archive(
                    self.archive([("PET.txt", self.line() + suffix)]))

    def test_oversized_line(self):
        member = self.line() + b" " * (4 * 1024 * 1024 + 1)
        with self.assertRaises(ValueError):
            select_eia_wti_bulk_archive(self.archive([("PET.txt", member)]))

    def test_declared_member_bound(self):
        raw = bytearray(self.archive([("PET.txt", self.line())]))
        central = raw.index(b"PK\x01\x02")
        struct.pack_into("<I", raw, central + 24, 512 * 1024 * 1024 + 1)
        with self.assertRaises(ValueError):
            select_eia_wti_bulk_archive(bytes(raw))

    def test_symlink_and_unsupported_compression(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            info = zipfile.ZipInfo("PET.txt")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, self.line())
        with self.assertRaises(ValueError):
            select_eia_wti_bulk_archive(out.getvalue())
        raw = self.archive([("PET.txt", self.line())], zipfile.ZIP_BZIP2)
        with self.assertRaises(ValueError):
            select_eia_wti_bulk_archive(raw)

    def test_crc_failure(self):
        raw = bytearray(self.archive([("PET.txt", self.line())], zipfile.ZIP_STORED))
        location = raw.index(b"Synthetic source")
        raw[location] = ord("X")
        with self.assertRaises(ValueError):
            select_eia_wti_bulk_archive(bytes(raw))

    def test_invalid_or_unbounded_transport_input(self):
        for raw in (b"", b"not a zip", "not bytes",
                    b"x" * (64 * 1024 * 1024 + 1)):
            with self.assertRaises(ValueError):
                select_eia_wti_bulk_archive(raw)


if __name__ == "__main__":
    unittest.main()
