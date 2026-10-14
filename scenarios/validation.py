"""Deterministic configuration and evidence validation.

Two validators, both local and both read-only.

The configuration validator refuses a deployment configuration that is missing,
malformed, or pointed at the wrong network or token. It never fills a gap in:
the designated test token address, the deployment target, the RPC endpoint and
the wallet permissions stay **unresolved** here, and ``UNRESOLVED`` is the only
accepted stand-in. A guessed value is a refusal, not a default.

The evidence validator refuses a result record that lacks its own identity, or
that carries a fabricated hash or a placeholder success in place of a real one.

Neither validator opens a socket or signs anything.
"""
import re

from exchange.errors import require
from exchange.ids import HEX32, canonical_json

#: The confirmed test network from the requirements. Reading a stated network id
#: is not guessing; the token address on it is still not ours to supply.
DESIGNATED_CHAIN_ID = 11155111

#: The marker a configuration must use for a value this side may not invent.
UNRESOLVED = "UNRESOLVED"

REQUIRED_CONFIG = ("networkName", "chainId", "quoteTokenAddress", "deploymentTarget",
                   "rpcEndpoint", "walletPermissions", "confirmationPolicy")

#: Values that must stay unresolved locally. Anything else in these fields is a
#: guess and is refused.
MUST_REMAIN_UNRESOLVED = ("quoteTokenAddress", "deploymentTarget", "rpcEndpoint",
                          "walletPermissions")

ADDRESS = re.compile(r"\A0x[0-9a-fA-F]{40}\Z")

#: Patterns that betray a fabricated or placeholder value.
FABRICATED = (re.compile(r"\A0x0+\Z"), re.compile(r"(?i)\A(todo|tbd|placeholder|example|xxx)"),
              re.compile(r"(?i)deadbeef"), re.compile(r"\A0x(00){20,}\Z"))

REQUIRED_EVIDENCE = ("schema", "runId", "commit", "tree", "worktreeClean", "commands",
                     "startedAt", "finishedAt", "scenarioDigest", "notRun")


def _fabricated(value):
    return any(pattern.search(value) for pattern in FABRICATED)


def validate_config(config):
    """Report whether a deployment configuration may be used locally.

    ``accepted`` means only that the shape is right and nothing was invented. It
    never means the configuration is approved or that an address was verified.
    """
    reasons = []
    if not isinstance(config, dict):
        return {"accepted": False, "reasons": ("EX_CONFIG_SHAPE_REFUSED",), "unresolved": (),
                "checked": 0}
    for key in REQUIRED_CONFIG:
        if key not in config:
            reasons.append(f"EX_CONFIG_MISSING:{key}")
    unresolved = []
    for key in MUST_REMAIN_UNRESOLVED:
        value = config.get(key)
        if value == UNRESOLVED:
            unresolved.append(key)
        elif value is not None:
            # A real value here would have to be verified configuration. This
            # side has none, so anything concrete is treated as a guess.
            reasons.append(f"EX_CONFIG_NOT_VERIFIED_HERE:{key}")
            if isinstance(value, str) and _fabricated(value):
                reasons.append(f"EX_CONFIG_FABRICATED:{key}")
            elif key == "quoteTokenAddress" and isinstance(value, str) \
                    and ADDRESS.match(value) is None:
                reasons.append(f"EX_CONFIG_MALFORMED:{key}")
    chain = config.get("chainId")
    if chain is not None:
        if not isinstance(chain, int) or isinstance(chain, bool):
            reasons.append("EX_CONFIG_MALFORMED:chainId")
        elif chain != DESIGNATED_CHAIN_ID:
            reasons.append("EX_CONFIG_WRONG_CHAIN:chainId")
    policy = config.get("confirmationPolicy")
    if policy is not None and not (isinstance(policy, dict)
                                   and isinstance(policy.get("confirmations"), int)
                                   and not isinstance(policy.get("confirmations"), bool)
                                   and policy["confirmations"] >= 1):
        reasons.append("EX_CONFIG_MALFORMED:confirmationPolicy")
    ordered = tuple(dict.fromkeys(reasons))
    return {"accepted": ordered == (), "reasons": ordered, "unresolved": tuple(unresolved),
            "checked": len(REQUIRED_CONFIG),
            "meaning": ("shape and non-invention only; no address is verified and no "
                        "deployment is authorized by this result")}


