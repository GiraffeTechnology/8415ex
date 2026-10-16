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
import datetime
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

#: Identity fields that must carry real content. An empty or whitespace-only
#: value is not an identity, and it must not pass merely by being a string.
NON_EMPTY_IDENTITY = ("schema", "runId")


def parse_instant(value):
    """A UTC instant, or ``None`` when it is not one.

    The shape regex is not enough: ``2026-13-01T00:00:00Z`` and
    ``2026-02-29T00:00:00Z`` both match it while naming no real moment. The
    value is parsed as an actual calendar date so an impossible instant is
    refused, and the parsed value is returned so two instants can be ordered.
    """
    if not isinstance(value, str) or UTC_INSTANT.match(value) is None:
        return None
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc)
    except ValueError:
        # A shape-valid but impossible calendar instant.
        return None

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

#: Outcomes where a process was started but never reported an exit status: it
#: could not be launched, or it was stopped before exiting. A null exit code is
#: the truthful record for these, and any number here would be invented. 124 in
#: particular is a shell convention, not something the process reported.
NO_EXIT_OUTCOMES = ("error", "timeout")

#: Outcomes that must carry a real integer exit status.
EXIT_CODE_OUTCOMES = ("passed", "failed", "signalled")

#: The only outcome that may name a signal.
SIGNALLED_OUTCOME = "signalled"

#: An outcome is a pass only here. Everything else, however structurally valid
#: the record is, means the run that contains it did not pass.
PASSING_OUTCOME = "passed"


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
    executed = entry.get("executed")
    if "executed" in entry:
        if not _typed(executed, bool):
            reasons.append("EX_EVIDENCE_COMMAND_REFUSED:executed")
        elif executed is not (outcome in EXECUTED_OUTCOMES):
            # A record cannot say nothing ran and then report a result, nor say
            # it ran and report no result at all.
            reasons.append("EX_EVIDENCE_EXECUTED_MISMATCH")
    if outcome in UNEXECUTED_OUTCOMES:
        # Execution-only fields cannot turn an unexecuted placeholder into
        # evidence. Empty optional fields are harmless, populated ones are not.
        for key in ("signal", "durationMs", "stdout", "stderr", "rawLog",
                    "rawLogPath", "rawLogRef", "observedInRun", "selfReported"):
            if entry.get(key) not in (None, "", [], {}):
                reasons.append(f"EX_EVIDENCE_UNEXECUTED_SIGNAL:{key}")
        # Nothing ran, so there is no exit code to report. A success code here
        # would be invented evidence.
        if exit_code is not None:
            reasons.append("EX_EVIDENCE_UNEXECUTED_EXIT_CODE")
        for key in ("startedAt", "finishedAt"):
            if entry.get(key) is not None:
                reasons.append("EX_EVIDENCE_UNEXECUTED_TIMING")
    else:
        if outcome in NO_EXIT_OUTCOMES:
            # The process never reported an exit status. Null is the truthful
            # record; a number here is invented, including the 124 a shell
            # would substitute for a timeout.
            if exit_code is not None:
                reasons.append("EX_EVIDENCE_INVENTED_EXIT_CODE")
        elif not _typed(exit_code, int):
            reasons.append("EX_EVIDENCE_COMMAND_REFUSED:exitCode")
        elif outcome == "passed" and exit_code != 0:
            reasons.append("EX_EVIDENCE_OUTCOME_MISMATCH")
        elif outcome == "failed" and exit_code <= 0:
            # A failure reports a positive status; a negative one is a signal.
            reasons.append("EX_EVIDENCE_OUTCOME_MISMATCH")
        elif outcome == SIGNALLED_OUTCOME and exit_code >= 0:
            reasons.append("EX_EVIDENCE_OUTCOME_MISMATCH")
        # The signal field must agree with the real process result: present and
        # matching for a signalled process, absent for every other outcome.
        signal = entry.get("signal")
        if outcome == SIGNALLED_OUTCOME:
            if not _typed(signal, int) or signal <= 0:
                reasons.append("EX_EVIDENCE_SIGNAL_REFUSED")
            elif _typed(exit_code, int) and signal != -exit_code:
                reasons.append("EX_EVIDENCE_SIGNAL_MISMATCH")
        elif signal is not None:
            reasons.append("EX_EVIDENCE_SIGNAL_REFUSED")
        for key in ("startedAt", "finishedAt"):
            value = entry.get(key)
            if not isinstance(value, str) or UTC_INSTANT.match(value) is None:
                reasons.append(f"EX_EVIDENCE_COMMAND_REFUSED:{key}")
            elif parse_instant(value) is None:
                reasons.append(f"EX_EVIDENCE_INSTANT_REFUSED:{key}")
        began, ended = parse_instant(entry.get("startedAt")), \
            parse_instant(entry.get("finishedAt"))
        if began is not None and ended is not None and ended < began:
            reasons.append("EX_EVIDENCE_TIME_ORDER_REFUSED")
    return tuple(dict.fromkeys(reasons))


