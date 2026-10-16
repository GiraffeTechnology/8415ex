"""The open-decision register: what is undecided, and what it actually blocks.

An undecided question is not the same as a defect, and it is not the same as a
blocked stage. Each entry here names one open decision, who confirms it, the
narrowest scope that genuinely waits on it, and the work that proceeds anyway.
Recording the last column is the point: without it an open decision tends to be
read as blocking far more than it does, and work that is authorized stops.

Nothing here answers a decision. Where a question could be settled by reading
an existing interface or configuration rather than by a product choice, that is
said, so it is investigated instead of being escalated.

Identifiers and this package's own English wording only. No approved-requirement
text, document identity, digest or private locator appears in this source.
"""

#: Who is recorded as confirming a decision. These are roles in this project's
#: own terms, not an assertion that any outside party is involved.
PRODUCT_OWNER = "the product owner"
ENGINEERING = "engineering, by checking the existing interfaces and configuration"
PRODUCT_OWNER_AFTER_ENGINEERING = (
    "engineering establishes what the existing components already do, and the "
    "product owner confirms any remaining choice")

#: Whether this package can carry the decision's consequence locally.
LOCAL_MODEL_PROCEEDS = "local model and fixtures proceed"
LOCAL_MODEL_BLOCKED = "the dependent local branch waits"

OPEN_DECISIONS = (
    {
        "id": "D-01",
        "undecided": "the final matching priority and fairness rules",
        "confirmedBy": PRODUCT_OWNER,
        "blocks": "a formal matching engine beyond explicitly paired intents",
        "doesNotBlock": "the paired-intent fixture, the asset model and the "
                        "authorization model, all of which are in place",
        "localStatus": LOCAL_MODEL_PROCEEDS,
    },
    {
        "id": "D-02",
        "undecided": "the complete set of mint condition fields, their time unit "
                     "and permitted ranges",
        "confirmedBy": PRODUCT_OWNER_AFTER_ENGINEERING,
        "blocks": "real input and validation for the undecided fields in the exit "
                  "stage",
        "doesNotBlock": "the fields already recorded, and a fixed-instant fixture",
        "localStatus": LOCAL_MODEL_PROCEEDS,
    },
    {
        "id": "D-03",
        "undecided": "the exact precedence when a registration timeout, the trading "
                     "cutoff and an in-flight result collide",
        "confirmedBy": PRODUCT_OWNER,
        "blocks": "the affected boundary branch in the exit stage, and the "
                  "corresponding deployed scenario",
        "doesNotBlock": "refusing a new trade after the cutoff, and ordinary "
                        "registration and rollback, which are implemented",
        "localStatus": LOCAL_MODEL_PROCEEDS,
        "reportedBy": "DEMO-06 records the collision rather than ranking it",
    },
    {
        "id": "D-04",
        "undecided": "the gas budget, over-limit handling, apportionment of a shared "
                     "operation, and how a fee is actually deducted",
        "confirmedBy": PRODUCT_OWNER_AFTER_ENGINEERING,
        "blocks": "real fee deduction, and the send path that depends on it",
        "doesNotBlock": "the responsibility model in which the buyer bears that "
                        "leg's gas, and the labelled fee fixtures",
        "localStatus": LOCAL_MODEL_PROCEEDS,
        "reportedBy": "DEMO-03 records the whole principal in the quote asset and "
                      "the gas amount, unit and bearer separately, and leaves "
                      "actual deduction NOT_RUN",
    },
    {
        "id": "D-05",
        "undecided": "the precise implementation of real asset-return control and "
                     "wallet authorization",
        "confirmedBy": ENGINEERING,
        "blocks": "a real on-chain rollback",
        "doesNotBlock": "the confirmed rollback business outcome, the state machine "
                        "and its fixtures",
        "localStatus": LOCAL_MODEL_PROCEEDS,
    },
    {
        "id": "D-06",
        "undecided": "the recovery detail when registration is confirmed but payment "
                     "has temporarily failed",
        "confirmedBy": PRODUCT_OWNER_AFTER_ENGINEERING,
        "blocks": "real integration of that failure branch in the settlement stage",
        "doesNotBlock": "ordinary independent per-segment settlement and the "
                        "idempotency model",
        "localStatus": LOCAL_MODEL_PROCEEDS,
    },
    {
        "id": "D-07",
        "undecided": "the confirmation and recovery order for voucher hand-over, "
                     "stopping resale and the burn",
        "confirmedBy": PRODUCT_OWNER,
        "blocks": "the real exit sequence and the corresponding deployed scenario",
        "doesNotBlock": "eligibility checks, the refusal cases and the retained "
                        "history",
        "localStatus": LOCAL_MODEL_PROCEEDS,
        "reportedBy": "DEMO-06 reports the undecided ordering rather than choosing one",
    },
    {
        "id": "D-08",
        "undecided": "how the existing source, journal, asset and segment components "
                     "bind to the deployment interfaces",
        "confirmedBy": ENGINEERING,
        "blocks": "the real integration path for whichever interface is missing",
        "doesNotBlock": "the other paths and the domain layer",
        "localStatus": LOCAL_MODEL_PROCEEDS,
    },
    {
        "id": "D-09",
        "undecided": "the compatibility matrix of required wallet capabilities",
        "confirmedBy": ENGINEERING,
        "blocks": "real execution against any wallet that has not been verified",
        "doesNotBlock": "the already supported paths and the compatibility contract "
                        "checks",
        "localStatus": LOCAL_MODEL_PROCEEDS,
        "note": "the presence of a token or provider interface is not evidence that "
                "a wallet satisfies this project's semantics",
    },
    {
        "id": "D-10",
        "undecided": "the agent service fee mechanism, its rate, when it applies, who "
                     "bears it and how it is refunded",
        "confirmedBy": PRODUCT_OWNER,
        "blocks": "connecting any commercial charge",
        "doesNotBlock": "the core trading mechanism through every stage, and a "
                        "demonstration with no commercial charge",
        "localStatus": LOCAL_MODEL_PROCEEDS,
    },
    {
        "id": "D-11",
        "undecided": "the formal asset classes, outside cooperation, real registrars "
                     "and commercial admission",
        "confirmedBy": PRODUCT_OWNER,
        "blocks": "later real business expansion",
        "doesNotBlock": "the three simulated paths and the whole-receipt "
                        "demonstration",
        "localStatus": LOCAL_MODEL_PROCEEDS,
    },
    {
        "id": "D-12",
        "undecided": "commercial pricing, revenue, funding narrative, operations and "
                     "the legal path",
        "confirmedBy": "the product owner and the professionals they designate",
        "blocks": "a later commercial version or any outward commitment",
        "doesNotBlock": "all currently authorized test development",
        "localStatus": LOCAL_MODEL_PROCEEDS,
    },
    {
        "id": "D-13",
        "undecided": "the approved absolute directory for the private requirements "
                     "copy, and its write-back receipt",
        "confirmedBy": "the party holding access to that environment",
        "blocks": "synchronising that one document",
        "doesNotBlock": "the private hand-off and every authorized development item "
                        "that does not depend on that synchronisation",
        "localStatus": LOCAL_MODEL_PROCEEDS,
        "owner": "not this package: no credential or persistent access is set up here",
    },
)

