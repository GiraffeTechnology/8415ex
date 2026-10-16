"""The execution handoff for the party that owns real deployment and chain work.

Every real-evidence slot starts as ``NOT_RUN``. A slot is never pre-filled with
a plausible-looking value: an empty slot says NOT_RUN, and a fabricated hash or
a placeholder success is refused by :mod:`scenarios.validation`.

This package does not deploy, does not send a transaction and holds no
credential. The checklist describes what the owning party must record.
"""
from .demos import MAIN_PATHS
from .validation import UNRESOLVED

NOT_RUN = "NOT_RUN"

#: Evidence every real run must record, in the order it becomes available.
EVIDENCE_SLOTS = (
    ("deployedHead", "the exact commit and tree actually deployed, full length"),
    ("deployedTree", "the tree of that commit"),
    ("requiredCiRun", "the required CI run id on that exact head, and its conclusion"),
    ("chainId", "the chain id actually connected to"),
    ("verifiedAddresses", "the verified contract and test token addresses, independently "
                          "checked rather than assumed"),
    ("transactionHashes", "one hash per executed step"),
    ("receipts", "the receipt for each transaction"),
    ("blockIdentities", "block number and hash per receipt"),
    ("confirmationPolicy", "the confirmation depth applied, and the reorg window observed"),
    ("events", "the emitted events per step, with log index"),
    ("perSegmentReconciliation", "principal, fees, net and final balance per segment"),
    ("uiAssertions", "the real browser journey per scenario, with what was asserted on screen"),
    ("artifactHashes", "byte counts and digests of the stored artifacts, read back"),
)

#: What each scenario needs on a real run, beyond its local assertions.
SCENARIO_STEPS = {
    "DEMO-01": ("mint one whole receipt", "fund and execute A to B", "file the holder change",
                "apply the registrar result", "release the segment",
                "request and complete the exit", "confirm the burn and the retained history"),
    "DEMO-02": ("execute A to B to C to D", "file one request per hop",
                "apply the later result first and observe the deferral",
                "apply the earlier results and observe the ordered advance",
                "release each segment independently"),
    "DEMO-03": ("execute A to B to C to D", "record the first-hop refusal",
                "open the rollback", "refund each buyer", "return the receipt to the origin"),
    "DEMO-04": ("settle the first segment", "record the second-hop refusal",
                "unwind only the later segments", "return the receipt to the first buyer",
                "show the settled segment untouched"),
    "DEMO-05": ("leave the intermediate wallets without gas", "attempt the return",
                "record the blocked, resumable state", "resume once the budget allows"),
    "DEMO-06": ("reach the stop-trading instant", "attempt a new trade and record the refusal",
                "complete the in-flight registration and settlement",
                "check the exit eligibility", "complete the exit"),
}


#: Things this package depends on but does not own, and must not change. Each
#: one names where it lives, who owns it and what this package does instead.
EXISTING_OWNER_DEPENDENCIES = (
    {
        "dependency": "mixed-unit projection in the rollback report",
        "where": "exchange/ledger.py, the netToOriginalBuyer field",
        "detail": "the field subtracts a gas-unit count from a quote-asset "
                  "principal, so its result is a number in no single unit",
        "owner": "the domain owner of exchange/ledger.py",
        "thisPackageDoes": "records the whole principal in the quote asset and the "
                           "gas amount, unit and bearer separately, observes the "
                           "legacy field without reading it as net proceeds, and "
                           "changes no domain code",
        "status": "open, reported to its owner",
    },
    {
        "dependency": "actual fee deduction from a refunded principal",
        "where": "open decision D-04",
        "detail": "whether a real fee is deducted from a refund, in which asset "
                  "and by whom, is undecided",
        "owner": "the party that owns the commercial decision",
        "thisPackageDoes": "models no deduction and records the obligation NOT_RUN",
        "status": "open decision",
    },
)


def build(matrix=None):
    """The checklist, with every real-evidence slot unfilled."""
    scenarios = []
    for scenario_id, path in sorted(MAIN_PATHS.items()):
        scenarios.append({
            "scenarioId": scenario_id,
            "mainPath": path,
            "steps": list(SCENARIO_STEPS[scenario_id]),
            "localResult": "recorded by scenarios.demos; model evidence only",
            "evidence": {name: NOT_RUN for name, _ in EVIDENCE_SLOTS},
        })
    return {
        "schema": "8415ex-execution-handoff/2",
        "existingOwnerDependencies": list(EXISTING_OWNER_DEPENDENCIES),
        "owner": "the party that owns approved-environment deployment and authorized "
                 "test-network execution",
        "preconditions": {
            "quoteTokenAddress": UNRESOLVED,
            "deploymentTarget": UNRESOLVED,
            "rpcEndpoint": UNRESOLVED,
            "walletPermissions": UNRESOLVED,
            "note": "these stay unresolved here and must be supplied from verified "
                    "configuration, never guessed",
        },
        "evidenceSlots": [{"slot": name, "requires": requirement, "status": NOT_RUN}
                          for name, requirement in EVIDENCE_SLOTS],
        "scenarios": scenarios,
        "remainingObligations": [row["case"] for row in (matrix or {}).get("rows", [])
                                 if row.get("remainingRealEvidence")],
        "rules": [
            "an empty slot says NOT_RUN; never a fabricated hash or a placeholder success",
            "a local model result never substitutes for real integration acceptance",
            "a rendered status page is not operable UI acceptance",
            "no mainnet activity, no real value movement, no new permission",
            "the presentation claims follow verified execution evidence, not expectations",
        ],
    }
