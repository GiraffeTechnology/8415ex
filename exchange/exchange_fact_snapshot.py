"""Detached EX-owned facts. No live restore, callbacks or external journal reads."""
from dataclasses import dataclass

from .ledger import Exchange, Transfer
from .mint_specification import MintDeclarationBook
from .priority_exchange import PriorityBook
from .receipt_checkpoint_codec import encode_receipt_facts, decode_receipt_facts
from .wallet_fact_codec import encode_wallet_facts, decode_wallet_facts
from .operational_facts_codec import encode_operational_facts, decode_operational_facts


class ExchangeSnapshotRefused(ValueError):
    pass


SCHEMA = "8415ex-owned-fact-snapshot/1"
DOMAIN_FIELDS = (
    "_escrows", "_escrow_by_leg", "_gas", "_rollbacks", "_returned_to",
    "_active_legs", "_rollback_history", "_exits", "_mint_declarations",
    "_nft0_currency_sets", "_asset_keys", "_legs", "_holder_index", "_requests",
    "_requests_by_leg", "_applied_results", "_deferred", "_rejections", "_events",
)
PER_RECEIPT = (
    "_escrow_by_leg", "_gas", "_rollbacks", "_returned_to", "_active_legs",
    "_rollback_history", "_exits", "_mint_declarations", "_nft0_currency_sets",
    "_legs", "_holder_index", "_requests_by_leg", "_deferred", "_rejections", "_events",
)
# These are dependencies/current policy, not recoverable authority. Never inspect
# adapters, callbacks, external connections or native journals through them.
RUNTIME_FIELDS = (
    "_clock", "_eth_gas_gate", "_price_balance_gate", "_priority_store", "payments",
    "funding_required", "_release_sources", "asset_control", "_rollback_sources",
    "_budgets", "voucher_desk", "registrars",
)
SPECIAL_FIELDS = ("_receipts", "_authorizations", "_sessions", "_intents",
                  "_used_nonces", "_order_books", "_mint_book")
BOOK_FIELDS = ("exchange", "receipt_id", "asset", "quote_asset", "clock", "_entries",
               "_nonces", "_sequence", "_lock", "_store", "_book_scope", "_unresolved")
BOOK_FACTS = ("receiptId", "asset", "quoteAsset", "entries", "nonces", "sequence",
              "scope", "unresolved")
MINT_INDEXES = ("_assets", "_receipts", "_documents")
TOP_FIELDS = ("schema", "receipts", "wallet", "domain", "mintIndexes", "priorityBooks")


@dataclass(frozen=True)
class DecodedExchangeFacts:
    receipts: dict
    wallet: dict
    domain: dict
    mint_indexes: object
    priority_books: dict
    execution_authorized: bool = False
    complete_recovery: bool = False


