"""Read-only projection of the original Wallet receipt-task contract.

This consumer does not validate a Wallet grant, reproduce its digest, authorize
an action or translate EX actions into ArtFi phases. Output is never READY.
"""
from collections.abc import Mapping
import re

WALLET_SOURCE_COMMIT = "19c47cbc9aa1106b7c0663065e9f2c70e2b75e48"
WALLET_TASK_SOURCE = "src/agent/receiptTask.ts"
WALLET_PHASES = ("funded", "registered", "paid")
WALLET_SOURCE_CHAINS = ("31337", "560048")
EX_REQUIRED_CHAIN = "11155111"


def _object(value):
    if not isinstance(value, Mapping):
        raise ValueError("receipt-task object required")
    return value


def _text(value, pattern):
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise ValueError("receipt-task public field refused")
    return value


def _uint(value):
    return _text(value, r"(?:0|[1-9][0-9]{0,77})")


def _hash(value):
    value = _text(value, r"0x[0-9a-fA-F]{64}")
    if int(value[2:], 16) == 0:
        raise ValueError("zero receipt identity refused")
    return value.lower()


def _address(value):
    return _text(value, r"0x[0-9a-fA-F]{40}").lower()


def project_receipt_task(frozen_task):
    """Project public fields from a host-supplied original frozen task.

    Lexical checks support an honest UI, not Wallet semantic validation. The
    original host must still use receiptTaskCopy/receiptPhaseScope and the held
    authorization/capability/native journal. No supplied verified flag is used.
    This snapshot must never be fed back as a signed or validated task.
    """
    task = _object(frozen_task)
    policy = _object(task.get("policy"))
    if policy.get("schema") != "8415-agent-task/1":
        raise ValueError("original receipt-task schema required")
    intent = _object(policy.get("intent"))
    if (intent.get("kind"), intent.get("handlerId")) != (
            "artfi-receipt", "artfi:whole-receipt:v1"):
        raise ValueError("original receipt handler required")
    sale = _object(intent.get("sale"))
    chain = _uint(policy.get("chainId"))
    phases = intent.get("phases")
    if not isinstance(phases, (list, tuple)) or not 1 <= len(phases) <= 3:
        raise ValueError("bounded original receipt phases required")
    seen, slots = set(), []
    for raw in phases:
        slot = _object(raw)
        phase = slot.get("phase")
        if phase not in WALLET_PHASES or phase in seen:
            raise ValueError("original distinct receipt phase required")
        seen.add(phase)
        slots.append({"phase": phase, "nonce": _uint(slot.get("nonce")),
                      "planDigest": _hash(slot.get("planDigest")),
                      "journalBindingHash": _hash(slot.get("journalBindingHash"))})
    gaps = ["EX_ACTION_TO_ORIGINAL_PHASE_MAPPING_NOT_ESTABLISHED",
            "SOURCE_ASSET_SEGMENT_JOURNAL_PROVENANCE_NOT_VERIFIED",
            "ORIGINAL_HELD_GATE_AND_NATIVE_JOURNAL_NOT_CONNECTED"]
    if chain != EX_REQUIRED_CHAIN:
        gaps.append("EX_SEPOLIA_CHAIN_MISMATCH")
    if EX_REQUIRED_CHAIN not in WALLET_SOURCE_CHAINS:
        gaps.append("PINNED_WALLET_RECEIPT_CONTRACT_HAS_NO_SEPOLIA_SUPPORT")
    return {
        "kind": "ORIGINAL_RECEIPT_TASK_READ_ONLY",
        "taskId": _text(policy.get("taskId"), r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}"),
        "taskDigest": _hash(task.get("digest")),
        "chainId": chain, "requiredChainId": EX_REQUIRED_CHAIN,
        "segmentId": _hash(intent.get("segmentId")),
        "asset": {"collection": _address(sale.get("collection")),
                  "tokenId": _uint(sale.get("tokenId"))},
        "actor": _address(policy.get("actor")),
        "phases": slots,
        "source": {"repository": "GiraffeTechnology/8415Wallet-Code",
                   "commit": WALLET_SOURCE_COMMIT, "path": WALLET_TASK_SOURCE},
        "state": "NOT_VERIFIED", "canExecute": False,
        "digestVerification": "NOT_RUN", "authorization": "NOT_VERIFIED",
        "provider": "NOT_CONNECTED", "journal": "NOT_CONNECTED",
        "gaps": gaps,
    }
