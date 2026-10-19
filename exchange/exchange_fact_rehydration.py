"""Rebuild EX-owned in-memory structures using current original runtime ports."""
from copy import deepcopy

from .exchange_fact_snapshot import (DOMAIN_FIELDS, RUNTIME_FIELDS, SPECIAL_FIELDS,
    decode_exchange_snapshot, encode_exchange_snapshot)
from .ledger import Exchange
from .mint_specification import MintDeclarationBook
from .priority_exchange import PriorityBook
from .serialized_exchange_access import SerializedExchangeAccess


class ExchangeRehydrationRefused(ValueError):
    pass


def rehydrate_exchange_facts(snapshot_bytes, runtime):
    """Return a new serialized Exchange, without executing or replacing runtime.

    `runtime` is a fresh Exchange configured by the existing application, with
    its current sessions and authorization observations. Snapshot grant records
    remain references; snapshot sessions never reconnect an account. External
    journals and native outcomes must still be reconciled through their original
    ports. No clock, callback, provider, database or credential is selected here.
    """
    if (type(runtime) is not Exchange
            or set(vars(runtime)) != set(DOMAIN_FIELDS + RUNTIME_FIELDS + SPECIAL_FIELDS)):
        raise ExchangeRehydrationRefused("original configured Exchange runtime required")
    # Do not silently overwrite an existing writer's accepted domain data.
    if (runtime._receipts or runtime._intents or runtime._order_books
            or any(getattr(runtime, name) for name in DOMAIN_FIELDS)):
        raise ExchangeRehydrationRefused("fresh runtime must not contain another domain history")
    encode_exchange_snapshot(runtime)
    facts = decode_exchange_snapshot(snapshot_bytes)
    current_authorizations = dict(runtime._authorizations)
    saved_authorizations = {item.authorization_id: item for item in facts.wallet["authorizations"]}
    for identity, current in current_authorizations.items():
        saved = saved_authorizations.get(identity)
        if saved is not None and (current.account, current.chain_id, current.asset) != (
                saved.account, saved.chain_id, saved.asset):
            raise ExchangeRehydrationRefused("current authorization identity refers to another account or asset")

    candidate = Exchange.__new__(Exchange)
    for name in RUNTIME_FIELDS:
        setattr(candidate, name, getattr(runtime, name))
    candidate._budgets = dict(runtime._budgets)
    for name in DOMAIN_FIELDS:
        setattr(candidate, name, deepcopy(facts.domain[name]))
    candidate._receipts = deepcopy(facts.receipts)
    candidate._authorizations = deepcopy(saved_authorizations)
    candidate._authorizations.update(deepcopy(current_authorizations))
    candidate._sessions = dict(runtime._sessions)
    candidate._intents = {item.intent_id: deepcopy(item) for item in facts.wallet["intents"]}
    candidate._used_nonces = set(facts.wallet["usedNonces"]) | set(runtime._used_nonces)

    if facts.mint_indexes is not None:
        if type(runtime._mint_book) is not MintDeclarationBook:
            raise ExchangeRehydrationRefused("original configured declaration verifier is unavailable")
        candidate._mint_book = MintDeclarationBook(runtime._mint_book.verify)
        for name, values in facts.mint_indexes.items():
            setattr(candidate._mint_book, name, deepcopy(values))
    else:
        candidate._mint_book = (MintDeclarationBook(runtime._mint_book.verify)
                                if runtime._mint_book is not None else None)
    candidate._order_books = {}
    for identity, saved in facts.priority_books.items():
        scope = saved["scope"]
        if type(scope) is not dict or type(scope.get("generation")) is not int:
            raise ExchangeRehydrationRefused("original priority generation scope required")
        book = PriorityBook(candidate, saved["receiptId"], saved["quoteAsset"], candidate._clock,
                            sequence_store=candidate._priority_store, generation=scope["generation"])
        if book._book_scope != scope or identity != (saved["receiptId"], saved["quoteAsset"]):
            raise ExchangeRehydrationRefused("original priority identity or scope differs")
        book._entries = {key: (candidate._intents[key], pair[1])
                         for key, pair in saved["entries"].items()}
        book._nonces = deepcopy(saved["nonces"])
        book._sequence = saved["sequence"]
        book._unresolved = tuple(saved["unresolved"])
        candidate._order_books[identity] = book
    # Original encoder rechecks all reconstructed domain/reference memberships.
    # This captures data only: it neither invokes a verifier nor enquiries a
    # native controller or external priority journal.
    encode_exchange_snapshot(candidate)
    return SerializedExchangeAccess(candidate)
