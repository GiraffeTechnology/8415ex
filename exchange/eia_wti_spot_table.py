"""Decode only the original EIA daily WTI spot table; no network or execution."""
from datetime import date, timedelta
import hashlib
from html.parser import HTMLParser
import re

SOURCE_URL = "https://www.eia.gov/dnav/pet/hist/RWTCD.htm"
TITLE = "Cushing, OK WTI Spot Price FOB (Dollars per Barrel)"
SCOPE = {
    "provider": "U.S. Energy Information Administration",
    "series": "PET.RWTC.D",
    "commodity": "crude-oil",
    "spec": "WTI",
    "market": "Cushing, Oklahoma; FOB",
    "priceType": "spot-reference",
    "currency": "USD",
    "unit": "barrel",
}
MONTHS = {name: index for index, name in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
WEEK = re.compile(r"(\d{4}) ([A-Za-z]{3})-\s*(\d{1,2}) to ([A-Za-z]{3})-\s*(\d{1,2})")
MISSING = {"", "-", "--", "NA", "W"}


def _text(value):
    return " ".join(value.split())


class _SpotTable(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.selected = None
        self.tables = 0
        self.row = None
        self.cell = None
        self.rows = []
        self.release_dates = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self.selected is not None:
                raise ValueError("nested spot table refused")
            self.depth += 1
            values = [value for key, value in attrs if key == "summary"]
            if len(values) > 1:
                raise ValueError("ambiguous table identity")
            if values and _text(values[0] or "") == TITLE:
                self.tables += 1
                if self.tables != 1:
                    raise ValueError("duplicate spot series")
                self.selected = self.depth
        elif self.selected is not None:
            if tag == "tr":
                if self.row is not None:
                    raise ValueError("unclosed spot row")
                self.row = []
            elif tag in ("td", "th"):
                if self.row is None or self.cell is not None:
                    raise ValueError("unclosed spot cell")
                self.cell = []
            elif tag in ("script", "iframe", "object"):
                raise ValueError("active spot table content refused")

    def handle_endtag(self, tag):
        if self.selected is not None:
            if tag in ("td", "th"):
                if self.cell is None or self.row is None:
                    raise ValueError("spot cell boundary differs")
                self.row.append(_text("".join(self.cell)))
                self.cell = None
            elif tag == "tr":
                if self.row is None or self.cell is not None:
                    raise ValueError("spot row boundary differs")
                self.rows.append(self.row)
                self.row = None
                if len(self.rows) > 5000:
                    raise ValueError("spot row bound exceeded")
            elif tag == "table" and self.depth == self.selected:
                if self.row is not None or self.cell is not None:
                    raise ValueError("incomplete spot table")
                self.selected = None
        if tag == "table":
            self.depth -= 1
            if self.depth < 0:
                raise ValueError("table boundary differs")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)
        value = _text(data)
        if value.startswith("Release Date:"):
            self.release_dates.append(value)


def parse_eia_wti_spot_table(raw):
    """Return the latest reported daily record, with source precision unchanged.

    Empty future weekday cells and declared missing markers are not zero.
    Historical negative values are valid source records; a latest nonpositive
    value is unavailable to the existing positive-price reference contract,
    rather than silently replaced by an older positive observation.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= 2 * 1024 * 1024:
        raise ValueError("bounded original source bytes required")
    parsed = _SpotTable()
    parsed.feed(raw.decode("utf-8"))
    parsed.close()
    if (parsed.tables != 1 or parsed.selected is not None or parsed.row is not None
            or parsed.cell is not None or parsed.depth != 0):
        raise ValueError("complete fixed daily spot table required")
    if not parsed.rows or parsed.rows[0] != ["Week Of", "Mon", "Tue", "Wed", "Thu", "Fri"]:
        raise ValueError("daily weekday columns differ")
    if len(parsed.release_dates) != 1:
        raise ValueError("one original publication date required")
    publication = re.fullmatch(r"Release Date:\s*(\d{1,2})/(\d{1,2})/(\d{4})",
                               parsed.release_dates[0])
    if publication is None:
        raise ValueError("publication date differs")
    month, day, year = map(int, publication.groups())
    published = date(year, month, day)
    previous, latest = None, None
    for row in parsed.rows[1:]:
        if len(row) == 6 and not any(row):
            continue
        if len(row) != 6:
            raise ValueError("daily spot row width differs")
        match = WEEK.fullmatch(row[0])
        if match is None:
            raise ValueError("daily spot week differs")
        year, first_month, first_day, last_month, last_day = match.groups()
        if first_month not in MONTHS or last_month not in MONTHS:
            raise ValueError("source month differs")
        year = int(year)
        start = date(year, MONTHS[first_month], int(first_day))
        end = date(year + (MONTHS[last_month] < MONTHS[first_month]),
                   MONTHS[last_month], int(last_day))
        if start.weekday() != 0 or end != start + timedelta(days=4):
            raise ValueError("source weekday binding differs")
        if previous is not None and start <= previous:
            raise ValueError("duplicate or reversed source week")
        previous = start
        for offset, value in enumerate(row[1:]):
            if value in MISSING:
                continue
            if len(value) > 80 or re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value) is None:
                raise ValueError("source decimal differs")
            observed = start + timedelta(days=offset)
            if observed > published:
                raise ValueError("observation exceeds publication date")
            latest = observed, value
    if latest is None:
        raise ValueError("no reported daily spot record")
    observed, value = latest
    if value.startswith("-") or not any(char in "123456789" for char in value):
        raise ValueError("latest record is not a positive reference price")
    return dict(SCOPE, price=value, sourceAsOf=observed.isoformat(), sourcePrecision="date",
                publicationDate=published.isoformat(), sourceURL=SOURCE_URL,
                rawResponseSHA256=hashlib.sha256(raw).hexdigest())
