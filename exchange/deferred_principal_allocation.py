"""Narrow, pure original-journal allocation policy for PRD EX-DEFER-05.

This is not another wallet ledger, proof issuer, store or execution adapter.
Sources are authenticated projections of actual original principal receipts.
Claims consume those source receipts across ALL obligations in one original
journal scope. Balances are derived, never maintained alongside deferred escrow.

A plan is NOT a principal-allocation Fact and is NOT committed. The original
aggregate owner must atomically commit the claim and the corresponding deferred
credit, checking the exact before bytes/generation and original native revision.
An absent/ambiguous save cannot publish a Fact, credit escrow or dispatch funds.
"""
from copy import deepcopy
from dataclasses import dataclass
import json

from .errors import require
from .ids import canonical_json, digest, identifier

CODE = "EX_DEFERRED_PRINCIPAL_ALLOCATION_REFUSED"
SCHEMA = "ex-original-principal-allocation/1"


def _uint(value, *, positive=False):
    require(type(value) is int and (0 < value if positive else 0 <= value)
            and value < 2 ** 256, CODE, "exact bounded integer required")
    return value


def _fields(value, expected):
    require(type(value) is dict and set(value) == set(expected), CODE,
            "original record fields differ")


def _record(value):
    require(type(value) is dict and bool(value), CODE,
            "complete original authority record required")
    canonical_json(value)


@dataclass(frozen=True)
class PrincipalDestination:
    """Private exact terms from the original, still-open deferred obligation.

    Constructing this object does not attest an obligation or permit a payment.
    The joint transition must resolve it again from the same deferred preimage.
    """
    obligation_id: str
    obligation_terms: str
    chain: int
    asset: str
    borrower: str
    escrow: str

    def __post_init__(self):
        for value in (self.obligation_id, self.obligation_terms, self.asset,
                      self.borrower, self.escrow):
            identifier(value, CODE)
        _uint(self.chain, positive=True)

    @property
    def terms(self):
        return {"obligationId": self.obligation_id,
                "obligationTerms": self.obligation_terms, "chain": self.chain,
                "asset": self.asset, "borrower": self.borrower,
                "escrow": self.escrow}


@dataclass(frozen=True)
class PrincipalAllocationPlan:
    """Immutable byte plan; no native write, financial receipt or dispatch."""
    scope: str
    journal_reference: str
    expected_revision: int
    before: bytes
    after: bytes
    claim_bytes: bytes
    repeated: bool

    @property
    def commitment(self):
        return digest({"scope": self.scope, "journal": self.journal_reference,
                       "expectedRevision": self.expected_revision,
                       "before": self.before.decode("ascii"),
                       "after": self.after.decode("ascii"),
                       "claim": self.claim_bytes.decode("ascii")})