#: Defaults that must never be assumed in place of a decision. Each of these has
#: been offered as an obvious answer at some point and is none.
REFUSED_DEFAULTS = (
    "a pre-funded test account standing in for a decided gas policy",
    "a budget deduction standing in for a decided fee mechanism",
    "remote attestation, a device lock or a new security setting standing in for "
    "a decided authorization model",
)


def register():
    """The whole register, with what it does and does not block."""
    blocked, proceeding = [], []
    for entry in OPEN_DECISIONS:
        (blocked if entry["localStatus"] == LOCAL_MODEL_BLOCKED
         else proceeding).append(entry["id"])
    return {
        "schema": "8415ex-open-decisions/1",
        "decisions": [dict(entry) for entry in OPEN_DECISIONS],
        "decisionCount": len(OPEN_DECISIONS),
        "localWorkBlockedBy": blocked,
        "localWorkProceedingDespite": proceeding,
        "refusedDefaults": list(REFUSED_DEFAULTS),
        "meaning": ("an open decision is not a defect and not a blocked stage; each "
                    "entry names the narrowest scope that waits on it and the work "
                    "that proceeds anyway, so authorized work is not stopped by a "
                    "question it does not depend on"),
        "answersNothing": True,
    }


def reported_locally():
    """Decisions a scenario reports as an observation rather than resolving."""
    return {entry["id"]: entry["reportedBy"] for entry in OPEN_DECISIONS
            if entry.get("reportedBy")}
