"""Correlate original remint receipt logs without any execution or journal write."""
from copy import deepcopy
import json
import re
from .receipt_gas_observer import ReceiptGasObserver, _pairs, _quantity
from .remint_read_results import decode_remint_declaration


class RemintReceiptRefused(ValueError):
    pass


ZERO = "0x" + "0" * 40


def _word(value):
    if (type(value) is not str or re.fullmatch(r"0x[0-9a-f]{64}", value) is None
            or int(value[2:], 16) == 0):
        raise RemintReceiptRefused("Original nonzero bytes32 required")
    return value


def _address(value, *, zero=False):
    if (type(value) is not str or re.fullmatch(r"0x[0-9a-f]{40}", value) is None
            or not zero and value == ZERO):
        raise RemintReceiptRefused("Original canonical address required")
    return value


def _token(value):
    if (type(value) is not str or re.fullmatch(r"[1-9][0-9]{0,77}", value) is None
            or int(value) >= 2**256):
        raise RemintReceiptRefused("Original positive uint256 token required")
    return value


def _replacement(value):
    keys = {"billKey", "termsHash", "currencyDeclarationHash", "allowedCurrencies"}
    if type(value) is not dict or set(value) != keys:
        raise RemintReceiptRefused("Exact original replacement declaration required")
    currencies = value["allowedCurrencies"]
    if type(currencies) is not list or not 1 <= len(currencies) <= 32762:
        raise RemintReceiptRefused("Bounded original currency words required")
    values = [_word(value[k]) for k in ("billKey", "termsHash", "currencyDeclarationHash")]
    values += [_word(word) for word in currencies]
    integer = lambda n: n.to_bytes(32, "big")
    raw = integer(32) + b"".join(bytes.fromhex(v[2:]) for v in values[:3])
    raw += integer(128) + integer(len(currencies))
    raw += b"".join(bytes.fromhex(v[2:]) for v in values[3:])
    return decode_remint_declaration(raw)


