"""Bounded read-only receipt lookup through an injected existing RPC transport."""
import json
from .gas_budget import GasBudgetRefused
from .receipt_gas_observer import ReceiptGasObserver, _pairs, _quantity, _hash


class OriginalGasReceiptReader:
    """No endpoint selection, retry, signing, sending or financial mutation."""
    def __init__(self, original_rpc, verify_original_attempt):
        if not callable(original_rpc) or not callable(verify_original_attempt):
            raise GasBudgetRefused('original RPC and original attempt verifier required')
        self.rpc = original_rpc
        self.verify_attempt = verify_original_attempt

    def read(self, *, attempt_id, transaction_hash, proof_reference):
        _hash(transaction_hash)
        for value in (attempt_id, proof_reference):
            if type(value) is not str or not value.strip() or len(value) > 256:
                raise GasBudgetRefused('bounded original identity required')
        transcript = []

        def query(method, parameters):
            try:
                raw = self.rpc(method, parameters)
            except Exception:
                raise GasBudgetRefused('original RPC read unavailable') from None
            if type(raw) is not bytes or not 1 <= len(raw) <= 262144:
                raise GasBudgetRefused('bounded authenticated original result bytes required')
            try:
                value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                    parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            except (ValueError, UnicodeError, RecursionError):
                raise GasBudgetRefused('invalid original RPC result JSON') from None
            transcript.append({'method': method, 'parameters': parameters, 'raw': raw})
            return raw, value

        _, chain = query('eth_chainId', [])
        if _quantity(chain) != 11155111:
            raise GasBudgetRefused('original RPC is not Sepolia')
        raw_receipt, receipt = query('eth_getTransactionReceipt', [transaction_hash])
        if receipt is None:
            return None
        if type(receipt) is not dict:
            raise GasBudgetRefused('original mined receipt required')
        number = _quantity(receipt.get('blockNumber'))
        block_hash = _hash(receipt.get('blockHash'))
        if _hash(receipt.get('transactionHash')) != transaction_hash:
            raise GasBudgetRefused('original transaction mismatch')
        _, finalized = query('eth_getBlockByNumber', ['finalized', False])
        if type(finalized) is not dict:
            raise GasBudgetRefused('original finalized head unavailable')
        finalized_number = _quantity(finalized.get('number'))
        _hash(finalized.get('hash'))
        if number > finalized_number:
            raise GasBudgetRefused('receipt not finalized; retain reservation')
        _, block = query('eth_getBlockByNumber', [hex(number), False])

        def canonical(value):
            if (type(value) is not dict or _quantity(value.get('number')) != number
                    or _hash(value.get('hash')) != block_hash):
                raise GasBudgetRefused('receipt block is not canonical')
        canonical(block)
        raw_again, _ = query('eth_getTransactionReceipt', [transaction_hash])
        if raw_again != raw_receipt:
            raise GasBudgetRefused('receipt changed during observation')
        _, block_again = query('eth_getBlockByNumber', [hex(number), False])
        canonical(block_again)
        _, chain_again = query('eth_chainId', [])
        if _quantity(chain_again) != 11155111:
            raise GasBudgetRefused('original RPC chain changed')

        def verify(evidence):
            # This is the original adapter trust boundary, not an inferred wallet proof.
            return self.verify_attempt({'attemptId': attempt_id,
                'transactionHash': transaction_hash, 'proofReference': proof_reference,
                'chainId': 11155111, 'finalizedBlockNumber': finalized_number,
                'finalizedBlockHash': finalized['hash'],
                'receiptEvidence': evidence, 'reads': tuple(transcript)})
        return ReceiptGasObserver(verify).observe(raw_receipt, chain_id=11155111,
            attempt_id=attempt_id, transaction_hash=transaction_hash,
            proof_reference=proof_reference)
