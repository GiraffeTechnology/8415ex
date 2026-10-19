"""One original access boundary for domain calls, UI observations and snapshots."""
from copy import deepcopy
from threading import RLock

from .ledger import Exchange
from .workbench import RuntimeBinding
from .exchange_fact_snapshot import encode_exchange_snapshot
from .exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint


class SerializedAccessRefused(ValueError):
    pass


class SerializedExchangeAccess:
    """Host composition object, not authorization or protection from its owner.

    All writers/readers must use this instance. Retained raw Exchange references
    and separate wrappers are outside its lock. A domain call retains its original
    behavior; this class never retries a callback, widens a grant or rolls back a
    native effect. Checkpointing remains an explicit separate operation.
    """

    def __init__(self, exchange):
        if type(exchange) is not Exchange:
            raise SerializedAccessRefused("exact original Exchange instance required")
        self._exchange = exchange
        self._lock = RLock()

    def __getattr__(self, name):
        if (type(name) is not str or name.startswith("_")
                or not callable(vars(Exchange).get(name))):
            raise AttributeError("original public domain method required")
        def original_call(*args, **kwargs):
            with self._lock:
                result = getattr(self._exchange, name)(*args, **kwargs)
                # No mutable original domain result escapes the writer lock.
                return deepcopy(result)
        return original_call

    def snapshot_bytes(self):
        with self._lock:
            return encode_exchange_snapshot(self._exchange)

    def write_checkpoint(self, checkpoint, scope, *, expected_generation):
        if not isinstance(checkpoint, ExchangeSnapshotCheckpoint):
            raise SerializedAccessRefused("original snapshot checkpoint adapter required")
        with self._lock:
            raw = encode_exchange_snapshot(self._exchange)
            # The same lock covers capture, continuity preflight and generation
            # CAS. Original storage errors and commit UNKNOWN propagate once.
            return checkpoint.save(scope, raw, expected_generation=expected_generation)

    def bind_runtime(self, receipt_id, **options):
        return SerializedRuntimeBinding(self, receipt_id, **options)


class SerializedRuntimeBinding(RuntimeBinding):
    """Existing workbench contract with each complete observation under one lock."""

    def __init__(self, access, receipt_id, **options):
        if type(access) is not SerializedExchangeAccess:
            raise SerializedAccessRefused("the same original access object is required")
        self._access = access
        super().__init__(access, receipt_id, **options)

    def snapshot(self):
        # RuntimeBinding.snapshot reads several methods. Locking those methods
        # individually would still permit interleaving between subobservations.
        with self._access._lock:
            return super().snapshot()

    def public_detail(self):
        with self._access._lock:
            return super().public_detail()

    def command(self, action, key, revision, payload):
        # Original revision, gateway enquiry, task scope and authorization checks
        # remain in the original command implementation. Nested domain calls on
        # the same thread are supported by RLock; no gateway is invented here.
        with self._access._lock:
            return super().command(action, key, revision, payload)
