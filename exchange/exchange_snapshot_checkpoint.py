"""Persist complete detached snapshots through the original generation CAS."""
from .aggregate_checkpoint import AggregateCheckpointStore
from .exchange_fact_snapshot import decode_exchange_snapshot
from .receipt_checkpoint_codec import encode_receipt_facts


class ExchangeCheckpointRefused(ValueError):
    pass


COMPONENTS = ("owned-facts",)


def _retained_map(previous, candidate):
    return all(key in candidate and candidate[key] == value for key, value in previous.items())


def _retained_prefix(previous, candidate):
    return type(previous) is list and type(candidate) is list and candidate[:len(previous)] == previous


def _continuity(previous, candidate):
    for identity, receipt in previous.receipts.items():
        current = candidate.receipts.get(identity)
        if current is None or encode_receipt_facts(current) != encode_receipt_facts(receipt):
            raise ExchangeCheckpointRefused("original receipt declaration cannot be removed or replaced")
        for name in ("_mint_declarations", "_nft0_currency_sets"):
            if candidate.domain[name][identity] != previous.domain[name][identity]:
                raise ExchangeCheckpointRefused("original complete mint declaration cannot be replaced")
        for name in ("_events", "_rollback_history"):
            if not _retained_prefix(previous.domain[name][identity], candidate.domain[name][identity]):
                raise ExchangeCheckpointRefused("original retained history prefix differs")
    if not previous.wallet["usedNonces"].issubset(candidate.wallet["usedNonces"]):
        raise ExchangeCheckpointRefused("consumed nonce history cannot be released by checkpointing")
    original_intents = {item.intent_id: item.digest for item in previous.wallet["intents"]}
    current_intents = {item.intent_id: item.digest for item in candidate.wallet["intents"]}
    if not _retained_map(original_intents, current_intents):
        raise ExchangeCheckpointRefused("original signed intent history differs")
    if previous.mint_indexes is not None:
        if candidate.mint_indexes is None or any(
                not _retained_map(previous.mint_indexes[name], candidate.mint_indexes[name])
                for name in ("_assets", "_receipts", "_documents")):
            raise ExchangeCheckpointRefused("original mint uniqueness identities differ")
    if not _retained_map(previous.domain["_applied_results"], candidate.domain["_applied_results"]):
        raise ExchangeCheckpointRefused("original applied-result idempotency identities differ")


class ExchangeSnapshotCheckpoint:
    """No database selection, live capture/mutation, authority restoration or effects.

    Preflight reads one generation, validates continuity against exactly that
    generation, then passes the SAME expected generation to original save().
    An intervening normal writer increments it and the original transactional
    CAS refuses this candidate. No compare against one generation followed by
    unconditional overwrite of another is allowed.
    """

    def __init__(self, store):
        if not isinstance(store, AggregateCheckpointStore) or store.components != COMPONENTS:
            raise ExchangeCheckpointRefused("original exact owned-facts component store required")
        self.store = store

    def read(self, scope):
        row = self.store.read(scope)
        if row is None:
            return None
        return {**row, "facts": decode_exchange_snapshot(row["components"]["owned-facts"]),
                "executionAuthorized": False, "completeRecovery": False}

    def save(self, scope, snapshot_bytes, *, expected_generation):
        if type(expected_generation) is not int or not 0 <= expected_generation < 2 ** 63 - 1:
            raise ExchangeCheckpointRefused("exact bounded expected generation required")
        if type(snapshot_bytes) is not bytes:
            raise ExchangeCheckpointRefused("complete immutable snapshot bytes required")
        candidate = decode_exchange_snapshot(snapshot_bytes)
        previous = self.read(scope)
        actual = previous["generation"] if previous is not None else 0
        if actual != expected_generation:
            raise ExchangeCheckpointRefused("preflight belongs to another generation")
        if previous is not None:
            _continuity(previous["facts"], candidate)
        # Captured bytes cannot drift between comparison and encoding. Original
        # save rechecks this same generation under BEGIN IMMEDIATE. Its source,
        # durability, foreign-transaction and commit-UNKNOWN boundaries remain.
        # In particular, never catch/retry CheckpointCommitUnknown here.
        result = self.store.save(scope, {"owned-facts": snapshot_bytes},
                                 expected_generation=expected_generation)
        return {**result, "executionAuthorized": False, "completeRecovery": False}
