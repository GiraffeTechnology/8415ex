"""NFT0 price currency and separate native price-balance admission.

Available units exclude reservations and the separately reported original
freeze. Only a verifier authenticated against the original native journal can
prove that frozen units belong to this exact escrow. No conversion or send.
"""
from copy import deepcopy
import re


class NFT0PriceBalanceGate:
    def __init__(self, read_native, verify_native):
        if not callable(read_native) or not callable(verify_native):
            raise ValueError("original price-balance reader and verifier required")
        self.read_native, self.verify_native = read_native, verify_native

    def admit(self, match, currency, escrow_id, now, gas_admission=None):
        refused = {"allowed": False, "code": "EX_PRICE_BALANCE_UNVERIFIED",
                   "warning": "NFT0 price-currency balance is unverified; trading is disabled."}
        if match.quote_asset != currency:
            return dict(refused, code="EX_NFT0_CURRENCY_MISMATCH",
                        warning="Use NFT0 price currency; EX does not exchange or substitute currencies.")
        request = {"chainId": match.asset.chain_id, "buyer": match.buyer,
                   "contract": match.asset.contract, "tokenId": str(match.asset.token_id),
                   "sellIntentDigest": match.sell_intent_digest,
                   "buyIntentDigest": match.buy_intent_digest, "currency": currency,
                   "principalBaseUnits": str(match.price), "originalEscrowId": escrow_id}
        try:
            row = deepcopy(self.read_native(deepcopy(request), now))
            fields = {"request", "currency", "unit", "availableBaseUnits", "boundFrozenBaseUnits",
                      "blockNumber", "blockHash", "observedAt", "sourceReference"}
            if (type(now) is not int or now < 0 or type(row) is not dict or set(row) != fields
                    or row["request"] != request or row["currency"] != currency
                    or row["unit"] != "base-units"
                    or any(type(row[k]) is not int or not 0 <= row[k] < 2 ** 256
                           for k in ("availableBaseUnits", "boundFrozenBaseUnits", "blockNumber", "observedAt"))
                    or (escrow_id is None and row["boundFrozenBaseUnits"] != 0)
                    or not 0 <= now - row["observedAt"] <= 30
                    or type(row["blockHash"]) is not str
                    or re.fullmatch(r"0x[0-9a-fA-F]{64}", row["blockHash"]) is None
                    or int(row["blockHash"], 16) == 0
                    or type(row["sourceReference"]) is not str or not row["sourceReference"].strip()
                    or self.verify_native(deepcopy(request), deepcopy(row)) is not True):
                return refused
        except Exception:
            return refused
        covered = row["availableBaseUnits"] + row["boundFrozenBaseUnits"]
        if covered < match.price:
            return dict(refused, code="EX_PRICE_BALANCE_INSUFFICIENT",
                        warning="Insufficient NFT0 price-currency balance; trading is disabled.")
        if currency == "ETH":
            # Both liabilities use wei. The original snapshot must exclude all
            # reservations, including the disjoint principal freeze. A single
            # available wei cannot cover both unfrozen principal and gas.
            gas = gas_admission
            try:
                if (type(gas) is not dict or gas.get("allowed") is not True
                        or gas.get("asset") != "ETH" or gas.get("unit") != "wei"
                        or (gas.get("blockNumber"), gas.get("blockHash"), gas.get("observedAt"))
                           != (row["blockNumber"], row["blockHash"], row["observedAt"])):
                    return refused
                required_gas = int(gas["requiredWei"])
                gas_available = int(gas["balanceWei"]) - int(gas["reservedWei"])
                remaining_principal = max(0, match.price - row["boundFrozenBaseUnits"])
                needed = remaining_principal + required_gas
                if required_gas <= 0 or gas_available < 0:
                    return refused
                if min(row["availableBaseUnits"], gas_available) < needed:
                    return dict(refused, code="EX_ETH_COMBINED_BALANCE_INSUFFICIENT",
                                warning="ETH cannot cover both this price and gas; trading is disabled.")
            except (KeyError, TypeError, ValueError):
                return refused
        return {"allowed": True, "code": None, "warning": None, "currency": currency,
                "unit": "base-units", "conversionPerformed": False,
                "nativeAtomicRecheckRequired": True}