def _keys(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise ExchangeSnapshotRefused("exact original fact membership required")


def _book(book, exchange):
    if type(book) is not PriorityBook or set(vars(book)) != set(BOOK_FIELDS) or book.exchange is not exchange:
        raise ExchangeSnapshotRefused("original priority book contract differs")
    entries = {}
    for identity, entry in book._entries.items():
        if type(entry) is not tuple or len(entry) != 2:
            raise ExchangeSnapshotRefused("original priority entry pair required")
        intent, sequence = entry
        if exchange._intents.get(identity) != intent or intent.intent_id != identity:
            raise ExchangeSnapshotRefused("priority entry lacks its original signed intent")
        entries[identity] = (intent.digest, sequence)
    return {"receiptId": book.receipt_id, "asset": book.asset, "quoteAsset": book.quote_asset,
            "entries": entries, "nonces": book._nonces, "sequence": book._sequence,
            "scope": book._book_scope, "unresolved": book._unresolved}


def _pack(exchange):
    if type(exchange) is not Exchange or set(vars(exchange)) != set(DOMAIN_FIELDS + RUNTIME_FIELDS + SPECIAL_FIELDS):
        raise ExchangeSnapshotRefused("Exchange fields changed; explicit snapshot revision required")
    if (any(type(getattr(exchange, name)) is not dict for name in
            ("_receipts", "_authorizations", "_sessions", "_intents", "_order_books"))
            or type(exchange._used_nonces) is not set):
        raise ExchangeSnapshotRefused("original owned map and consumed nonce set types required")
    references = tuple(exchange._authorizations.values())
    intents = tuple(exchange._intents.values())
    if (any(key != item.authorization_id for key, item in exchange._authorizations.items())
            or any(key != item.intent_id for key, item in exchange._intents.items())):
        raise ExchangeSnapshotRefused("original wallet indexes differ")
    wallet = encode_wallet_facts({"authorizations": references, "intents": intents,
        "sessions": exchange._sessions, "usedNonces": frozenset(exchange._used_nonces)})
    mint = exchange._mint_book
    if mint is not None:
        if type(mint) is not MintDeclarationBook or set(vars(mint)) != set((*MINT_INDEXES, "verify")):
            raise ExchangeSnapshotRefused("original mint indexes changed")
        mint = {name: getattr(mint, name) for name in MINT_INDEXES}
    return {"schema": SCHEMA,
        "receipts": {key: encode_receipt_facts(receipt).decode("ascii")
                     for key, receipt in exchange._receipts.items()},
        "wallet": wallet.decode("ascii"),
        "domain": {name: getattr(exchange, name) for name in DOMAIN_FIELDS},
        "mintIndexes": mint,
        "priorityBooks": {key: _book(book, exchange) for key, book in exchange._order_books.items()}}


def _unpack(value):
    _keys(value, TOP_FIELDS)
    if value["schema"] != SCHEMA or type(value["receipts"]) is not dict or type(value["wallet"]) is not str:
        raise ExchangeSnapshotRefused("exact snapshot schema and embedded fact encodings required")
    receipts = {}
    for identity, text in value["receipts"].items():
        if type(text) is not str:
            raise ExchangeSnapshotRefused("canonical receipt text required")
        receipt = decode_receipt_facts(text.encode("ascii")).receipt
        if identity != receipt.receipt_id:
            raise ExchangeSnapshotRefused("receipt identity index differs")
        receipts[identity] = receipt
    wallet = decode_wallet_facts(value["wallet"].encode("ascii")).facts
    domain = value["domain"]
    _keys(domain, DOMAIN_FIELDS)
    if any(type(domain[name]) is not dict for name in DOMAIN_FIELDS):
        raise ExchangeSnapshotRefused("original domain maps required")
    for name in PER_RECEIPT:
        if set(domain[name]) != set(receipts):
            raise ExchangeSnapshotRefused("per-receipt fact coverage differs")
    if domain["_asset_keys"] != {receipt.asset.key: key for key, receipt in receipts.items()}:
        raise ExchangeSnapshotRefused("original asset index differs")
    if len(domain["_asset_keys"]) != len(receipts):
        raise ExchangeSnapshotRefused("duplicate receipt asset identity")
    for identity, receipt in receipts.items():
        if domain["_nft0_currency_sets"][identity] != (receipt.allowed_price_currencies, receipt.nft0_currency_reference):
            raise ExchangeSnapshotRefused("original immutable currency terms differ")
        legs = domain["_legs"][identity]
        if type(legs) is not list or any(type(leg) is not Transfer or leg.receipt_id != identity or leg.leg_index != index
                                       for index, leg in enumerate(legs)):
            raise ExchangeSnapshotRefused("original transfer occurrences differ")
        holder = domain["_holder_index"][identity]
        active = domain["_active_legs"][identity]
        if type(holder) is not int or not 0 <= holder <= len(legs):
            raise ExchangeSnapshotRefused("holder occurrence outside original history")
        if (type(active) is not list or any(type(index) is not int or not 0 <= index < len(legs) for index in active)
                or active != sorted(set(active))):
            raise ExchangeSnapshotRefused("active occurrence index differs")
    mint = value["mintIndexes"]
    if mint is not None:
        _keys(mint, MINT_INDEXES)
        if any(type(mint[name]) is not dict for name in MINT_INDEXES):
            raise ExchangeSnapshotRefused("original mint uniqueness maps required")
    books = value["priorityBooks"]
    if type(books) is not dict:
        raise ExchangeSnapshotRefused("original priority map required")
    intent_index = {intent.intent_id: intent for intent in wallet["intents"]}
    for book in books.values():
        _keys(book, BOOK_FACTS)
        receipt = receipts.get(book["receiptId"])
        if receipt is None or book["asset"] != receipt.asset or type(book["sequence"]) is not int or book["sequence"] < 0:
            raise ExchangeSnapshotRefused("priority scope or original sequence differs")
        if type(book["entries"]) is not dict or type(book["nonces"]) is not dict or type(book["unresolved"]) is not tuple:
            raise ExchangeSnapshotRefused("original priority fact containers required")
        for identity, pair in book["entries"].items():
            intent = intent_index.get(identity)
            if (intent is None or type(pair) is not tuple or len(pair) != 2 or pair[0] != intent.digest
                    or type(pair[1]) is not int or not 0 < pair[1] <= book["sequence"]
                    or intent.asset != receipt.asset or intent.quote_asset != book["quoteAsset"]):
                raise ExchangeSnapshotRefused("priority signed terms or admission occurrence differs")
    return DecodedExchangeFacts(receipts, wallet, domain, mint, books)


def encode_exchange_snapshot(exchange):
    """Caller must serialize this read with its original writer; no lock is invented here."""
    try:
        raw = encode_operational_facts(_pack(exchange))
        _unpack(decode_operational_facts(raw).value)
        return raw
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RuntimeError):
        raise ExchangeSnapshotRefused("Exchange-owned snapshot refused") from None


def decode_exchange_snapshot(raw):
    try:
        return _unpack(decode_operational_facts(raw).value)
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RuntimeError):
        raise ExchangeSnapshotRefused("stored Exchange-owned snapshot refused") from None