class DeferredPrincipalAllocator:
    """Pure policy over an authenticated, exhaustive original journal snapshot.

    verify_original(snapshot) must validate source/store/scope identity, current
    revision/freshness, final actual receipt, exact asset/recipient/amount, global source
    exclusivity, all claims and other consumption, and pending/UNKNOWN effects.
    It must reject omission of committed claims or reuse in another scope. An
    unsigned dictionary, schema match or caller 'verified' flag is not evidence.

    verify_cut(source_binding, cut) must independently validate the original
    authoritative ordered registration cut, exact source segment/NFT/journal,
    effective time/deadline and permanent extinguishment of its full refundable
    principal. Current holder, address equality, state labels or a payment alone
    cannot establish this. Both callbacks are read-only trusted injection ports.
    No defaults or production adapter are supplied.
    """
    def __init__(self, scope, journal_reference, verify_original, verify_cut):
        self.scope = identifier(scope, CODE)
        self.journal_reference = identifier(journal_reference, CODE)
        require(callable(verify_original) and callable(verify_cut), CODE,
                "original journal and ordered-cut verifiers required")
        self._verify_original = verify_original
        self._verify_cut = verify_cut

    @staticmethod
    def _bytes(snapshot):
        return canonical_json(snapshot).encode("ascii")

    @staticmethod
    def _source_binding(binding):
        _fields(binding, ("sourceId", "kind", "chain", "asset", "borrower",
                          "escrow", "receivedUnits", "creditOperation",
                          "receiptIdentity", "segment"))
        for field in ("sourceId", "asset", "borrower", "escrow",
                      "creditOperation", "receiptIdentity"):
            identifier(binding[field], CODE)
        _uint(binding["chain"], positive=True)
        _uint(binding["receivedUnits"], positive=True)
        require(binding["kind"] in ("resale", "top-up"), CODE,
                "only actual resale principal or borrower top-up")
        segment = binding["segment"]
        if binding["kind"] == "top-up":
            require(segment is None, CODE, "top-up cannot impersonate a segment")
        else:
            _fields(segment, ("receiptId", "transferId", "legIndex", "nftChain",
                              "nftContract", "tokenId", "buyer", "seller",
                              "principalAsset", "principalUnits", "journalReference"))
            for key in ("receiptId", "transferId", "nftContract", "buyer",
                        "seller", "principalAsset", "journalReference"):
                identifier(segment[key], CODE)
            for key in ("legIndex", "tokenId"):
                _uint(segment[key])
            _uint(segment["nftChain"], positive=True)
            _uint(segment["principalUnits"], positive=True)
            require(segment["buyer"] != segment["seller"]
                    and segment["seller"] == binding["borrower"]
                    and segment["principalAsset"] == binding["asset"]
                    and segment["principalUnits"] == binding["receivedUnits"]
                    and segment["nftChain"] == binding["chain"], CODE,
                    "original resale segment and actual credit differ")

    def _source(self, source_id, source):
        _fields(source, ("binding", "receipt", "cut", "refund", "spentElsewhereUnits",
                         "pendingEffects"))
        binding = source["binding"]
        self._source_binding(binding)
        require(source_id == binding["sourceId"], CODE, "source key differs")
        _record(source["receipt"])
        _uint(source["spentElsewhereUnits"])
        require(source["spentElsewhereUnits"] <= binding["receivedUnits"], CODE,
                "original source conservation failure")
        pending = source["pendingEffects"]
        require(type(pending) is list, CODE, "original pending effects required")
        for item in pending:
            identifier(item, CODE)
        require(len(set(pending)) == len(pending), CODE, "duplicate pending effect")
        cut = source["cut"]
        if cut is not None:
            require(binding["kind"] == "resale", CODE, "top-up has no registration cut")
            _fields(cut, ("identity", "sourceBinding", "refundableUnitsExtinguished",
                          "original"))
            identifier(cut["identity"], CODE)
            _uint(cut["refundableUnitsExtinguished"], positive=True)
            require(cut["sourceBinding"] == digest(binding)
                    and cut["refundableUnitsExtinguished"] == binding["receivedUnits"],
                    CODE, "ordered cut does not extinguish exact original exposure")
            _record(cut["original"])
            require(self._verify_cut(deepcopy(binding), deepcopy(cut)) is True,
                    CODE, "original ordered-cut authority unavailable")
        refund = source["refund"]
        refunded = 0
        if refund is not None:
            require(binding["kind"] == "resale" and cut is None, CODE,
                    "registered release and original suffix refund are exclusive")
            _fields(refund, ("identity", "sourceBinding", "units", "recipient", "original"))
            identifier(refund["identity"], CODE)
            _uint(refund["units"], positive=True)
            require(refund["sourceBinding"] == digest(binding)
                    and refund["units"] == binding["receivedUnits"]
                    and refund["recipient"] == binding["segment"]["buyer"], CODE,
                    "refund must return exact original principal to original buyer")
            _record(refund["original"])
            refunded = refund["units"]
        # Unregistered resale principal is fully protected. Top-up has no
        # suffix liability only if the original financial verifier confirms it.
        protected = binding["receivedUnits"] - refunded if binding["kind"] == "resale" and cut is None else 0
        return protected, refunded

    def _validate(self, snapshot, *, authenticate):
        _fields(snapshot, ("schema", "scope", "journalReference", "revision",
                           "sources", "claims"))
        require(snapshot["schema"] == SCHEMA and snapshot["scope"] == self.scope
                and snapshot["journalReference"] == self.journal_reference,
                CODE, "original journal identity differs; no migration")
        _uint(snapshot["revision"])
        sources, claims = snapshot["sources"], snapshot["claims"]
        require(type(sources) is dict and type(claims) is dict, CODE,
                "complete original sources and shared allocation claims required")
        receipts, operations, segments, cuts = set(), set(), set(), {}
        protected, refunded, allocated = {}, {}, {key: 0 for key in sources}
        for source_id, source in sources.items():
            identifier(source_id, CODE)
            protected[source_id], refunded[source_id] = self._source(source_id, source)
            b = source["binding"]
            # These identities may not be relabelled as a new top-up/source.
            for value, seen in ((b["receiptIdentity"], receipts),
                                (b["creditOperation"], operations)):
                require(value not in seen, CODE, "original receipt reused")
                seen.add(value)
            if b["segment"] is not None:
                segment_key = digest({key: b["segment"][key] for key in
                    ("journalReference", "receiptId", "transferId", "legIndex",
                     "nftChain", "nftContract", "tokenId")})
                require(segment_key not in segments, CODE, "original segment reused")
                segments.add(segment_key)
                require(b["segment"]["journalReference"] == self.journal_reference,
                        CODE, "source segment belongs to another journal")
            if source["cut"] is not None:
                cut_id = source["cut"]["identity"]
                original_cut = digest(source["cut"]["original"])
                require(cut_id not in cuts or cuts[cut_id] == original_cut, CODE,
                        "same original ordered-cut identity changed content")
                cuts[cut_id] = original_cut
        for claim_id, claim in claims.items():
            _fields(claim, ("allocationId", "sourceId", "sourceBinding",
                            "sourceReceipt", "cutCommitment", "destination",
                            "units", "createdRevision"))
            identifier(claim_id, CODE)
            identifier(claim["sourceId"], CODE)
            require(claim["allocationId"] == claim_id and claim["sourceId"] in sources,
                    CODE, "allocation identity or source differs")
            source = sources[claim["sourceId"]]
            b = source["binding"]
            _uint(claim["units"], positive=True)
            _uint(claim["createdRevision"], positive=True)
            require(claim["createdRevision"] <= snapshot["revision"], CODE,
                    "allocation revision is in the future")
            _fields(claim["destination"], ("obligationId", "obligationTerms", "chain",
                                           "asset", "borrower", "escrow"))
            d = claim["destination"]
            PrincipalDestination(d["obligationId"], d["obligationTerms"], d["chain"],
                                 d["asset"], d["borrower"], d["escrow"])
            require(all(d[key] == b[key] for key in ("chain", "asset", "borrower", "escrow"))
                    and claim["sourceBinding"] == digest(b)
                    and claim["sourceReceipt"] == b["receiptIdentity"]
                    and claim["cutCommitment"] == (digest(source["cut"]) if source["cut"] else None),
                    CODE, "allocation source, destination or original cut changed")
            require(protected[claim["sourceId"]] == 0 and source["refund"] is None, CODE,
                    "refundable resale principal cannot be allocated")
            allocated[claim["sourceId"]] += claim["units"]
        for source_id, source in sources.items():
            require(allocated[source_id] + source["spentElsewhereUnits"] + refunded[source_id]
                    <= source["binding"]["receivedUnits"] - protected[source_id], CODE,
                    "source principal over-allocated or refund exposure consumed")
        if authenticate:
            require(self._verify_original(deepcopy(snapshot)) is True, CODE,
                    "current exhaustive original principal journal not verified")
        return protected, refunded, allocated

    def restore(self, raw):
        """Revalidate exact canonical bytes and original authority, not flags."""
        require(type(raw) is bytes, CODE, "original canonical bytes required")
        try:
            snapshot = json.loads(raw.decode("ascii"))
        except (ValueError, UnicodeError) as error:
            raise ValueError("invalid original principal allocation snapshot") from error
        # Canonical equality also rejects duplicate fields, noncanonical numbers,
        # whitespace disguises and unexpected JSON representations.
        require(self._bytes(snapshot) == raw, CODE, "noncanonical original snapshot")
        self._validate(snapshot, authenticate=True)
        return deepcopy(snapshot)

    def availability(self, raw, source_id):
        snapshot = self.restore(raw)
        identifier(source_id, CODE)
        require(source_id in snapshot["sources"], CODE, "unknown source")
        protected, refunded, allocated = self._validate(snapshot, authenticate=False)
        source = snapshot["sources"][source_id]
        unallocated = (source["binding"]["receivedUnits"] - protected[source_id]
                       - source["spentElsewhereUnits"] - refunded[source_id] - allocated[source_id])
        return {"protectedUnits": protected[source_id], "allocatedUnits": allocated[source_id],
                "refundedUnits": refunded[source_id],
                "availableUnits": 0 if source["pendingEffects"] else unallocated,
                "reconcileOnly": bool(source["pendingEffects"])}

    def plan(self, raw, destination, *, source_id, allocation_id, units, expected_revision):
        """Propose exactly one immutable claim; never commit or manufacture funds."""
        snapshot = self.restore(raw)
        require(type(destination) is PrincipalDestination, CODE, "exact destination required")
        for value in (source_id, allocation_id):
            identifier(value, CODE)
        _uint(units, positive=True)
        _uint(expected_revision)
        require(expected_revision == snapshot["revision"], CODE, "stale original revision")
        require(source_id in snapshot["sources"], CODE, "original source unavailable")
        source = snapshot["sources"][source_id]
        b = source["binding"]
        require(all(destination.terms[key] == b[key]
                    for key in ("chain", "asset", "borrower", "escrow")), CODE,
                "no currency, chain, account or destination substitution")
        existing = snapshot["claims"].get(allocation_id)
        claim = {"allocationId": allocation_id, "sourceId": source_id,
                 "sourceBinding": digest(b), "sourceReceipt": b["receiptIdentity"],
                 "cutCommitment": digest(source["cut"]) if source["cut"] else None,
                 "destination": destination.terms, "units": units,
                 "createdRevision": existing["createdRevision"] if existing else expected_revision + 1}
        if existing is not None:
            require(existing == claim, CODE, "same allocation identity has changed terms")
            return PrincipalAllocationPlan(self.scope, self.journal_reference,
                expected_revision, raw, raw, self._bytes(claim), True)
        require(not source["pendingEffects"], CODE,
                "unknown original effect must reconcile before allocation")
        require(expected_revision + 1 < 2 ** 256, CODE, "revision exhausted")
        after = deepcopy(snapshot)
        after["revision"] += 1
        after["claims"][allocation_id] = claim
        self._validate(after, authenticate=False)
        return PrincipalAllocationPlan(self.scope, self.journal_reference,
            expected_revision, raw, self._bytes(after), self._bytes(claim), False)
