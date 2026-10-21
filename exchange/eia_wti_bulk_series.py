"""Decode one explicitly selected EIA bulk series; no transport or lifecycle."""
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import re

from .eia_wti_spot_table import SCOPE

BULK_URL = "https://www.eia.gov/opendata/bulk/PET.zip"
MAX_SERIES_BYTES = 4 * 1024 * 1024


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate series field")
        result[key] = value
    return result


def _day(value):
    if type(value) is not str or re.fullmatch(r"[0-9]{8}", value) is None:
        raise ValueError("daily source date required")
    return date(int(value[:4]), int(value[4:6]), int(value[6:]))


def parse_eia_wti_bulk_series(raw):
    """Decode the PET.RWTC.D NDJSON member line selected by the caller.

    Copyright and upstream source are source facts, not a permission decision.
    The caller owns archive selection, transport limits and source policy.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_SERIES_BYTES:
        raise ValueError("bounded series bytes required")
    row = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                     parse_float=Decimal, parse_int=Decimal,
                     parse_constant=lambda value: (_ for _ in ()).throw(
                         ValueError("nonfinite source number")))
    if type(row) is not dict:
        raise ValueError("one series object required")
    expected = {
        "series_id": "PET.RWTC.D", "f": "D",
        "name": "Cushing, OK WTI Spot Price FOB, Daily",
        "units": "Dollars per Barrel", "unitsshort": "$/bbl",
        "geography": "USA-OK", "iso3166": "USA-OK",
    }
    if any(row.get(key) != value for key, value in expected.items()):
        raise ValueError("fixed daily WTI series metadata differs")
    for key in ("source", "copyright"):
        if (type(row.get(key)) is not str or not row[key].strip()
                or len(row[key]) > 256 or any(ord(c) < 32 for c in row[key])):
            raise ValueError("source attribution metadata required")
    updated_raw = row.get("last_updated")
    if type(updated_raw) is not str or len(updated_raw) > 64:
        raise ValueError("source update timestamp required")
    updated = datetime.fromisoformat(updated_raw)
    if updated.tzinfo is None or updated.utcoffset() is None:
        raise ValueError("source update offset required")
    start, end = _day(row.get("start")), _day(row.get("end"))
    if start > end or end > updated.date():
        raise ValueError("series date range differs")
    data = row.get("data")
    if type(data) is not list or not 0 < len(data) <= 100000:
        raise ValueError("bounded daily observations required")
    previous = None
    first = last = latest = None
    for item in data:
        if type(item) is not list or len(item) != 2:
            raise ValueError("daily observation pair required")
        day = _day(item[0])
        if day < start or day > end or (previous is not None and day >= previous):
            raise ValueError("daily dates must descend within the declared range")
        if first is None:
            first = day
        last, previous = day, day
        value = item[1]
        if value is None:
            continue
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ValueError("numeric source observation or null required")
        if value.as_tuple().exponent < -80 or value.adjusted() > 79:
            raise ValueError("source decimal exceeds reference bound")
        rendered = format(value, "f")
        if len(rendered) > 80:
            raise ValueError("source decimal exceeds reference bound")
        if latest is None:
            latest = day, value, rendered
    if first != end or last != start or latest is None:
        raise ValueError("complete declared series range required")
    day, value, rendered = latest
    if value <= 0:
        raise ValueError("latest reported price is not positive")
    return dict(SCOPE, price=rendered, sourceAsOf=day.isoformat(),
                sourcePrecision="date", sourceURL=BULK_URL,
                rawResponseSHA256=hashlib.sha256(raw).hexdigest(),
                sourceUpdatedAt=updated_raw, upstreamSource=row["source"],
                sourceCopyright=row["copyright"],
                responseDigestScope="selected-series-line")
