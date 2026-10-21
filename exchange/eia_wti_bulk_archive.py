"""Select the fixed daily WTI series from bounded EIA petroleum ZIP bytes."""
import hashlib
import io
import json
import stat
import zipfile
import zlib

from .eia_wti_bulk_series import MAX_SERIES_BYTES, parse_eia_wti_bulk_series

MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 512 * 1024 * 1024
MAX_LINES = 1000000


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate petroleum field")
        result[key] = value
    return result


def select_eia_wti_bulk_archive(raw):
    """Return an observation plus independent archive/member identities.

    Input must come from an explicitly selected, independently checked source.
    No extraction to disk, transport, source switching or service startup occurs.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_ARCHIVE_BYTES:
        raise ValueError("bounded petroleum archive bytes required")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) != 1:
                raise ValueError("one original petroleum member required")
            entry = entries[0]
            file_type = stat.S_IFMT(entry.external_attr >> 16)
            if (entry.filename != "PET.txt" or entry.is_dir()
                    or file_type not in (0, stat.S_IFREG)
                    or entry.flag_bits & 1
                    or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                    or not 0 < entry.file_size <= MAX_MEMBER_BYTES):
                raise ValueError("bounded original petroleum member required")
            selected = None
            total = count = 0
            member_hash = hashlib.sha256()
            with archive.open(entry) as member:
                while True:
                    line = member.readline(MAX_SERIES_BYTES + 1)
                    if not line:
                        break
                    total += len(line)
                    count += 1
                    if (len(line) > MAX_SERIES_BYTES or total > MAX_MEMBER_BYTES
                            or count > MAX_LINES):
                        raise ValueError("petroleum member stream exceeds bounds")
                    member_hash.update(line)
                    row = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_fields)
                    if type(row) is not dict:
                        raise ValueError("petroleum line must be an object")
                    if row.get("series_id") == "PET.RWTC.D":
                        if selected is not None:
                            raise ValueError("duplicate fixed daily WTI series")
                        selected = parse_eia_wti_bulk_series(line)
            if total != entry.file_size or selected is None:
                raise ValueError("complete member and fixed daily WTI series required")
            return {
                "observation": selected,
                "archiveEvidence": {
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw), "member": entry.filename,
                    "memberBytes": total, "memberSHA256": member_hash.hexdigest(),
                    "lineCount": count,
                },
            }
    except (zipfile.BadZipFile, zipfile.LargeZipFile, UnicodeError,
            json.JSONDecodeError, RecursionError, NotImplementedError, EOFError, zlib.error) as error:
        raise ValueError("invalid petroleum archive content") from error
