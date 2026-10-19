"""Server-supplied receipt bindings, never a client-selected source or wallet."""
import hashlib
from types import MappingProxyType


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
