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

    def admit(self, match, now, escrow_id=None):
        request = {"chainId": match.asset.chain_id, "buyer": match.buyer,
                   "contract": match.asset.contract, "tokenId": str(match.asset.token_id),
                   "sellIntentDigest": match.sell_intent_digest,
                   "buyIntentDigest": match.buy_intent_digest, "originalEscrowId": escrow_id}
        refused = {"allowed": False, "code": "EX_ETH_GAS_UNVERIFIED",
                   "warning": "ETH gas balance is unverified; trading is disabled.",
                   "asset": "ETH", "unit": "wei"}
        try:
            row = deepcopy(self.read_native(deepcopy(request), now))
            expected = {"request", "asset", "unit", "balanceWei", "reservedWei",
                        "requiredWei", "blockNumber", "blockHash", "observedAt",
                        "sourceReference"}
            if (type(now) is not int or now < 0 or type(row) is not dict
                    or set(row) not in (expected, expected | {"boundGasWei"}) or row["request"] != request
                    or row["asset"] != "ETH" or row["unit"] != "wei"
                    or any(type(row[k]) is not int or not 0 <= row[k] < 2 ** 256 for k in
                           ("balanceWei", "reservedWei", "requiredWei", "blockNumber", "observedAt"))
                    or type(row.get("boundGasWei", 0)) is not int
                    or not 0 <= row.get("boundGasWei", 0) < 2 ** 256
                    or (escrow_id is None and row.get("boundGasWei", 0) != 0)
                    or row["reservedWei"] > row["balanceWei"]
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
        bound_gas = row.get("boundGasWei", 0)
        available = row["balanceWei"] - row["reservedWei"]
        amounts = {"balanceWei": str(row["balanceWei"]), "reservedWei": str(row["reservedWei"]),
                   "availableWei": str(available), "boundGasWei": str(bound_gas),
                   "requiredWei": str(row["requiredWei"]),
                   "shortfallWei": str(max(0, row["requiredWei"] - available - bound_gas)),
                   "blockNumber": row["blockNumber"], "blockHash": row["blockHash"],
                   "observedAt": row["observedAt"], "nativeAtomicRecheckRequired": True}
        if row["balanceWei"] == 0 and bound_gas == 0:
            return dict(refused, **amounts, code="EX_ETH_GAS_EMPTY",
                        warning=f"No ETH is available for gas; available {available} wei, "
                        f"required {row['requiredWei']} wei, shortfall {amounts['shortfallWei']} wei. "
                        "Trading is disabled.")
        if available + bound_gas < row["requiredWei"]:
            return dict(refused, **amounts, code="EX_ETH_GAS_INSUFFICIENT",
                        warning=f"Available ETH cannot cover this operation's gas; available {available} wei, "
                        f"original bound gas {bound_gas} wei, required {row['requiredWei']} wei, "
                        f"shortfall {amounts['shortfallWei']} wei. Trading is disabled.")
        return {"allowed": True, "code": None, "warning": None, "asset": "ETH", "unit": "wei",
                "balanceWei": str(row["balanceWei"]), "reservedWei": str(row["reservedWei"]),
                "requiredWei": str(row["requiredWei"]), "boundGasWei": str(bound_gas),
                "blockNumber": row["blockNumber"], "blockHash": row["blockHash"],
                "observedAt": row["observedAt"],
                "nativeAtomicRecheckRequired": True}
