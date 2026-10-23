"""ETH-only trade admission from the installed authenticated wallet reader.

This gate never queries an invented RPC, signs, reserves, sends or settles.
The native execution gate must recheck balance, reservations and fees atomically.
"""
from copy import deepcopy
import re


class ETHTradeGasGate:
    def __init__(self, read_native, verify_native, max_age_seconds=30):
        if not callable(read_native) or not callable(verify_native):
            raise ValueError("original wallet reader and verifier required")
        if type(max_age_seconds) is not int or not 0 <= max_age_seconds <= 30:
            raise ValueError("bounded observation age required")
        self.read_native = read_native
        self.verify_native = verify_native
        self.max_age_seconds = max_age_seconds

    def admit(self, match, now):
        request = {"chainId": match.asset.chain_id, "buyer": match.buyer,
                   "contract": match.asset.contract, "tokenId": str(match.asset.token_id),
                   "sellIntentDigest": match.sell_intent_digest,
                   "buyIntentDigest": match.buy_intent_digest}
        refused = {"allowed": False, "code": "EX_ETH_GAS_UNVERIFIED",
                   "warning": "ETH gas balance is unverified; trading is disabled.",
                   "asset": "ETH", "unit": "wei"}
        try:
            row = deepcopy(self.read_native(deepcopy(request), now))
            expected = {"request", "asset", "unit", "balanceWei", "reservedWei",
                        "requiredWei", "blockNumber", "blockHash", "observedAt",
                        "sourceReference"}
            if (type(now) is not int or now < 0 or type(row) is not dict
                    or set(row) != expected or row["request"] != request
                    or row["asset"] != "ETH" or row["unit"] != "wei"
                    or any(type(row[k]) is not int or row[k] < 0 for k in
                           ("balanceWei", "reservedWei", "requiredWei", "blockNumber", "observedAt"))
                    or row["requiredWei"] == 0
                    or not 0 <= now - row["observedAt"] <= self.max_age_seconds
                    or type(row["blockHash"]) is not str
                    or re.fullmatch(r"0x[0-9a-fA-F]{64}", row["blockHash"]) is None
                    or int(row["blockHash"], 16) == 0
                    or type(row["sourceReference"]) is not str
                    or not row["sourceReference"].strip()
                    or self.verify_native(deepcopy(request), deepcopy(row)) is not True):
                return refused
        except Exception:
            return refused
        if row["balanceWei"] == 0:
            return dict(refused, code="EX_ETH_GAS_EMPTY",
                        warning="No ETH is available for gas. Add ETH before trading.")
        available = row["balanceWei"] - row["reservedWei"]
        if available < row["requiredWei"]:
            return dict(refused, code="EX_ETH_GAS_INSUFFICIENT",
                        warning="Available ETH cannot cover this operation's gas; trading is disabled.")
        return {"allowed": True, "code": None, "warning": None, "asset": "ETH", "unit": "wei",
                "balanceWei": str(row["balanceWei"]), "reservedWei": str(row["reservedWei"]),
                "requiredWei": str(row["requiredWei"]),
                "blockNumber": row["blockNumber"], "blockHash": row["blockHash"],
                "observedAt": row["observedAt"],
                "nativeAtomicRecheckRequired": True}
