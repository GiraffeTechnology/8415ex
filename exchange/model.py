"""Warehouse receipts, wallet authorization and signed trade intents.

Three facts stay separate throughout this module, because collapsing any pair of
them is the error the PRD names:

* ``owner`` is the position the on-chain trade chain has reached;
* ``holder`` is the position the registrar has confirmed;
* a simulated registrar is never presented as a real registration institution.

A position is a proved occurrence index in one receipt's accepted chain. It is
never the numeric order of an address, and nothing here compares addresses for
magnitude.
"""
from dataclasses import dataclass, field, replace

from .errors import require
from .ids import address, amount, chain_id, digest, identifier, instant

#: A transfer always moves one whole receipt. There is no divisible quantity.
WHOLE_RECEIPT_UNITS = 1

#: The three simulated registration paths. They share one contract; the names
#: denote simulated business roles only and imply no real-world cooperation.
REGISTRATION_PATHS = ("REG_DIRECT", "REG_ELECTRONIC", "REG_INTERMEDIARY")

SIDES = ("sell", "buy")


@dataclass(frozen=True)
class Asset:
    """The on-chain identity of one whole-receipt NFT."""

    chain_id: int
    contract: str
    token_id: int

    def __post_init__(self):
        chain_id(self.chain_id)
        address(self.contract, "EX_ASSET_REFUSED")
        require(isinstance(self.token_id, int) and not isinstance(self.token_id, bool) and self.token_id >= 0,
                "EX_ASSET_REFUSED", "token id must be a non-negative integer")

    @property
    def key(self):
        return (self.chain_id, self.contract, self.token_id)


@dataclass(frozen=True)
class WarehouseReceipt:
    """One whole warehouse receipt projected as exactly one NFT.

    ``commodity_quantity`` describes the goods inside the single receipt. The
    tradeable quantity is always :data:`WHOLE_RECEIPT_UNITS`; the two are
    different things and this type keeps them apart.
    """

    receipt_id: str
    asset: Asset
    commodity_name: str
    commodity_quantity: int
    commodity_unit: str
    receipt_number: str
    registration_path: str
    trade_stop_at: int
    origin_account: str
    minted_at: int
    allowed_price_currencies: tuple = ()
    nft0_currency_reference: str = None

    def __post_init__(self):
        identifier(self.receipt_id, "EX_RECEIPT_REFUSED")
        require(type(self.allowed_price_currencies) is tuple
                and all(type(c) is str for c in self.allowed_price_currencies)
                and len(set(self.allowed_price_currencies)) == len(self.allowed_price_currencies),
                "EX_NFT0_CURRENCY_REFUSED", "unique immutable currency tuple required")
        for currency in self.allowed_price_currencies:
            identifier(currency, "EX_NFT0_CURRENCY_REFUSED")
        if self.nft0_currency_reference is not None:
            identifier(self.nft0_currency_reference, "EX_NFT0_CURRENCY_REFUSED")
        require(isinstance(self.asset, Asset), "EX_RECEIPT_REFUSED", "asset must be an Asset")
        require(isinstance(self.commodity_name, str) and self.commodity_name.strip() != "",
                "EX_RECEIPT_REFUSED", "commodity name is required")
        require(isinstance(self.commodity_quantity, int) and not isinstance(self.commodity_quantity, bool)
                and self.commodity_quantity > 0, "EX_RECEIPT_QUANTITY_REFUSED",
                "the goods quantity inside one receipt must be a positive integer")
        require(isinstance(self.commodity_unit, str) and self.commodity_unit.strip() != "",
                "EX_RECEIPT_REFUSED", "commodity unit is required")
        identifier(self.receipt_number, "EX_RECEIPT_REFUSED")
        require(self.registration_path in REGISTRATION_PATHS, "EX_REGISTRATION_PATH_REFUSED", self.registration_path)
        instant(self.trade_stop_at, "EX_RECEIPT_DEADLINE_REFUSED")
        address(self.origin_account, "EX_RECEIPT_REFUSED")
        instant(self.minted_at, "EX_RECEIPT_REFUSED")
        require(self.minted_at < self.trade_stop_at, "EX_RECEIPT_DEADLINE_REFUSED",
                "the stop-trading instant must follow minting")

    @property
    def tradeable_units(self):
        """Always one. Minting records a technical fact and asserts no legal right."""
        return WHOLE_RECEIPT_UNITS


