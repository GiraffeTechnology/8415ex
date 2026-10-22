"""Adapt original gas receipts into an explicitly authenticated P50 population.

No RPC, sampling policy, clock, fee prediction, quote cap or wallet operation.
"""
from copy import deepcopy
from dataclasses import asdict
import re

from .gas_budget import FeeSample, GasBudgetRefused
from .receipt_gas_observer import ReceiptGasObservation


def _label(value):
    if (type(value) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', value) is None
            or re.search(r'0x[0-9a-fA-F]{40}', value)):
        raise GasBudgetRefused('original nonsecret sample label required')
    return value


def _uint(value):
    if type(value) is not int or not 0 <= value < 2**256:
        raise GasBudgetRefused('exact original receipt integer required')
    return value


def _hash(value, prefix=True):
    pattern = r'0x[0-9a-f]{64}' if prefix else r'[0-9a-f]{64}'
    if type(value) is not str or re.fullmatch(pattern, value) is None:
        raise GasBudgetRefused('original receipt hash required')
    return value


def receipt_fee_samples(population, *, scope, window_start, window_end,
                        verify_applicability):
    """Keep each exact observed transaction fee once; never invent population.

    The installed original source must authenticate the COMPLETE selected
    population, operation scope and observation times. This callback is the
    application evidence boundary, not a new human approval or RPC discovery.
    Shape, a typed observation or True from a fixture is not source authority.
    OriginalGasReceiptReader owns canonical/finality and attempt verification;
    this bridge does not replace those checks or establish current chain state.
    """
    _label(scope)
    _uint(window_start)
    _uint(window_end)
    if window_start > window_end or not callable(verify_applicability):
        raise GasBudgetRefused('original sample window and applicability verifier required')
    if type(population) not in (tuple, list) or not 2 <= len(population) <= 512:
        raise GasBudgetRefused('bounded multiple original receipt samples required')
    samples, evidence, identities, transactions = [], [], set(), set()
    for item in population:
        if type(item) is not dict or set(item) != {'observation', 'sampleId', 'observedAt', 'source'}:
            raise GasBudgetRefused('exact original sample binding required')
        observation = item['observation']
        if type(observation) is not ReceiptGasObservation:
            raise GasBudgetRefused('original mined gas observation required')
        if type(observation.chain_id) is not int or observation.chain_id != 11155111:
            raise GasBudgetRefused('original EX Sepolia receipt required')
        _hash(observation.transaction_hash)
        _hash(observation.block_hash)
        _hash(observation.raw_sha256, False)
        _uint(observation.block_number)
        _uint(observation.gas_used)
        _uint(observation.effective_gas_price)
        _uint(observation.actual_wei)
        if (observation.gas_used == 0
                or observation.actual_wei != observation.gas_used * observation.effective_gas_price
                or observation.outcome not in ('SUCCESS', 'FAILED')):
            raise GasBudgetRefused('complete actual original transaction fee required')
        for value in (observation.attempt_id, observation.proof_reference):
            if type(value) is not str or not value.strip() or len(value) > 256:
                raise GasBudgetRefused('original attempt and proof binding required')
        sample_id = _label(item['sampleId'])
        source = _label(item['source'])
        observed_at = _uint(item['observedAt'])
        if not window_start <= observed_at <= window_end:
            raise GasBudgetRefused('original sample observation outside supplied window')
        transaction = (observation.chain_id, observation.transaction_hash)
        if sample_id in identities or transaction in transactions:
            raise GasBudgetRefused('duplicate original sample or transaction refused')
        identities.add(sample_id)
        transactions.add(transaction)
        sample = FeeSample(sample_id, scope, observation.chain_id,
                           observation.actual_wei, observed_at,
                           observation.block_number, source, observation.raw_sha256)
        samples.append(sample)
        evidence.append({'observation': asdict(observation),
                         'sample': asdict(sample)})
    binding = {'scope': scope, 'chainId': 11155111,
               'windowStart': window_start, 'windowEnd': window_end,
               'population': evidence}
    try:
        verified = verify_applicability(deepcopy(binding))
    except Exception:
        raise GasBudgetRefused('original sample applicability unavailable') from None
    if verified is not True:
        raise GasBudgetRefused('original sample population not authenticated')
    return tuple(samples)
