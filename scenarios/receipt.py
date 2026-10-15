"""The candidate receipt: the nine groups a candidate must account for.

A delivery contract is only useful if the shape it asks for is produced by the
code rather than assembled by hand each time, where a group can quietly go
missing. This builds that shape from the artefacts a run already produced, and
where a group covers work this package does not perform - deployment, chain
execution - it emits the group with NOT_RUN rather than omitting it. A missing
group and an unperformed one look identical in a hand-written receipt; here
they cannot.

The nine groups:

1. source identity: repository, branch, full commit and tree, parent and base
   identity, and the exact diff range
2. requirements: which identifiers this candidate claims, which are recorded as
   not locally testable, and what is unimplemented or unexecuted
3. environment: platform, runtime, the actual commands, a configuration summary
   and the unique run id
4. results: totals, per-item outcomes, exit codes, start and end instants, and
   where the raw log for this run can be read
5. artifacts: every produced file with its byte count, digest, how it was built
   and where it is stored
6. deployment: target, deployed version, URL and health verification, or an
   explicit statement that nothing was deployed
7. chain: chain id, verified addresses, transaction hashes, receipts, block
   identity, confirmation policy and events, or NOT_RUN for each
8. per-scenario reconciliation: for each rollback or settlement scenario, the
   per-segment funds, gas, owner and holder positions, registration prefix and
   recovery outcome
9. blockers: the exact action blocked, the missing evidence or decision, the
   affected scope, its owner, and the independent work that continued

The private requirements identity belongs in group 2 and is never embedded in
this source. It is supplied at call time through the same mechanism the scan
uses for private markers, and only its presence is reported unless the caller
asks for it, so a public artifact never carries it.
"""
import os

from . import decisions, manifest

#: The environment variable through which the private requirements identity may
#: be supplied at call time. Its value is never written into this source, and
#: never into a record unless the caller explicitly includes it.
REQUIREMENTS_IDENTITY_ENV = "EX_REQUIREMENTS_IDENTITY"

NOT_RUN = "NOT_RUN"

#: Group 7, every field a real chain run would have to supply.
CHAIN_FIELDS = ("chainId", "verifiedAddresses", "transactionHashes", "receipts",
                "blockIdentities", "confirmationPolicy", "events", "finalAssertions")

#: Group 6, every field a real deployment would have to supply.
DEPLOYMENT_FIELDS = ("target", "deployedCommit", "deployedTree", "url",
                     "startupVerification", "healthVerification", "recovery")


def _requirements_identity(supplied=None):
    """Whether a private requirements identity was supplied, without echoing it."""
    value = supplied if supplied is not None else os.environ.get(
        REQUIREMENTS_IDENTITY_ENV, "")
    present = bool(str(value).strip())
    return {
        "supplied": present,
        "where": ("supplied at call time through the approved private mechanism"
                  if present else
                  "not supplied to this run; the identity is held privately and is "
                  "never embedded in this source"),
        "publishedHere": False,
    }


def _source_group(root, source, parents=None, diff_range=None):
    identity = dict(source)
    identity["parents"] = list(parents or manifest.parent_identity(root)["parents"])
    identity["base"] = (diff_range or manifest.parent_identity(root))["base"]
    identity["diffRange"] = (diff_range
                             or manifest.parent_identity(root))["diffRange"]
    return identity


