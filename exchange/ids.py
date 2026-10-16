"""Canonical encoding and identity helpers.

Amounts are integers in the smallest unit; no floating point appears anywhere in
the domain. Digests are over a canonical JSON encoding so two processes that
agree on the fields agree on the identity.
"""
import json
import re
from hashlib import sha256

from .errors import require

IDENTIFIER = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
ADDRESS = re.compile(r"\A0x[0-9a-f]{40}\Z")
HEX32 = re.compile(r"\A0x[0-9a-f]{64}\Z")


def identifier(value, code="EX_IDENTIFIER_REFUSED"):
    require(isinstance(value, str) and IDENTIFIER.match(value) is not None, code, value)
    return value


def address(value, code="EX_ADDRESS_REFUSED"):
    """A lowercase hex account. Addresses are identities, never magnitudes:
    nothing in this package compares them for order."""
    require(isinstance(value, str) and ADDRESS.match(value) is not None, code, value)
    return value


def instant(value, code="EX_INSTANT_REFUSED"):
    """Unix seconds as an exact integer, on the same scale as a block timestamp."""
    require(isinstance(value, int) and not isinstance(value, bool), code, value)
    require(0 <= value < 2 ** 64, code, value)
    return value


def amount(value, code="EX_AMOUNT_REFUSED"):
    """A non-negative integer in the asset's smallest unit."""
    require(isinstance(value, int) and not isinstance(value, bool), code, value)
    require(value >= 0, code, value)
    return value


def chain_id(value, code="EX_CHAIN_REFUSED"):
    require(isinstance(value, int) and not isinstance(value, bool) and value > 0, code, value)
    return value


def canonical_json(value):
    """Deterministic JSON: sorted keys, no insignificant whitespace, no floats."""

    def check(node):
        require(not isinstance(node, float), "EX_CANONICAL_REFUSED", "floating point is not a domain value")
        if isinstance(node, dict):
            for key, item in node.items():
                require(isinstance(key, str), "EX_CANONICAL_REFUSED", "object keys must be strings")
                check(item)
        elif isinstance(node, (list, tuple)):
            for item in node:
                check(item)

    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest(value):
    """``0x``-prefixed SHA-256 over the canonical encoding."""
    return "0x" + sha256(canonical_json(value).encode("ascii")).hexdigest()