@dataclass(frozen=True)
class AuthorizationReference:
    """What a wallet has authorized, as this layer may read it.

    This is a *reference to* a wallet authorization, not a second approval layer:
    nothing here can widen it, and the exchange never holds a private key. The
    fields are the signed constraints an action is checked against.
    """

    authorization_id: str
    account: str
    chain_id: int
    asset: Asset
    allowed_actions: tuple
    counterparties: tuple
    max_amount: int
    quote_asset: str
    not_before: int
    expires_at: int
    session_id: str
    revoked: bool = False

    def __post_init__(self):
        identifier(self.authorization_id, "EX_AUTH_REFUSED")
        address(self.account, "EX_AUTH_REFUSED")
        chain_id(self.chain_id)
        require(isinstance(self.asset, Asset), "EX_AUTH_REFUSED", "asset must be an Asset")
        require(isinstance(self.allowed_actions, tuple) and self.allowed_actions != ()
                and all(isinstance(a, str) and a != "" for a in self.allowed_actions),
                "EX_AUTH_REFUSED", "allowed actions must be a non-empty tuple of names")
        require(isinstance(self.counterparties, tuple)
                and all(isinstance(c, str) for c in self.counterparties),
                "EX_AUTH_REFUSED", "counterparties must be a tuple")
        for party in self.counterparties:
            address(party, "EX_AUTH_REFUSED")
        amount(self.max_amount, "EX_AUTH_REFUSED")
        identifier(self.quote_asset, "EX_AUTH_REFUSED")
        instant(self.not_before, "EX_AUTH_REFUSED")
        instant(self.expires_at, "EX_AUTH_REFUSED")
        require(self.not_before < self.expires_at, "EX_AUTH_REFUSED", "the validity window must be non-empty")
        identifier(self.session_id, "EX_AUTH_REFUSED")
        require(self.chain_id == self.asset.chain_id, "EX_AUTH_CHAIN_REFUSED",
                "the authorization chain must be the asset chain")
        require(isinstance(self.revoked, bool), "EX_AUTH_REFUSED", "revoked must be a boolean")

    def revoke(self):
        return replace(self, revoked=True)


@dataclass(frozen=True)
class TradeIntent:
    """A signed order for one whole receipt.

    ``units`` exists only so that a fractional or multi-unit order can be
    refused explicitly rather than silently rounded.
    """

    intent_id: str
    side: str
    signer: str
    asset: Asset
    limit_price: int
    quote_asset: str
    units: int
    nonce: int
    expires_at: int
    authorization_id: str
    counterparty: str = None
    currency_set_reference: str = None

    def __post_init__(self):
        identifier(self.intent_id, "EX_INTENT_REFUSED")
        require(self.side in SIDES, "EX_INTENT_REFUSED", f"side must be one of {SIDES}")
        address(self.signer, "EX_INTENT_REFUSED")
        require(isinstance(self.asset, Asset), "EX_INTENT_REFUSED", "asset must be an Asset")
        amount(self.limit_price, "EX_INTENT_PRICE_REFUSED")
        require(self.limit_price > 0, "EX_INTENT_PRICE_REFUSED", "a limit price must be positive")
        identifier(self.quote_asset, "EX_INTENT_REFUSED")
        require(self.units == WHOLE_RECEIPT_UNITS and isinstance(self.units, int)
                and not isinstance(self.units, bool), "EX_WHOLE_RECEIPT_REFUSED",
                "a trade covers exactly one whole receipt")
        require(isinstance(self.nonce, int) and not isinstance(self.nonce, bool) and self.nonce >= 0,
                "EX_INTENT_REFUSED", "nonce must be a non-negative integer")
        instant(self.expires_at, "EX_INTENT_REFUSED")
        identifier(self.authorization_id, "EX_INTENT_REFUSED")
        if self.counterparty is not None:
            address(self.counterparty, "EX_INTENT_REFUSED")
        if self.currency_set_reference is not None:
            identifier(self.currency_set_reference, "EX_INTENT_REFUSED")

    @property
    def signed_terms(self):
        """Exactly the fields a signature covers. Changing any of them changes
        the digest, so an altered intent cannot execute under the old signature."""
        return {
            "intentId": self.intent_id,
            "side": self.side,
            "signer": self.signer,
            "chainId": self.asset.chain_id,
            "contract": self.asset.contract,
            "tokenId": self.asset.token_id,
            "limitPrice": str(self.limit_price),
            "quoteAsset": self.quote_asset,
            "currencySetReference": self.currency_set_reference,
            "units": self.units,
            "nonce": self.nonce,
            "expiresAt": self.expires_at,
            "authorizationId": self.authorization_id,
            "counterparty": self.counterparty,
        }

    @property
    def digest(self):
        return digest(self.signed_terms)
