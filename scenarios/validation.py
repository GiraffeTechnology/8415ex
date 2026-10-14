"""Deterministic configuration and evidence validation, failing closed.

Both validators are local and read-only, and both refuse rather than assume.

Every required field is checked for presence, type and format. A field that is
present but null is a refusal, not an absence: treating `null` as "not supplied"
is how an invalid record slips through, so each required field names its own
reason. Optional fields are optional only where this schema says so.

The configuration validator never fills an external gap: the designated test
token address, the deployment target, the endpoint and the wallet permissions
stay UNRESOLVED here, and anything concrete in those fields is refused as
unverified. The declared network name must agree with the declared chain.

The evidence validator refuses a record that lacks its own identity, carries a
fabricated hash, or claims a success whose execution was not established.
"""
import re

from exchange.ids import canonical_json

#: The confirmed test network from the requirements, with the name it must
#: declare. Reading a stated network identity is not guessing; the token address
#: on it is still not ours to supply.
DESIGNATED_CHAIN_ID = 11155111
CHAIN_NAMES = {DESIGNATED_CHAIN_ID: "ethereum-sepolia"}

#: The marker a configuration must use for a value this side may not invent.
UNRESOLVED = "UNRESOLVED"

#: Values that must stay unresolved locally. Anything else is a guess.
MUST_REMAIN_UNRESOLVED = ("quoteTokenAddress", "deploymentTarget", "rpcEndpoint",
                          "walletPermissions")

#: Required configuration keys and the type each must carry when present.
CONFIG_SCHEMA = {
    "networkName": str,
    "chainId": int,
    "quoteTokenAddress": str,
    "deploymentTarget": str,
    "rpcEndpoint": str,
    "walletPermissions": str,
    "confirmationPolicy": dict,
}
REQUIRED_CONFIG = tuple(CONFIG_SCHEMA)

