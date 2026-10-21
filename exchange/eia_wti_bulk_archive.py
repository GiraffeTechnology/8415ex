"""Select the fixed daily WTI series from bounded EIA petroleum ZIP bytes."""
import hashlib
import io
import json
import stat
import struct
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



def _reject_constant(value):
    raise ValueError("nonfinite petroleum JSON constant")


def _verify_member_stream(raw, entry, central_start):
    """Validate the local header and complete physical compressed stream."""
    offset = entry.header_offset
    if type(offset) is not int or offset < 0 or offset + 30 > len(raw):
        raise ValueError("complete local petroleum header required")
    header = struct.unpack_from("<4s5H3I2H", raw, offset)
    signature, _, flags, method, _, _, crc, compressed, size, name_len, extra_len = header
    if (signature != b"PK\x03\x04" or flags != entry.flag_bits
            or method != entry.compress_type or flags & (1 | 64 | 8192)):
        raise ValueError("local petroleum flags or compression differ")
    start = offset + 30 + name_len + extra_len
    end = start + entry.compress_size
    if (raw[offset + 30:offset + 30 + name_len] != b"PET.txt"
            or not 0 <= start <= end <= central_start <= len(raw)):
        raise ValueError("bounded original local petroleum member required")
    # These bounded members use ordinary 32-bit local sizes. ZIP64 sentinels
    # are not silently interpreted as an authoritative ordinary-size header.
    if flags & 8:
        if any(value not in (0, expected) for value, expected in
               ((crc, entry.CRC), (compressed, entry.compress_size),
                (size, entry.file_size))):
            raise ValueError("local petroleum descriptor fields differ")
    elif (crc, compressed, size) != (entry.CRC, entry.compress_size, entry.file_size):
        raise ValueError("local and central petroleum sizes or CRC differ")
    total = checksum = 0
    def consume(block):
        nonlocal total, checksum
        total += len(block)
        if total > entry.file_size or total > MAX_MEMBER_BYTES:
            raise ValueError("actual petroleum member exceeds declared bound")
        checksum = zlib.crc32(block, checksum)
    view = memoryview(raw)
    if method == zipfile.ZIP_STORED:
        if entry.compress_size != entry.file_size:
            raise ValueError("stored petroleum member sizes differ")
        for position in range(start, end, 65536):
            consume(view[position:min(position + 65536, end)])
    else:
        decoder = zlib.decompressobj(-zlib.MAX_WBITS)
        for position in range(start, end, 65536):
            pending = view[position:min(position + 65536, end)]
            while True:
                block = decoder.decompress(pending, 65536)
                pending = decoder.unconsumed_tail
                consume(block)
                if decoder.unused_data:
                    raise ValueError("data follows petroleum compression endpoint")
                if not pending and len(block) < 65536:
                    break
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError("complete petroleum compression endpoint required")
    if total != entry.file_size or checksum != entry.CRC:
        raise ValueError("complete physical petroleum size and CRC required")


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
            _verify_member_stream(raw, entry, archive.start_dir)
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
                    row = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_fields,
                                     parse_constant=_reject_constant)
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