class RemintReceiptObserver:
    """Reuse original receipt verification and an installed original ABI log decoder.

    The receipt observer authenticates exact raw bytes, original attempt/tx and
    canonical/finality policy. The original log decoder must authenticate the
    deployed contract ABI/code and decode those exact raw log bytes; it returns
    None for unrelated events. Shape alone does not establish this provenance.
    No default verifier/decoder, RPC, signer, retry or effect exists here.
    """
    def __init__(self, receipt_observer, decode_original_log):
        if type(receipt_observer) is not ReceiptGasObserver or not callable(decode_original_log):
            raise RemintReceiptRefused("Original receipt observer and ABI log decoder required")
        self.receipt_observer = receipt_observer
        self.decode_original_log = decode_original_log

    def observe(self, raw_receipt, *, attempt_id, transaction_hash, proof_reference,
                contract, operation_id, old_token_id, actor, replacement):
        try:
            contract, actor = _address(contract), _address(actor)
            operation_id, old_token_id = _word(operation_id), _token(old_token_id)
            expected = _replacement(deepcopy(replacement))
            gas = self.receipt_observer.observe(raw_receipt, chain_id=11155111,
                attempt_id=attempt_id, transaction_hash=transaction_hash,
                proof_reference=proof_reference)
            common = {"schema": "8415ex-remint-receipt-observation/1",
                      "transactionHash": transaction_hash, "operationId": operation_id,
                      "oldTokenId": old_token_id, "replayAllowed": False,
                      "businessAcceptance": "NOT_ESTABLISHED",
                      "finality": "Not inferred from receipt status",
                      "financialMutation": False}
            if gas is None:
                return dict(common, status="NOT_MINED_AT_READ", newTokenId=None, actualGasWei=None)
            common.update(blockHash=gas.block_hash, blockNumber=gas.block_number,
                          actualGasWei=str(gas.actual_wei), rawReceiptSHA256=gas.raw_sha256)
            if gas.outcome == "FAILED":
                return dict(common, status="FAILED_RECEIPT", newTokenId=None)
            receipt = json.loads(raw_receipt.decode("utf-8"), object_pairs_hook=_pairs)
            logs = receipt.get("logs")
            if type(logs) is not list or len(logs) > 4096:
                raise RemintReceiptRefused("Bounded complete original receipt logs required")
            decoded, prior = [], -1
            context = {"chainId": 11155111, "contract": contract,
                       "transactionHash": gas.transaction_hash,
                       "blockHash": gas.block_hash, "blockNumber": gas.block_number}
            for log in logs:
                if (type(log) is not dict or log.get("transactionHash") != gas.transaction_hash
                        or log.get("blockHash") != gas.block_hash
                        or _quantity(log.get("blockNumber")) != gas.block_number
                        or log.get("removed") is not False):
                    raise RemintReceiptRefused("Original nonremoved receipt log binding required")
                index = _quantity(log.get("logIndex"))
                if index <= prior:
                    raise RemintReceiptRefused("Distinct ordered original receipt logs required")
                prior = index
                address = _address(log.get("address"))
                if address != contract:
                    continue
                event = self.decode_original_log(deepcopy(log), dict(context, logIndex=index))
                if event is not None:
                    if type(event) is not dict or type(event.get("event")) is not str:
                        raise RemintReceiptRefused("Original ABI event required")
                    decoded.append((index, deepcopy(event)))

            matching = [(i,e) for i,e in decoded if e.get("event") == "NFT0Reminted"
                        and e.get("operationId") == operation_id]
            if not matching:
                # A same-operation idempotent call can return without emitting
                # another event. No event in this receipt is not task absence.
                return dict(common, status="NO_MATCHING_EVENT_AT_READ", newTokenId=None)
            if len(matching) != 1:
                raise RemintReceiptRefused("Unique original operation event required")
            event_index, event = matching[0]
            if (set(event) != {"event", "operationId", "oldTokenId", "newTokenId", "holder", "billKey"}
                    or event["oldTokenId"] != old_token_id or event["holder"] != actor
                    or event["billKey"] != expected["billKey"]):
                raise RemintReceiptRefused("Original remint event differs from bound operation")
            new_token = _token(event["newTokenId"])
            if new_token == old_token_id:
                raise RemintReceiptRefused("Original replacement token must be distinct")
            burns = [(i,e) for i,e in decoded if e.get("event") == "Transfer"
                     and e.get("tokenId") == old_token_id and e.get("from") == actor and e.get("to") == ZERO]
            mints = [(i,e) for i,e in decoded if e.get("event") == "Transfer"
                     and e.get("tokenId") == new_token and e.get("from") == ZERO and e.get("to") == actor]
            declarations = [(i,e) for i,e in decoded if e.get("event") == "NFT0Declared"
                            and e.get("tokenId") == new_token]
            if any(len(rows) != 1 for rows in (burns, mints, declarations)):
                raise RemintReceiptRefused("Original burn/mint/declaration events required")
            for _, transfer in burns + mints:
                if set(transfer) != {"event", "from", "to", "tokenId"}:
                    raise RemintReceiptRefused("Exact original Transfer event required")
            declaration_index, declared = declarations[0]
            if (set(declared) != {"event", "tokenId", *expected}
                    or _replacement({k: declared[k] for k in expected}) != expected):
                raise RemintReceiptRefused("Actual declaration differs from original replacement")
            if not burns[0][0] < mints[0][0] < declaration_index < event_index:
                raise RemintReceiptRefused("Original atomic remint event order differs")
            # No holder/contract address, private proof reference or raw error is
            # projected. The actual new ID comes from the original event.
            return dict(common, status="CORRELATED_ORIGINAL_RECEIPT", newTokenId=new_token,
                        declaration=deepcopy(expected),
                        logIndices={"oldBurn": burns[0][0], "newMint": mints[0][0],
                                    "declaration": declaration_index, "remint": event_index})
        except Exception:
            raise RemintReceiptRefused("Original remint receipt observation unavailable") from None
