"""Synchronous get-only artfi-task-journal/1 wire adapter.

The host supplies existing held-grant capability and mutually authenticated
transport functions. This module creates no client, identity, grant or store.
"""
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re
import time
from urllib.parse import urlsplit
from .original_task_journal_reader import (
    _principal, _match, _validated_operation,
    OriginalJournalRefused, OriginalJournalUnavailable,
)

PATH = '/internal/v1/nft/operations'
MAX_BYTES = 65536


def canonical_bytes(value):
    """ArtFi Go/JS digest bytes: ASCII keys, safe integers, HTML escaping."""
    def check(item):
        if item is None or type(item) is bool:
            return
        if type(item) is str:
            item.encode('utf-8')
            return
        if type(item) is int and abs(item) <= 9007199254740991:
            return
        if type(item) is list:
            for child in item:
                check(child)
            return
        if type(item) is dict and all(type(k) is str and k.isascii() for k in item):
            for child in item.values():
                check(child)
            return
        raise ValueError('unsupported canonical value')
    try:
        check(value)
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False)
        for character in '<>&\u2028\u2029':
            encoded = encoded.replace(character, '\\u%04x' % ord(character))
        return encoded.encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise OriginalJournalRefused('unsupported journal encoding') from None


@dataclass(frozen=True)
class JournalHTTPResponse:
    status: int
    body: bytes
    url: str


class OriginalTaskJournalWire:
    """Callable for OriginalTaskJournalReader, with no network fallback.

    transport(endpoint, *, method, headers, body, timeout, max_bytes, redirect)
    must enforce the 8-second I/O deadline, bounded read, no redirect and the
    original verified mTLS identity. with_capability(scope, use) must hold the
    SAME original grant gate through use and response validation. Both are
    trusted host capabilities, not security proven by callable shape.
    """
    def __init__(self, *, endpoint, peer_id, transport, with_capability,
                 clock=time.monotonic):
        try:
            target = urlsplit(endpoint)
            valid = (type(endpoint) is str and target.scheme == 'https'
                and target.hostname and target.path == PATH
                and not target.username and not target.password
                and not target.query and not target.fragment
                and not any(c.isspace() or ord(c) < 32 for c in endpoint)
                and target.port != 0)
        except (ValueError, TypeError):
            valid = False
        if (not valid or type(peer_id) is not str or not peer_id
                or not callable(transport) or not callable(with_capability)
                or not callable(clock)):
            raise OriginalJournalUnavailable('original journal transport is UNBOUND')
        self.endpoint, self.peer_id = endpoint, peer_id
        self.transport, self.with_capability, self.clock = transport, with_capability, clock

    def __call__(self, principal, action, operation):
        principal = _principal(principal)
        if (action != 'get' or type(operation) is not dict or set(operation) != {'id'}
                or not _match(operation['id'], r'[A-Za-z0-9_-]{16,80}')):
            raise OriginalJournalRefused('get-only original journal operation required')
        operation = deepcopy(operation)
        request = {'action': 'get', 'operation': operation}
        body = json.dumps(request, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        scope = dict(principal=principal, action='get', operation=operation,
            peerId=self.peer_id, nativeOperationId=operation['id'], planDigest='',
            requestDigest=sha256(canonical_bytes(request)).hexdigest())
        entered = False
        active = True
        result_snapshot = None

        def use(capability):
            nonlocal entered, result_snapshot
            if not active or entered:
                raise OriginalJournalRefused('journal capability use is closed')
            entered = True
            if (type(capability) is not str or not 32 <= len(capability) <= 2048
                    or re.search(r'\s', capability)):
                raise OriginalJournalRefused('invalid journal capability')
            start = self.clock()
            response = self.transport(self.endpoint, method='POST',
                headers={'content-type': 'application/json', 'authorization': 'Bearer ' + capability},
                body=body, timeout=8.0, max_bytes=MAX_BYTES, redirect='error')
            elapsed = self.clock() - start
            if (not math.isfinite(elapsed) or elapsed < 0 or elapsed >= 8.0
                    or type(response) is not JournalHTTPResponse
                    or type(response.status) is not int or not 200 <= response.status < 300
                    or response.url != self.endpoint or type(response.body) is not bytes
                    or len(response.body) > MAX_BYTES):
                raise OriginalJournalUnavailable('original journal response refused')
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError('duplicate key')
                    result[key] = value
                return result
            raw = json.loads(response.body.decode('utf-8'), object_pairs_hook=unique,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError('non-finite')))
            if type(raw) is not dict:
                raise OriginalJournalUnavailable('original journal response refused')
            validated = _validated_operation(raw, principal, operation['id'],
                                             raw.get('chainId'), raw.get('wallet'))
            result_snapshot = deepcopy(validated)
            return validated
        try:
            result = self.with_capability(deepcopy(scope), use)
            if not entered or result_snapshot is None or result != result_snapshot:
                raise OriginalJournalUnavailable('original held capability did not complete')
            return deepcopy(result_snapshot)
        except Exception:
            raise OriginalJournalUnavailable('original journal unavailable; no retry or fallback') from None
        finally:
            active = False
