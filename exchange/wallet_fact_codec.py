"""EX wallet-reference facts and consumed nonces, never live wallet authority."""
from dataclasses import dataclass, fields

from .errors import DomainError
from .ids import address, identifier
from .model import AuthorizationReference, TradeIntent
from .operational_facts_codec import encode_operational_facts, decode_operational_facts


class WalletFactsRefused(ValueError):
    pass


AUTH_FIELDS = (
    "authorization_id", "account", "chain_id", "asset", "allowed_actions", "counterparties",
    "max_amount", "quote_asset", "not_before", "expires_at", "session_id", "revoked",
)
INTENT_FIELDS = (
    "intent_id", "side", "signer", "asset", "limit_price", "quote_asset", "units", "nonce",
    "expires_at", "authorization_id", "counterparty", "currency_set_reference",
)
GROUPS = ("authorizations", "intents", "sessions", "usedNonces")
SCHEMA = "8415ex-wallet-reference-facts/1"


@dataclass(frozen=True)
class DecodedWalletFacts:
    facts: dict
    execution_authorized: bool = False


def _contracts():
    if (tuple(field.name for field in fields(AuthorizationReference)) != AUTH_FIELDS
            or tuple(field.name for field in fields(TradeIntent)) != INTENT_FIELDS):
        raise WalletFactsRefused("domain fields changed; explicit codec revision required")


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise WalletFactsRefused("exact reference fact fields required")


def _validate(facts):
    _keys(facts, GROUPS)
    indexes = {}
    for group, cls, key in (("authorizations", AuthorizationReference, "authorization_id"),
                             ("intents", TradeIntent, "intent_id")):
        if type(facts[group]) is not tuple:
            raise WalletFactsRefused("immutable ordered references required")
        index = {}
        for record in facts[group]:
            if type(record) is not cls or getattr(record, key) in index:
                raise WalletFactsRefused("reference type or identity conflict")
            index[getattr(record, key)] = record
        indexes[group] = index
    for intent in indexes["intents"].values():
        reference = indexes["authorizations"].get(intent.authorization_id)
        if reference is None or intent.signer != reference.account or intent.asset != reference.asset:
            raise WalletFactsRefused("original intent/reference binding differs")
    if type(facts["sessions"]) is not dict or type(facts["usedNonces"]) is not frozenset:
        raise WalletFactsRefused("original session map and immutable consumed nonce set required")
    for account, session in facts["sessions"].items():
        address(account); identifier(session)
    for pair in facts["usedNonces"]:
        if type(pair) is not tuple or len(pair) != 2 or type(pair[1]) is not int or pair[1] < 0:
            raise WalletFactsRefused("exact original account/nonce pair required")
        address(pair[0])
    # Do not refresh expiry, restore revoked grants or align a historical grant
    # to a later session. Those differences must survive the checkpoint intact.


def _pack(facts):
    _validate(facts)
    return {
        "schema": SCHEMA,
        "authorizations": tuple({name: getattr(record, name) for name in AUTH_FIELDS}
                                  for record in facts["authorizations"]),
        "intents": tuple({name: getattr(record, name) for name in INTENT_FIELDS}
                         for record in facts["intents"]),
        "sessions": facts["sessions"], "usedNonces": facts["usedNonces"],
    }


def _unpack(value):
    _keys(value, ("schema", *GROUPS))
    if value["schema"] != SCHEMA:
        raise WalletFactsRefused("exact reference facts version required")
    result = {"sessions": value["sessions"], "usedNonces": value["usedNonces"]}
    for group, cls, names in (("authorizations", AuthorizationReference, AUTH_FIELDS),
                               ("intents", TradeIntent, INTENT_FIELDS)):
        if type(value[group]) is not tuple:
            raise WalletFactsRefused("original ordered reference records required")
        records = []
        for item in value[group]:
            _keys(item, names)
            records.append(cls(**item))
        result[group] = tuple(records)
    _validate(result)
    return result


def encode_wallet_facts(facts):
    _contracts()
    try:
        raw = encode_operational_facts(_pack(facts))
        # Reconstruct original types to recheck their domain constructors.
        _unpack(decode_operational_facts(raw).value)
        return raw
    except (DomainError, TypeError, ValueError, KeyError, AttributeError):
        raise WalletFactsRefused("wallet reference facts refused") from None


def decode_wallet_facts(raw):
    _contracts()
    try:
        result = _unpack(decode_operational_facts(raw).value)
        if encode_operational_facts(_pack(result)) != raw:
            raise WalletFactsRefused("reference facts differ from canonical encoding")
    except (DomainError, TypeError, ValueError, KeyError, AttributeError):
        raise WalletFactsRefused("stored wallet reference facts refused") from None
    return DecodedWalletFacts(result)