def build(bundle, root=".", requirements_identity=None, artifacts=(),
          deployment=None, chain=None, blockers=None):
    """One receipt over a completed run, with every group present.

    ``bundle`` is the record a run produced; nothing is recomputed from it.
    ``artifacts`` are the files the caller produced from that run, each as a
    mapping with at least a path; their bytes and digests are read here so the
    receipt cannot disagree with what is on disk.
    """
    source = bundle.get("source", {})
    scenario_report = bundle.get("scenarioReport", {})
    path_report = bundle.get("pathReport", {})
    acceptance = bundle.get("matrix", {})
    coverage = acceptance.get("requirementCoverage", {})
    checklist = bundle.get("handoff", {})

    measured = []
    for entry in artifacts:
        path = entry.get("path") if isinstance(entry, dict) else entry
        record = {"path": str(path),
                  "builtBy": (entry.get("builtBy") if isinstance(entry, dict)
                              else None) or "scenarios.cli, this run",
                  "storedAt": (entry.get("storedAt") if isinstance(entry, dict)
                               else None) or "private hand-off; not in the repository"}
        try:
            record.update(manifest.digest_of(path))
        except OSError as problem:
            record.update({"bytes": None, "sha256": None, "error": str(problem)})
        measured.append(record)

    commands = bundle.get("commands", [])
    results = {
        "commandCount": len(commands),
        "commands": [{"command": entry.get("command"),
                      "outcome": entry.get("outcome"),
                      "exitCode": entry.get("exitCode"),
                      "startedAt": entry.get("startedAt"),
                      "finishedAt": entry.get("finishedAt"),
                      "stdoutSha256": (entry.get("stdout") or {}).get("sha256"),
                      "stderrSha256": (entry.get("stderr") or {}).get("sha256")}
                     for entry in commands if isinstance(entry, dict)],
        "scenarioTotals": scenario_report.get("totals"),
        "pathTotals": path_report.get("totals"),
        "scenariosPassed": scenario_report.get("scenariosPassed"),
        "scenariosTotal": scenario_report.get("scenariosTotal"),
        "rawLog": ("the per-command stdout and stderr digests above identify the raw "
                   "output; the full log is handed over privately, outside the "
                   "repository"),
    }

    reconciliation = []
    for scenario in scenario_report.get("scenarios", []):
        segments = []
        for step in scenario.get("steps", []):
            facts = step.get("facts", {})
            if any(key in facts for key in ("payee", "principal", "released",
                                            "affectedLegs", "boundary")):
                segments.append({"step": step.get("name"), "facts": facts})
        reconciliation.append({
            "scenarioId": scenario.get("scenarioId"),
            "mainPath": scenario.get("mainPath"),
            "ownerAndHolder": [
                {"step": step.get("name"),
                 "owner": step.get("facts", {}).get("owner"),
                 "ownerPosition": step.get("facts", {}).get("ownerPosition"),
                 "holder": step.get("facts", {}).get("holder"),
                 "holderPosition": step.get("facts", {}).get("holderPosition"),
                 "registeredPrefixLegs": step.get("facts", {}).get(
                     "registeredPrefixLegs")}
                for step in scenario.get("steps", [])
                if "owner" in step.get("facts", {})],
            "fundsAndGas": segments,
            "recoveryOutcome": scenario.get("passed"),
            "scope": scenario.get("scope"),
        })

    return {
        "schema": "8415ex-candidate-receipt/1",
        "runId": bundle.get("runId"),
        "groups": {
            "1-source": _source_group(root, source),
            "2-requirements": {
                "requirementsIdentity": _requirements_identity(requirements_identity),
                "claimed": sorted(coverage.get("claimedByCases", {})),
                "claimedCount": coverage.get("claimedCount"),
                "notLocallyTestable": coverage.get("notLocallyTestable", {}),
                "unclaimed": coverage.get("unclaimed", []),
                "unimplementedOrUnexecuted": [
                    {"case": row.get("case"),
                     "state": row.get("localOutcome"),
                     "requires": row.get("remainingRealEvidence")}
                    for row in acceptance.get("rows", [])
                    if row.get("localOutcome") in ("not-run", "incomplete", "blocked",
                                                   "failed", "error")],
                "openDecisions": decisions.register(),
            },
            "3-environment": {
                "runtime": bundle.get("runtime"),
                "platformConstraint": "Linux only; no other platform is used for "
                                      "any run reported here",
                "commands": [entry.get("command") for entry in commands
                             if isinstance(entry, dict)],
                "configurationSummary": bundle.get("configuration", {}).get(
                    "validation"),
                "runId": bundle.get("runId"),
                "startedAt": bundle.get("startedAt"),
                "finishedAt": bundle.get("finishedAt"),
            },
            "4-results": results,
            "5-artifacts": {
                "artifacts": measured,
                "artifactCount": len(measured),
                "sourceInventory": {
                    "fileCount": bundle.get("manifest", {}).get("fileCount"),
                    "totalBytes": bundle.get("manifest", {}).get("totalBytes"),
                    "consistent": bundle.get("manifest", {}).get("consistent"),
                },
            },
            "6-deployment": dict(
                {field: NOT_RUN for field in DEPLOYMENT_FIELDS},
                **(deployment or {}),
                statement=("nothing was deployed by this run; this package does not "
                           "deploy, and no deployed identity may be inferred from a "
                           "candidate package name")),
            "7-chain": dict(
                {field: NOT_RUN for field in CHAIN_FIELDS},
                **(chain or {}),
                statement=("no transaction was sent, signed or broadcast by this "
                           "run; every field above stays NOT_RUN until its "
                           "authorized owner supplies genuine evidence"),
                evidenceSlots=checklist.get("evidenceSlots", [])),
            "8-reconciliation": {
                "scenarios": reconciliation,
                "note": ("principal is an amount in the quote asset and gas is a "
                         "count of gas units borne by a named party; the two are "
                         "recorded side by side and never subtracted"),
            },
            "9-blockers": {
                "blockers": list(blockers or []),
                "blockingFromThisRun": bundle.get("blocking", []),
                "independentWorkContinued": True,
                "note": ("a blocker names the exact action, its target, the error or "
                         "missing input, the affected scope, the owner and the next "
                         "step; only the dependent work pauses"),
            },
        },
        "groupsPresent": 9,
        "meaning": ("every group is present whether or not this package performs "
                    "that work, so an unperformed group reads NOT_RUN and cannot be "
                    "confused with a group that was left out"),
    }
