"""Current real-execution checklist; every unobserved slot remains NOT_RUN."""
from .current_prd import load, report

NOT_RUN = "NOT_RUN"
EVIDENCE_SLOTS = (
    ("deployedHead", "exact actual deployed commit"),
    ("deployedTree", "exact actual deployed tree"),
    ("requiredCiRun", "required checks on that exact head"),
    ("chainId", "observed Sepolia 11155111"),
    ("verifiedAddresses", "existing verified NFT and designated test PYUSD"),
    ("transactionHashes", "actual hash for each executed step"),
    ("receipts", "actual EVM transaction receipts, not a second business receipt"),
    ("blockIdentities", "block number/hash and canonicality"),
    ("confirmationPolicy", "actual finality/reorg policy"),
    ("events", "Oracle authority and actual logs"),
    ("perSegmentReconciliation", "principal, cap/P50 ETH/USD, confirmation, freezes, actual gas, unused unfreeze, refunds/releases, owner/holder"),
    ("uiAssertions", "actual source-specific browser journey"),
    ("artifactHashes", "full byte/size/hash readback"),
)
# No private environment or signer values belong in this source.
EXISTING_OWNER_DEPENDENCIES = (
    {"dependency": "actual native interfaces", "owner": "original runtime holder",
     "thisPackageDoes": "record exact absent binding; do not invent it",
     "status": "NOT_VERIFIED"},
    {"dependency": "shared-operation allocation only", "owner": "product owner",
     "thisPackageDoes": "continue fixed cap/confirmation/freeze/debit/unfreeze work",
     "status": "D-04 partially pending"},
)


def build(matrix=None):
    current = report("handoff")
    current["evidenceSlots"] = [
        {"slot": name, "requires": description, "status": NOT_RUN}
        for name, description in EVIDENCE_SLOTS
    ]
    current["existingOwnerDependencies"] = list(EXISTING_OWNER_DEPENDENCIES)
    current["remainingObligations"] = [entry["id"] for entry in load()["cases"]]
    current["scenarios"] = [
        dict(entry, steps=[entry["setup"], entry["expected"]],
             evidence={name: NOT_RUN for name, _ in EVIDENCE_SLOTS},
             localResult="NOT_VERIFIED against version 1.2")
        for entry in load()["demonstrations"]
    ]
    return current
