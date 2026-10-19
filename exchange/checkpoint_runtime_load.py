"""Load one original stored generation into a new EX access object."""
from dataclasses import dataclass

from .exchange_fact_rehydration import rehydrate_exchange_facts
from .exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint


@dataclass(frozen=True)
class LoadedExchangeCheckpoint:
    access: object
    scope: str
    generation: int
    digest: str
    source_commit: str
    source_tree: str


def load_exchange_checkpoint(checkpoint, scope, runtime):
    """Read once, reconstruct those exact bytes, and retain their generation.

    The caller supplies its existing original store and currently configured
    fresh runtime. No path, database initialization, journal migration, source
    fallback, retry, controller enquiry or domain advance is performed here.
    A missing checkpoint remains missing. The returned generation is the read
    observation, not a lease on the store or permission to execute an effect.
    """
    if not isinstance(checkpoint, ExchangeSnapshotCheckpoint):
        raise ValueError("original complete snapshot checkpoint required")
    row = checkpoint.read(scope)
    if row is None:
        return None
    raw = row["components"]["owned-facts"]
    access = rehydrate_exchange_facts(raw, runtime)
    return LoadedExchangeCheckpoint(access=access, scope=row["scope"],
        generation=row["generation"], digest=row["digest"],
        source_commit=checkpoint.store.source["commit"],
        source_tree=checkpoint.store.source["tree"])