def local_config_template():
    """The configuration shape, with every external value left unresolved."""
    return {
        "networkName": "ethereum-sepolia",
        "chainId": DESIGNATED_CHAIN_ID,
        "quoteTokenAddress": UNRESOLVED,
        "deploymentTarget": UNRESOLVED,
        "rpcEndpoint": UNRESOLVED,
        "walletPermissions": UNRESOLVED,
        "confirmationPolicy": {"confirmations": 3,
                               "note": "a local reproducible choice, not a production policy"},
    }


def synthetic_rejection_cases():
    """Explicitly synthetic inputs that must be refused, for the negative tests."""
    good = local_config_template()
    return (
        ("missing a required key", {key: value for key, value in good.items()
                                    if key != "chainId"}, "EX_CONFIG_MISSING:chainId"),
        ("the wrong network", {**good, "chainId": 1}, "EX_CONFIG_WRONG_CHAIN:chainId"),
        ("a malformed network id", {**good, "chainId": "11155111"},
         "EX_CONFIG_MALFORMED:chainId"),
        ("a guessed token address", {**good, "quoteTokenAddress": "0x" + "ab" * 20},
         "EX_CONFIG_NOT_VERIFIED_HERE:quoteTokenAddress"),
        ("a fabricated token address", {**good, "quoteTokenAddress": "0x" + "00" * 20},
         "EX_CONFIG_FABRICATED:quoteTokenAddress"),
        ("a malformed token address", {**good, "quoteTokenAddress": "not-an-address"},
         "EX_CONFIG_MALFORMED:quoteTokenAddress"),
        ("a guessed endpoint", {**good, "rpcEndpoint": "https://example.invalid/rpc"},
         "EX_CONFIG_NOT_VERIFIED_HERE:rpcEndpoint"),
        ("a placeholder deployment target", {**good, "deploymentTarget": "TODO"},
         "EX_CONFIG_FABRICATED:deploymentTarget"),
        ("a malformed confirmation policy", {**good, "confirmationPolicy": {"confirmations": 0}},
         "EX_CONFIG_MALFORMED:confirmationPolicy"),
        ("not a mapping", ["chainId"], "EX_CONFIG_SHAPE_REFUSED"),
    )


def validate_result(record):
    """Refuse a local result record that cannot stand on its own identity."""
    reasons = []
    if not isinstance(record, dict):
        return {"accepted": False, "reasons": ("EX_EVIDENCE_SHAPE_REFUSED",)}
    for key in REQUIRED_EVIDENCE:
        if key not in record:
            reasons.append(f"EX_EVIDENCE_MISSING:{key}")
    for key in ("commit", "tree"):
        value = record.get(key)
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is None:
            reasons.append(f"EX_EVIDENCE_IDENTITY_REFUSED:{key}")
    digest_value = record.get("scenarioDigest")
    if isinstance(digest_value, str) and HEX32.match(digest_value) is None:
        reasons.append("EX_EVIDENCE_IDENTITY_REFUSED:scenarioDigest")
    if record.get("worktreeClean") is not True:
        reasons.append("EX_EVIDENCE_DIRTY_WORKTREE")
    commands = record.get("commands")
    if not (isinstance(commands, list) and commands
            and all(isinstance(entry, dict) and isinstance(entry.get("command"), str)
                    and isinstance(entry.get("exitCode"), int)
                    and not isinstance(entry.get("exitCode"), bool) for entry in commands)):
        reasons.append("EX_EVIDENCE_COMMANDS_REFUSED")
    for entry in commands if isinstance(commands, list) else ():
        if isinstance(entry, dict) and isinstance(entry.get("command"), str) \
                and _fabricated(entry["command"]):
            reasons.append("EX_EVIDENCE_FABRICATED:commands")
    not_run = record.get("notRun")
    if not isinstance(not_run, list):
        reasons.append("EX_EVIDENCE_NOT_RUN_REFUSED")
    else:
        for entry in not_run:
            if not (isinstance(entry, dict) and entry.get("status") == "NOT_RUN"
                    and isinstance(entry.get("obligation"), str)):
                reasons.append("EX_EVIDENCE_NOT_RUN_REFUSED")
                break
    for key in ("transactionHashes", "receipts", "blockIdentities"):
        value = record.get(key)
        if value in ("", [], {}, None):
            continue
        if value == "NOT_RUN":
            continue
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            for item in value:
                if _fabricated(item) or HEX32.match(item) is None:
                    reasons.append(f"EX_EVIDENCE_FABRICATED:{key}")
                    break
        else:
            reasons.append(f"EX_EVIDENCE_FABRICATED:{key}")
    ordered = tuple(dict.fromkeys(reasons))
    return {"accepted": ordered == (), "reasons": ordered,
            "canonicalBytes": len(canonical_json(record).encode("ascii"))
            if ordered == () else None}
