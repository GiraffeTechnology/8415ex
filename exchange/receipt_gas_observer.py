"""Read-only mined receipt gas observation for the existing budget contract."""
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from .gas_budget import GasConsumption, GasBudgetRefused


def _hash(value):
    if type(value) is not str or re.fullmatch(r'0x[0-9a-f]{64}', value) is None:
        raise GasBudgetRefused('canonical hash required')
    return value


def _quantity(value):
    if type(value) is not str or re.fullmatch(r'0x(?:0|[1-9a-f][0-9a-f]{0,63})', value) is None:
        raise GasBudgetRefused('canonical bounded quantity required')
    return int(value, 16)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GasBudgetRefused('duplicate receipt field')
        result[key] = value
    return result


@dataclass(frozen=True)
class ReceiptGasObservation:
    chain_id: int
    attempt_id: str
    transaction_hash: str
    block_hash: str
    block_number: int
    gas_used: int
    effective_gas_price: int
    actual_wei: int
    outcome: str
    raw_sha256: str
    proof_reference: str

    def consumption(self):
        return GasConsumption(self.attempt_id, self.transaction_hash,
                              self.actual_wei, self.outcome, self.proof_reference)


class ReceiptGasObserver:
    """No RPC client, wallet writes, retry, fallback or budget mutation.

    The verifier must authenticate the exact raw response, original attempt/tx
    association and current canonical/finality policy. A fixture returning True
    is not real chain evidence. Receipt status proves execution outcome only,
    never Oracle registration or successful business settlement.
    """
    def __init__(self, verify):
        if not callable(verify):
            raise GasBudgetRefused('original chain evidence verifier required')
        self.verify = verify

    def observe(self, raw_receipt, *, chain_id, attempt_id, transaction_hash,
                proof_reference):
        if type(chain_id) is not int or chain_id != 11155111:
            raise GasBudgetRefused('explicit Sepolia chain context required')
        for value in (attempt_id, proof_reference):
            if type(value) is not str or not value.strip() or len(value) > 256:
                raise GasBudgetRefused('bounded original identity required')
        _hash(transaction_hash)
        if type(raw_receipt) is not bytes or not 1 <= len(raw_receipt) <= 262144:
            raise GasBudgetRefused('bounded original receipt bytes required')
        try:
            receipt = json.loads(raw_receipt.decode('utf-8'), object_pairs_hook=_pairs,
                                 parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, UnicodeError, RecursionError):
            raise GasBudgetRefused('invalid original receipt JSON') from None
        if receipt is None:
            return None  # pending/not found is unknown, never zero-cost settlement
        if type(receipt) is not dict:
            raise GasBudgetRefused('receipt result object required')
        required = ('transactionHash', 'blockHash', 'blockNumber', 'gasUsed',
                    'effectiveGasPrice', 'status', 'type')
        if any(key not in receipt or receipt[key] is None for key in required):
            raise GasBudgetRefused('mined complete receipt required')
        if _hash(receipt['transactionHash']) != transaction_hash:
            raise GasBudgetRefused('original transaction mismatch')
        block_hash = _hash(receipt['blockHash'])
        block_number = _quantity(receipt['blockNumber'])
        gas_used = _quantity(receipt['gasUsed'])
        price = _quantity(receipt['effectiveGasPrice'])
        status = _quantity(receipt['status'])
        kind = _quantity(receipt['type'])
        if status not in (0, 1) or kind not in (0, 1, 2):
            raise GasBudgetRefused('unsupported receipt outcome or fee model')
        # Blob fees and provider-specific additional fees cannot be silently omitted.
        if any(key in receipt for key in ('blobGasUsed', 'blobGasPrice', 'l1Fee',
                                          'l1GasUsed', 'l1GasPrice')):
            raise GasBudgetRefused('additional fee model requires original adapter')
        if gas_used == 0:
            raise GasBudgetRefused('zero mined gas is not applicable')
        actual = gas_used * price
        raw_hash = sha256(raw_receipt).hexdigest()
        evidence = {'chainId': chain_id, 'attemptId': attempt_id,
                    'transactionHash': transaction_hash, 'blockHash': block_hash,
                    'blockNumber': block_number, 'rawSHA256': raw_hash,
                    'rawReceipt': raw_receipt, 'proofReference': proof_reference,
                    'gasUsed': gas_used, 'effectiveGasPrice': price,
                    'actualWei': actual, 'status': status, 'transactionType': kind}
        try:
            verified = self.verify(evidence)
        except Exception:
            raise GasBudgetRefused('original chain verification unavailable') from None
        if verified is not True:
            raise GasBudgetRefused('original canonical receipt evidence not verified')
        return ReceiptGasObservation(chain_id, attempt_id, transaction_hash,
            block_hash, block_number, gas_used, price, actual,
            'SUCCESS' if status == 1 else 'FAILED', raw_hash, proof_reference)