ADDRESS = re.compile(r"\A0x[0-9a-fA-F]{40}\Z")
COMMIT = re.compile(r"\A[0-9a-f]{40}\Z")
DIGEST = re.compile(r"\A0x[0-9a-f]{64}\Z")
UTC_INSTANT = re.compile(r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")

#: Patterns that betray a fabricated or placeholder value.
FABRICATED = (re.compile(r"\A0x0+\Z"), re.compile(r"(?i)\A(todo|tbd|placeholder|example|xxx)"),
              re.compile(r"(?i)deadbeef"), re.compile(r"\A0x(00){20,}\Z"))

#: Required evidence fields: the type each must carry, and the format it must
#: match when it is a string. A hash field is never accepted as null, as a
#: number, as a boolean, or as a container.
EVIDENCE_SCHEMA = {
    "schema": (str, None),
    "runId": (str, None),
    "commit": (str, COMMIT),
    "tree": (str, COMMIT),
    "worktreeClean": (bool, None),
    "commands": (list, None),
    "startedAt": (str, UTC_INSTANT),
    "finishedAt": (str, UTC_INSTANT),
    "scenarioDigest": (str, DIGEST),
    "notRun": (list, None),
}
REQUIRED_EVIDENCE = tuple(EVIDENCE_SCHEMA)

#: Optional evidence fields that may be absent, but are validated when present.
#: ``NOT_RUN`` is the only non-list value any of them may carry.
OPTIONAL_CHAIN_EVIDENCE = ("transactionHashes", "receipts", "blockIdentities")

#: Command record outcomes. A pending or not-run command never carries a
#: success exit code, and only an executed command may be "passed".
COMMAND_OUTCOMES = ("passed", "failed", "pending", "not-run", "error", "timeout", "signalled")
EXECUTED_OUTCOMES = ("passed", "failed", "error", "timeout", "signalled")
UNEXECUTED_OUTCOMES = ("pending", "not-run")


def _fabricated(value):
    return isinstance(value, str) and any(pattern.search(value) for pattern in FABRICATED)


def _typed(value, expected):
    """Exact type check. ``bool`` is not an acceptable ``int`` here."""
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected is bool:
        return isinstance(value, bool)
    return isinstance(value, expected)


def validate_config(config):
    """Report whether a deployment configuration may be used locally.

    ``accepted`` means only that every required field is present with the right
    type and that nothing external was invented. It never means the
    configuration is approved or that an address was verified.
    """
    if not isinstance(config, dict):
        return {"accepted": False, "reasons": ("EX_CONFIG_SHAPE_REFUSED",), "unresolved": (),
                "checked": 0, "meaning": "a configuration must be a mapping"}
    reasons, unresolved = [], []
    for key, expected in CONFIG_SCHEMA.items():
        if key not in config:
            reasons.append(f"EX_CONFIG_MISSING:{key}")
            continue
        value = config[key]
        if value is None:
            # Present-null is a refusal in its own right. It is not an absence,
            # and it must not fall through the type or value checks below.
            reasons.append(f"EX_CONFIG_NULL_REFUSED:{key}")
            continue
        if not _typed(value, expected):
            reasons.append(f"EX_CONFIG_TYPE_REFUSED:{key}")
            continue
        if key in MUST_REMAIN_UNRESOLVED:
            if value == UNRESOLVED:
                unresolved.append(key)
            else:
                reasons.append(f"EX_CONFIG_NOT_VERIFIED_HERE:{key}")
                if _fabricated(value):
                    reasons.append(f"EX_CONFIG_FABRICATED:{key}")
                elif key == "quoteTokenAddress" and ADDRESS.match(value) is None:
                    reasons.append(f"EX_CONFIG_MALFORMED:{key}")
        elif key == "chainId":
            if value != DESIGNATED_CHAIN_ID:
                reasons.append("EX_CONFIG_WRONG_CHAIN:chainId")
        elif key == "confirmationPolicy":
            confirmations = value.get("confirmations")
            if not _typed(confirmations, int) or confirmations < 1:
                reasons.append("EX_CONFIG_MALFORMED:confirmationPolicy")
        elif key == "networkName" and value.strip() == "":
            reasons.append("EX_CONFIG_MALFORMED:networkName")
    # The declared name must agree with the declared chain, so a record cannot
    # carry one network's name over another network's id.
    chain, name = config.get("chainId"), config.get("networkName")
    if _typed(chain, int) and isinstance(name, str):
        expected_name = CHAIN_NAMES.get(chain)
        if expected_name is not None and name != expected_name:
            reasons.append("EX_CONFIG_NETWORK_MISMATCH:networkName")
        elif expected_name is None:
            reasons.append("EX_CONFIG_WRONG_CHAIN:chainId")
    ordered = tuple(dict.fromkeys(reasons))
    return {"accepted": ordered == (), "reasons": ordered, "unresolved": tuple(unresolved),
            "checked": len(CONFIG_SCHEMA),
            "meaning": ("presence, type and non-invention only; no address is verified and no "
                        "deployment is authorized by this result")}


def local_config_template():
    """The configuration shape, with every external value left unresolved."""
    return {
        "networkName": CHAIN_NAMES[DESIGNATED_CHAIN_ID],
        "chainId": DESIGNATED_CHAIN_ID,
        "quoteTokenAddress": UNRESOLVED,
        "deploymentTarget": UNRESOLVED,
        "rpcEndpoint": UNRESOLVED,
        "walletPermissions": UNRESOLVED,
        "confirmationPolicy": {"confirmations": 3,
                               "note": "a local reproducible choice, not a production policy"},
    }


def synthetic_rejection_cases():
    """Explicitly synthetic inputs that must be refused, for the negative tests.

    Each case names the one reason it exists to prove. They are invented values,
    never a real address, endpoint or path.
    """
    good = local_config_template()
    cases = [
        ("missing a required key", {key: value for key, value in good.items()
                                    if key != "chainId"}, "EX_CONFIG_MISSING:chainId"),
        ("the wrong network", {**good, "chainId": 1}, "EX_CONFIG_WRONG_CHAIN:chainId"),
        ("a network name that disagrees with the chain",
         {**good, "networkName": "ethereum-mainnet"}, "EX_CONFIG_NETWORK_MISMATCH:networkName"),
        ("an empty network name", {**good, "networkName": "   "},
         "EX_CONFIG_MALFORMED:networkName"),
        ("a guessed token address", {**good, "quoteTokenAddress": "0x" + "ab" * 20},
         "EX_CONFIG_NOT_VERIFIED_HERE:quoteTokenAddress"),
        ("a fabricated token address", {**good, "quoteTokenAddress": "0x" + "00" * 20},
         "EX_CONFIG_FABRICATED:quoteTokenAddress"),
        ("a malformed token address", {**good, "quoteTokenAddress": "not-an-address"},
         "EX_CONFIG_MALFORMED:quoteTokenAddress"),
        ("a guessed endpoint", {**good, "rpcEndpoint": "https://endpoint.invalid/rpc"},
         "EX_CONFIG_NOT_VERIFIED_HERE:rpcEndpoint"),
        ("a placeholder deployment target", {**good, "deploymentTarget": "TODO"},
         "EX_CONFIG_FABRICATED:deploymentTarget"),
        ("a malformed confirmation policy", {**good, "confirmationPolicy": {"confirmations": 0}},
         "EX_CONFIG_MALFORMED:confirmationPolicy"),
        ("not a mapping", ["chainId"], "EX_CONFIG_SHAPE_REFUSED"),
    ]
    # A present-null and a wrong type must be refused for every required key,
    # rather than being read as an absence or coerced.
    for key, expected in CONFIG_SCHEMA.items():
        cases.append((f"a present-null {key}", {**good, key: None},
                      f"EX_CONFIG_NULL_REFUSED:{key}"))
        wrong = True if expected is not bool else "yes"
        if expected is str:
            wrong = 1
        elif expected is int:
            wrong = "11155111"
        elif expected is dict:
            wrong = ["confirmations"]
        cases.append((f"a wrong-typed {key}", {**good, key: wrong},
                      f"EX_CONFIG_TYPE_REFUSED:{key}"))
    return tuple(cases)


def validate_command_record(entry):
    """One command record: what was run, how it ended, and whether it ran at all."""
    reasons = []
    if not isinstance(entry, dict):
        return ("EX_EVIDENCE_COMMAND_SHAPE_REFUSED",)
    command = entry.get("command")
    if not isinstance(command, str) or command.strip() == "":
        reasons.append("EX_EVIDENCE_COMMAND_REFUSED:command")
    elif _fabricated(command):
        reasons.append("EX_EVIDENCE_FABRICATED:commands")
    outcome = entry.get("outcome")
    if outcome not in COMMAND_OUTCOMES:
        reasons.append("EX_EVIDENCE_COMMAND_REFUSED:outcome")
        return tuple(dict.fromkeys(reasons))
    exit_code = entry.get("exitCode")
    if outcome in UNEXECUTED_OUTCOMES:
        # Nothing ran, so there is no exit code to report. A success code here
        # would be invented evidence.
        if exit_code is not None:
            reasons.append("EX_EVIDENCE_UNEXECUTED_EXIT_CODE")
        for key in ("startedAt", "finishedAt"):
            if entry.get(key) is not None:
                reasons.append("EX_EVIDENCE_UNEXECUTED_TIMING")
    else:
        if not _typed(exit_code, int):
            reasons.append("EX_EVIDENCE_COMMAND_REFUSED:exitCode")
        elif outcome == "passed" and exit_code != 0:
            reasons.append("EX_EVIDENCE_OUTCOME_MISMATCH")
        elif outcome == "failed" and exit_code == 0:
            reasons.append("EX_EVIDENCE_OUTCOME_MISMATCH")
        for key in ("startedAt", "finishedAt"):
            value = entry.get(key)
            if not isinstance(value, str) or UTC_INSTANT.match(value) is None:
                reasons.append(f"EX_EVIDENCE_COMMAND_REFUSED:{key}")
    return tuple(dict.fromkeys(reasons))


def validate_result(record):
    """Refuse a local result record that cannot stand on its own identity.

    Every required field must be present, of the declared type, and in the
    declared format. A missing, null, boolean, numeric or container value in a
    hash field is refused, never read as "format not applicable".
    """
    if not isinstance(record, dict):
        return {"accepted": False, "reasons": ("EX_EVIDENCE_SHAPE_REFUSED",)}
    reasons = []
    for key, (expected, pattern) in EVIDENCE_SCHEMA.items():
        if key not in record:
            reasons.append(f"EX_EVIDENCE_MISSING:{key}")
            continue
        value = record[key]
        if value is None:
            reasons.append(f"EX_EVIDENCE_NULL_REFUSED:{key}")
            continue
        if not _typed(value, expected):
            reasons.append(f"EX_EVIDENCE_TYPE_REFUSED:{key}")
            continue
        if pattern is not None and pattern.match(value) is None:
            reasons.append(f"EX_EVIDENCE_IDENTITY_REFUSED:{key}")
        elif _fabricated(value):
            reasons.append(f"EX_EVIDENCE_FABRICATED:{key}")
    if record.get("worktreeClean") is False:
        reasons.append("EX_EVIDENCE_DIRTY_WORKTREE")
    commands = record.get("commands")
    if not isinstance(commands, list) or not commands:
        # A record with no command list, or one that is not a list at all,
        # carries no execution evidence of any kind.
        reasons.append("EX_EVIDENCE_COMMANDS_REFUSED")
    else:
        for entry in commands:
            reasons.extend(validate_command_record(entry))
    not_run = record.get("notRun")
    if not isinstance(not_run, list):
        reasons.append("EX_EVIDENCE_NOT_RUN_REFUSED")
    else:
        for entry in not_run:
            if not (isinstance(entry, dict) and entry.get("status") == "NOT_RUN"
                    and isinstance(entry.get("obligation"), str)):
                reasons.append("EX_EVIDENCE_NOT_RUN_REFUSED")
                break
    for key in OPTIONAL_CHAIN_EVIDENCE:
        if key not in record:
            continue
        value = record[key]
        if value == "NOT_RUN" or value == []:
            continue
        if not isinstance(value, list):
            reasons.append(f"EX_EVIDENCE_FABRICATED:{key}")
            continue
        for item in value:
            if not isinstance(item, str) or DIGEST.match(item) is None or _fabricated(item):
                reasons.append(f"EX_EVIDENCE_FABRICATED:{key}")
                break
    ordered = tuple(dict.fromkeys(reasons))
    return {"accepted": ordered == (), "reasons": ordered,
            "canonicalBytes": len(canonical_json(record).encode("ascii"))
            if ordered == () else None}
