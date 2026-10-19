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
            shortfall = match.price - covered
            return dict(refused, code="EX_PRICE_BALANCE_INSUFFICIENT", currency=currency,
                        unit="base-units", availableBaseUnits=str(row["availableBaseUnits"]),
                        boundFrozenBaseUnits=str(row["boundFrozenBaseUnits"]),
                        requiredPrincipalBaseUnits=str(match.price), shortfallBaseUnits=str(shortfall),
                        blockNumber=row["blockNumber"], blockHash=row["blockHash"], observedAt=row["observedAt"],
                        conversionPerformed=False, nativeAtomicRecheckRequired=True,
                        warning=f"Insufficient NFT0 price-currency balance for {currency}; available "
                        f"{row['availableBaseUnits']} base-units, original bound principal "
                        f"{row['boundFrozenBaseUnits']} base-units, required principal {match.price} base-units, "
                        f"shortfall {shortfall} base-units. Trading is disabled.")
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
                # Original prepaid gas covers only gas, never principal.
                bound_gas = int(gas.get("boundGasWei", "0"))
                needed = remaining_principal + max(0, required_gas - bound_gas)
                if required_gas <= 0 or gas_available < 0 or bound_gas < 0:
                    return refused
                if min(row["availableBaseUnits"], gas_available) < needed:
                    available = min(row["availableBaseUnits"], gas_available)
                    return dict(refused, code="EX_ETH_COMBINED_BALANCE_INSUFFICIENT",
                                currency="ETH", unit="wei", availableWei=str(available),
                                requiredPrincipalBaseUnits=str(match.price),
                                boundFrozenBaseUnits=str(row["boundFrozenBaseUnits"]),
                                remainingPrincipalWei=str(remaining_principal), requiredGasWei=str(required_gas),
                                boundGasWei=str(bound_gas), unfundedGasWei=str(max(0, required_gas - bound_gas)),
                                requiredUnfrozenWei=str(needed), shortfallWei=str(needed - available),
                                blockNumber=row["blockNumber"], blockHash=row["blockHash"], observedAt=row["observedAt"],
                                conversionPerformed=False, nativeAtomicRecheckRequired=True,
                                warning=f"ETH cannot cover both this price and gas; available {available} wei, "
                                f"remaining principal {remaining_principal} wei, "
                                f"unfunded gas {max(0, required_gas - bound_gas)} wei, "
                                f"required unfrozen {needed} wei, shortfall {needed - available} wei. "
                                "Trading is disabled.")
            except (KeyError, TypeError, ValueError):
                return refused
        return {"allowed": True, "code": None, "warning": None, "currency": currency,
                "unit": "base-units", "conversionPerformed": False,
                "nativeAtomicRecheckRequired": True}
