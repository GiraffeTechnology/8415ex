"""Read-only consumer of the existing artfi-task-journal/1 runtime entry.

No HTTP/TLS client, capability issuer, credential or persistence is created here.
"""
from copy import deepcopy
from datetime import datetime
import json
import re


INTERFACE = 'artfi-task-journal/1'
PRINCIPAL_KEYS = {'kind', 'taskId', 'taskDigest', 'executorDigest', 'grantReference',
                  'grantPolicyVersion', 'operationId'}
STATUSES = {'awaiting-wallet', 'submitted', 'pending', 'accepted', 'cancelled',
            'rejected', 'failed', 'confirmed'}
FORBIDDEN = {'signature', 'exactsignature', 'privatekey', 'seedphrase', 'mnemonic',
    'rawtransaction', 'signedtransaction', 'rawsignedtransaction', 'signedrawtransaction',
    'accesstoken', 'refreshtoken', 'apikey', 'authorization', 'capability', 'password', 'secret'}


class OriginalJournalRefused(ValueError):
    pass


class OriginalJournalUnavailable(RuntimeError):
    pass


def _match(value, pattern):
    return type(value) is str and re.fullmatch(pattern, value) is not None


def _safe_integer(value, minimum=1):
    return type(value) is int and minimum <= value <= 9007199254740991


def _unsigned(value):
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                return False
            normalized = re.sub('[^a-z0-9]', '', key.lower())
            if normalized in FORBIDDEN or 'signature' in normalized or not _unsigned(child):
                return False
        return True
    if type(value) is list:
        return all(_unsigned(child) for child in value)
    return value is None or type(value) in (str, bool) or _safe_integer(value, -9007199254740991)


def _principal(value):
    if (type(value) is not dict or set(value) != PRINCIPAL_KEYS or value.get('kind') != 'task'
            or not _match(value.get('taskId'), r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}')
            or not _match(value.get('operationId'), r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}')
            or not _match(value.get('taskDigest'), r'0x[0-9a-f]{64}')
            or not _match(value.get('executorDigest'), r'0x[0-9a-f]{64}')
            or not _match(value.get('grantReference'), r'grant:[A-Za-z0-9_-]{1,122}')
            or not _match(value.get('grantPolicyVersion'), r'[1-9][0-9]{0,77}')):
        raise OriginalJournalRefused('exact existing task principal required')
    return deepcopy(value)


def _validated_operation(result, principal, operation_id, chain_id, wallet):
    if type(result) is not dict or not _unsigned(result):
        raise OriginalJournalRefused('unsigned original operation required')
    try:
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    except (ValueError, TypeError, UnicodeError):
        raise OriginalJournalRefused('unsupported original operation encoding') from None
    if len(encoded) > 65536:
        raise OriginalJournalRefused('original operation exceeds wire bound')
    plan = result.get('plan')
    if (result.get('id') != operation_id or type(plan) is not dict
            or not _match(result.get('wallet'), r'0x[0-9a-fA-F]{40}')
            or result['wallet'].lower() != wallet.lower()
            or not _safe_integer(result.get('chainId')) or result['chainId'] != chain_id
            or not _safe_integer(result.get('revision')) or type(result.get('status')) is not str
            or result['status'] not in STATUSES
            or not _match(result.get('requestHash'), r'[0-9a-f]{64}')
            or type(result.get('walletStarted')) is not bool
            or plan.get('operationId') != operation_id or type(plan.get('chainId')) is not int
            or plan['chainId'] != chain_id or 'sessionId' in plan
            or plan.get('taskPrincipal') != principal or type(plan.get('request')) is not dict
            or not _match(plan['request'].get('account'), r'0x[0-9a-fA-F]{40}')
            or plan['request']['account'].lower() != wallet.lower()):
        raise OriginalJournalRefused('foreign or changed original operation')
    try:
        stamp = datetime.fromisoformat(result['updatedAt'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('missing UTC offset')
    except (KeyError, ValueError, TypeError, AttributeError):
        raise OriginalJournalRefused('original operation timestamp unavailable') from None
    for field in ('transactionHash', 'orderHash'):
        if field in result and not _match(result[field], r'0x[0-9a-fA-F]{64}'):
            raise OriginalJournalRefused('invalid original transaction/order identity')
    return deepcopy(result)


class OriginalTaskJournalReader:
    """Supply an adapter already bound to createNftTaskJournal and its held gate.

    original_journal(principal, action, operation) is the original public entry;
    this consumer invokes get only. mTLS/capability/grant verification remains
    inside that existing runtime. A fixture callback is not real binding proof.
    """
    def __init__(self, original_journal):
        if not callable(original_journal):
            raise OriginalJournalUnavailable('existing authenticated journal adapter is unbound')
        self.original_journal = original_journal

    def read(self, principal, operation_id, expected_chain_id, expected_wallet):
        scope = _principal(principal)
        if (not _match(operation_id, r'[A-Za-z0-9_-]{16,80}')
                or not _safe_integer(expected_chain_id)
                or not _match(expected_wallet, r'0x[0-9a-fA-F]{40}')):
            raise OriginalJournalRefused('explicit original operation, chain and wallet binding required')
        try:
            result = self.original_journal(deepcopy(scope), 'get', {'id': operation_id})
        except Exception:
            raise OriginalJournalUnavailable('original journal unavailable; query the same operation, no fallback') from None
        operation = _validated_operation(result, scope, operation_id, expected_chain_id, expected_wallet)
        return {'sourceInterface': INTERFACE, 'nativeOperation': operation,
                'canExecute': False, 'oracleRegistration': 'NOT_VERIFIED',
                'principalFunding': 'NOT_VERIFIED', 'gasFunding': 'NOT_VERIFIED',
                'originalRuntimeBinding': 'requires installed adapter evidence; not attested by shape'}