def validate_historical_citation(citation):
    """Check citation shape only, without verifying the referenced source.

    Historical citations are separate from current-run commands. Full source
    hashes, a run identity and an evidence locator make a citation inspectable;
    they do not establish that the cited execution or source was verified.
    """
    reason = ("EX_EVIDENCE_HISTORICAL_CITATION_REFUSED",)
    if not isinstance(citation, dict):
        return reason
    if citation.get("scope") != "historical-citation" or \
            citation.get("verification") != "unverified":
        return reason
    for key in ("observedInRun", "evidenceLocator"):
        value = citation.get(key)
        if not isinstance(value, str) or not value.strip() or _fabricated(value):
            return reason
    source = citation.get("sourceIdentity")
    if not isinstance(source, dict):
        return reason
    for key in ("commit", "tree"):
        value = source.get(key)
        if not isinstance(value, str) or COMMIT.fullmatch(value) is None or _fabricated(value):
            return reason
    return ()


def validate_result(record):
    """Refuse a local result record that cannot stand on its own identity.

    Every required field must be present, of the declared type, and in the
    declared format. A missing, null, boolean, numeric or container value in a
    hash field is refused, never read as "format not applicable".
    """
    if not isinstance(record, dict):
        return {"accepted": False, "reasons": ("EX_EVIDENCE_SHAPE_REFUSED",)}
    reasons = []
    citations = record.get("historicalCitations", [])
    if not isinstance(citations, list):
        reasons.append("EX_EVIDENCE_HISTORICAL_CITATION_REFUSED")
    else:
        for citation in citations:
            reasons.extend(validate_historical_citation(citation))
            if isinstance(citation, dict) and citation.get("observedInRun") == record.get("runId"):
                reasons.append("EX_EVIDENCE_HISTORICAL_CITATION_CURRENT_RUN")
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
        elif pattern is UTC_INSTANT and parse_instant(value) is None:
            # Shape-valid but not a real calendar instant.
            reasons.append(f"EX_EVIDENCE_INSTANT_REFUSED:{key}")
        elif key in NON_EMPTY_IDENTITY and value.strip() == "":
            reasons.append(f"EX_EVIDENCE_EMPTY_REFUSED:{key}")
        elif _fabricated(value):
            reasons.append(f"EX_EVIDENCE_FABRICATED:{key}")
    commands = record.get("commands")
    started, finished = parse_instant(record.get("startedAt")), \
        parse_instant(record.get("finishedAt"))
    if started is not None and finished is not None and finished < started:
        # A run cannot finish before it started.
        reasons.append("EX_EVIDENCE_TIME_ORDER_REFUSED")
    # A command this run executed must have run while this run was running. A
    # record whose own commands sit outside its own window is describing work
    # from somewhere else, however well-formed each half looks on its own.
    #
    # This validator validates current-run evidence only. A historical run ID
    # is a citation, not proof of its source tree, log integrity or timing.
    # Historical evidence belongs in historicalCitations with its own source,
    # run and locator, explicitly unverified. It cannot bypass this window by
    # supplying observedInRun on a current-run command.
    if started is not None and finished is not None and isinstance(commands, list):
        for entry in commands:
            if not isinstance(entry, dict) or entry.get("outcome") in UNEXECUTED_OUTCOMES:
                continue
            origin = entry.get("observedInRun")
            if "observedInRun" in entry:
                if not isinstance(origin, str) or origin.strip() == "":
                    reasons.append("EX_EVIDENCE_REFERENCED_RUN_REFUSED")
                elif origin != record.get("runId"):
                    reasons.append("EX_EVIDENCE_HISTORICAL_COMMAND_UNSUPPORTED")
            began = parse_instant(entry.get("startedAt"))
            ended = parse_instant(entry.get("finishedAt"))
            if (began is not None and began < started) or \
                    (ended is not None and ended > finished):
                reasons.append("EX_EVIDENCE_COMMAND_OUTSIDE_RUN")
                break
    if record.get("worktreeClean") is False:
        reasons.append("EX_EVIDENCE_DIRTY_WORKTREE")
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
            obligation = entry.get("obligation") if isinstance(entry, dict) else None
            if not (isinstance(entry, dict) and entry.get("status") == "NOT_RUN"
                    and isinstance(obligation, str) and obligation.strip() != ""):
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
    # Structural validity and "the run passed" are two different questions. A
    # genuine failure, timeout, start error or signal record is perfectly valid
    # evidence, and it must still stop the run it belongs to from being read as
    # a pass. ``accepted`` answers the first question only.
    not_passing = []
    if isinstance(commands, list):
        for entry in commands:
            if not isinstance(entry, dict):
                continue
            outcome = entry.get("outcome")
            if outcome in EXECUTED_OUTCOMES and outcome != PASSING_OUTCOME:
                not_passing.append(f"{entry.get('command')} ended {outcome}")
            elif outcome == "pending":
                not_passing.append(f"{entry.get('command')} is still pending")
    return {"accepted": ordered == (), "reasons": ordered,
            "commandOutcomes": [entry.get("outcome") for entry in commands
                                if isinstance(entry, dict)]
            if isinstance(commands, list) else [],
            "historicalCitationsVerified": False,
            "historicalCitationCount": len(citations) if isinstance(citations, list) else 0,
            "historicalCitationScope": "citations only; excluded from current-run proof",
            "notPassing": tuple(not_passing),
            "runPassed": ordered == () and not_passing == [],
            "canonicalBytes": len(canonical_json(record).encode("ascii"))
            if ordered == () else None}
