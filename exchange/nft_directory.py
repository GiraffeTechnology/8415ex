"""Server-supplied receipt bindings, never a client-selected source or wallet."""
import hashlib
from types import MappingProxyType
import re
from .errors import DomainError


class OrderBookUnavailable(ValueError):
    pass


class NftDirectory:
    def __init__(self, bindings, *, allow_empty=False):
        if type(allow_empty) is not bool:
            raise ValueError("explicit empty directory policy required")
        rows = {}
        for binding in bindings:
            receipt_id = binding.receipt_id
            if not isinstance(receipt_id, str) or not receipt_id:
                raise ValueError("original receipt identity required")
            key = hashlib.sha256(receipt_id.encode("utf-8")).hexdigest()
            if key in rows:
                raise ValueError("duplicate receipt binding")
            rows[key] = binding
        if not rows and not allow_empty:
            raise ValueError("at least one original receipt binding required")
        self._bindings = MappingProxyType(rows)

    def key_for(self, binding):
        key = hashlib.sha256(binding.receipt_id.encode("utf-8")).hexdigest()
        if self._bindings.get(key) is not binding:
            raise KeyError("receipt binding not registered")
        return key

    def detail(self, key):
        # Exact lookup: never fall back to the previously selected NFT.
        binding = self._bindings[key]
        try:
            detail = dict(binding.public_detail())
        except Exception:
            detail = {"schema": "8415ex-public-nft-detail/1",
                      "positions": {"current": None, "owner": None, "holder": None},
                      "gap": "unknown", "displayGap": {"state": "unknown"}, "signatureStatusByPosition": [],
                      "terms": {"status": "unavailable", "clauses": []},
                      "sourceStatus": "detail-source-unavailable",
                      "ordinaryTransfer": {"gapEqualityFinalityGateApplied": False,
                                           "executionEligibility": "not-evaluated"}}
        detail.pop("receiptId", None)
        detail["nftKey"] = key
        return detail

    def currency_choices(self, key):
        """Read only the selected original NFT's immutable settlement set."""
        binding = self._bindings[key]
        try:
            currencies = binding.exchange.receipt(binding.receipt_id).allowed_price_currencies
        except Exception:
            raise OrderBookUnavailable("original NFT currencies unavailable") from None
        if (type(currencies) is not tuple or len(currencies) > 32
                or any(type(value) is not str or not value or len(value) > 256
                       or any(ord(char) < 32 for char in value) for value in currencies)
                or len(set(currencies)) != len(currencies)):
            raise OrderBookUnavailable("original NFT currencies unavailable")
        return currencies

    def order_book(self, key, currency, *, limit=20):
        """Exact registered source; no detail reader or fallback NFT is used."""
        binding = self._bindings[key]
        reader = getattr(getattr(binding, "exchange", None), "order_book_view", None)
        if not callable(reader):
            raise OrderBookUnavailable("original order book unavailable")
        try:
            value = reader(binding.receipt_id, currency, limit=limit)
        except DomainError as error:
            if error.code in ("EX_PUBLIC_BOOK_CURRENCY_REFUSED", "EX_PUBLIC_BOOK_LIMIT_REFUSED"):
                raise
            raise OrderBookUnavailable("original order book unavailable") from None
        except Exception:
            raise OrderBookUnavailable("original order book unavailable") from None
        fields = {"schema", "currency", "priceUnit", "observedAt", "asks", "bids",
                  "execution", "funding", "conversionPerformed", "meaning"}
        def refused():
            raise OrderBookUnavailable("original order book projection refused")
        if (type(value) is not dict or set(value) != fields
                or value["schema"] != "8415ex-public-order-book/1"
                or value["currency"] != currency
                or value["priceUnit"] != "base-units-per-whole-nft"
                or type(value["observedAt"]) is not int
                or not 0 <= value["observedAt"] < 2**64
                or value["execution"] != "NOT_RUN" or value["funding"] != "NOT_RUN"
                or value["conversionPerformed"] is not False
                or value["meaning"] != "original domain price/time observation; no signing or execution"):
            refused()
        public = {name: value[name] for name in fields - {"asks", "bids"}}
        for name in ("asks", "bids"):
            side = value[name]
            if (type(side) is not dict or set(side) != {"rows", "total", "hasMore"}
                    or type(side["rows"]) is not list or len(side["rows"]) > limit
                    or type(side["total"]) is not int or side["total"] < len(side["rows"])
                    or len(side["rows"]) != min(side["total"], limit)
                    or type(side["hasMore"]) is not bool
                    or side["hasMore"] != (side["total"] > len(side["rows"]))):
                refused()
            rows = []
            for index, row in enumerate(side["rows"]):
                if (type(row) is not dict
                        or set(row) != {"priority", "priceBaseUnits", "wholeNFTs"}
                        or type(row["priority"]) is not int or row["priority"] != index + 1
                        or type(row["priceBaseUnits"]) is not str
                        or re.fullmatch(r"[1-9][0-9]{0,77}", row["priceBaseUnits"]) is None
                        or int(row["priceBaseUnits"]) >= 2**256 or row["wholeNFTs"] != "1"):
                    refused()
                rows.append(dict(row))
            public[name] = {"rows": rows, "total": side["total"], "hasMore": side["hasMore"]}
        public["nftKey"] = key
        return public

    def choices(self):
        # Each independent original reader supplies its own gap; no global flag.
        rows = []
        for key in self._bindings:
            try:
                detail = self.detail(key)
                rows.append({"nftKey": key, "gap": detail["gap"], "displayGap": detail.get("displayGap", {"state": "unknown"})})
            except Exception:
                rows.append({"nftKey": key, "gap": "unknown", "displayGap": {"state": "unknown"}})
        return rows

    def catalogue(self):
        return [self.detail(key) for key in self._bindings]
