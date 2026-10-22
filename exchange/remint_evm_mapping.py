"""Bind original complete remint history to original EVM declaration arguments.

No semantic hashing, selector, transaction, RPC, wallet action or persistence.
"""
from copy import deepcopy
import re

from .durable_operation import _scope
from .remint_history import RemintHistoryStore
from .remint_terms import _encoded, RemintTermsRefused
from .remint_abi_arguments import encode_remint_arguments, REMINT_SIGNATURE


class RemintEVMMappingRefused(RemintTermsRefused):
    pass


def bind_remint_evm_arguments(scope, history, resolve_original_mapping):
    """Use a trusted installed original semantic mapping, never HTTP callbacks.

    Existing complete-history checks establish correlation, not source proof.
    The resolver must authenticate its actual operation/declaration/currency
    mapping. This bridge does not generate missing hashes or EVM identifiers.
    An unavailable mapping affects argument construction only, not original
    read-only operation enquiry or other authorized business operations.
    """
    binding = _scope(scope)
    original = deepcopy(history)
    RemintHistoryStore._bound(binding, original)
    new_asset = original['binding']['newAsset']
    if (type(new_asset) is not dict
            or _encoded({key: new_asset.get(key) for key in ('chain_id', 'contract')})
            != _encoded({'chain_id': binding['chainId'], 'contract': binding['contract']})):
        raise RemintEVMMappingRefused('original same-contract remint ABI mapping required')
    if not callable(resolve_original_mapping):
        raise RemintEVMMappingRefused('original semantic mapping source required')
    request = {'scope': deepcopy(binding), 'historyDigest': binding['intentDigest'],
               'billKey': original['billKey'],
               'oldDeclarationDigest': original['binding']['oldDeclarationDigest'],
               'newDeclarationDigest': original['binding']['newDeclarationDigest']}
    try:
        row = deepcopy(resolve_original_mapping(deepcopy(request),
                                               deepcopy(original['newDeclaration'])))
    except Exception:
        raise RemintEVMMappingRefused('original semantic mapping unavailable') from None
    expected = {'binding', 'operationId', 'replacement', 'sourceReference'}
    if (type(row) is not dict or set(row) != expected or type(row.get('binding')) is not dict
            or _encoded(row['binding']) != _encoded(request)
            or type(row.get('replacement')) is not dict
            or row['replacement'].get('billKey') != original['billKey']
            or type(row.get('sourceReference')) is not str
            or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', row['sourceReference']) is None):
        raise RemintEVMMappingRefused('exact original remint semantic binding required')
    arguments = encode_remint_arguments(row['operationId'], int(binding['tokenId']),
                                         row['replacement'])
    return {'scope': deepcopy(binding), 'historyDigest': binding['intentDigest'],
            'evmOperationId': row['operationId'], 'sourceReference': row['sourceReference'],
            'replacement': deepcopy(row['replacement']), 'signature': REMINT_SIGNATURE,
            'argumentsHex': '0x' + arguments.hex(),
            'semanticMappingTrust': 'installed-original-source-required',
            'selectorIncluded': False, 'walletOperationCreated': False,
            'dispatchAuthorized': False, 'nativeOutcomeVerified': False,
            'replayAllowed': False}
