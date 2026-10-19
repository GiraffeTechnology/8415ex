"""Persist one original direct-boundary rollback advance without changing it."""
from .exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint
from .serialized_exchange_access import SerializedExchangeAccess


class DirectReturnProgressNotSaved(RuntimeError):
    """Live effects may exist although the following snapshot was not acknowledged."""

    def __init__(self, storage_error, *, before, domain_error=None, report=None):
        super().__init__("original rollback progress requires outcome reconciliation")
        self.storage_error = storage_error
        self.before = before
        self.domain_error = domain_error
        self.report = report


class DirectReturnCheckpoint:
    """Optional composition around the existing original rollback method.

    This is neither an execution permission nor an installed wallet prerequisite.
    All participating writers must share the same access object. The local
    snapshots and external controller journal are not one atomic transaction.
    """

    def __init__(self, access, checkpoint, scope):
        if (type(access) is not SerializedExchangeAccess
                or not isinstance(checkpoint, ExchangeSnapshotCheckpoint)):
            raise ValueError("original serialized access and snapshot checkpoint required")
        checkpoint.store._scope(scope)
        self.access = access
        self.checkpoint = checkpoint
        self.scope = scope

    def advance(self, receipt_id, *, expected_generation, now=None):
        with self.access._lock:
            before = self.checkpoint.save(self.scope, self.access.snapshot_bytes(),
                                          expected_generation=expected_generation)
            report = None
            domain_error = None
            try:
                # Exactly one original method invocation. Its single asset
                # return goes directly to the effective holder boundary; each
                # original principal refund remains an independent operation.
                report = self.access.advance_rollback(receipt_id, now)
            except Exception as error:
                domain_error = error
            try:
                after = self.checkpoint.save(self.scope, self.access.snapshot_bytes(),
                                             expected_generation=before["generation"])
            except Exception as error:
                # Preserve live progress and both errors. No retry, rewind,
                # reservation release or guessed no-effect conclusion.
                raise DirectReturnProgressNotSaved(error, before=before,
                    domain_error=domain_error, report=report) from error
            if domain_error is not None:
                raise domain_error
            return {"report": report, "beforeCheckpoint": before,
                    "afterCheckpoint": after, "completeRecovery": False}
