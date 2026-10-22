"""Encode only the original EXNFT0Remint ABI arguments, without a selector.

No business-to-EVM mapping, hash derivation, authority, signer or chain action.
"""
import re


REMINT_SIGNATURE = 'remintNFT0(bytes32,uint256,(bytes32,bytes32,bytes32,bytes32[]))'


class RemintABIRefused(ValueError):
    pass


def _uint256(value):
    if type(value) is not int or not 0 <= value < 2**256:
        raise RemintABIRefused('exact uint256 argument required')
    return value.to_bytes(32, 'big')


def _bytes32(value):
    if (type(value) is not str or re.fullmatch(r'0x[0-9a-f]{64}', value) is None
            or value == '0x' + '0' * 64):
        raise RemintABIRefused('original nonzero canonical bytes32 argument required')
    return bytes.fromhex(value[2:])


def encode_remint_arguments(operation_id, old_token_id, replacement):
    """Return abi.encode(operationId, oldTokenId, replacement) argument bytes.

    The installed original mapping must supply the real EVM operation identity,
    bill and declaration hashes and original ordered currency references.
    UUIDs, EX SHA-256 history digests and currency labels are never converted.
    The original contract retains possession/effective-holder and atomic checks.
    """
    operation = _bytes32(operation_id)
    old_token = _uint256(old_token_id)
    expected = {'billKey', 'termsHash', 'currencyDeclarationHash', 'allowedCurrencies'}
    if type(replacement) is not dict or set(replacement) != expected:
        raise RemintABIRefused('exact original replacement declaration required')
    bill = _bytes32(replacement['billKey'])
    terms = _bytes32(replacement['termsHash'])
    currency_declaration = _bytes32(replacement['currencyDeclarationHash'])
    values = replacement['allowedCurrencies']
    if type(values) not in (tuple, list) or not values:
        raise RemintABIRefused('nonempty original currency reference array required')
    currencies = tuple(_bytes32(value) for value in values)
    if len(set(currencies)) != len(currencies):
        raise RemintABIRefused('duplicate original currency reference refused')
    # Three outer head words; the declaration tuple is dynamic because its
    # fourth field is bytes32[]. Array offset is relative to that tuple.
    declaration = (bill + terms + currency_declaration + _uint256(4 * 32)
                   + _uint256(len(currencies)) + b''.join(currencies))
    return operation + old_token + _uint256(3 * 32) + declaration
