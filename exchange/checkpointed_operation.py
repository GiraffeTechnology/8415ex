"""Persist EX facts after the original claim and before its checked native gate."""
from copy import deepcopy
import hashlib
import json

from .durable_operation import (DurableEXOperationJournal, DurableNativeOutcomeUnknown,
                                _scope as original_operation_scope)
from .exchange_fact_snapshot import decode_exchange_snapshot
from .exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint
from .serialized_exchange_access import SerializedExchangeAccess


class CheckpointedOperationRefused(ValueError):
    pass


class CheckpointedOperationBridge:
    """Trusted host composition only, not an HTTP command or new execution grant.

    Original native enquiry, scope validation, receipt CAS, durable UNKNOWN claim,
    grant/funds/gas/nonce and actual read-and-act remain the original gateway's.
    This adds a durable pre-effect snapshot, not a cross-journal transaction or
    an economic outcome. No database, scope or provider default is selected.
    """

    def __init__(self, access, checkpoint, journal, checkpoint_scope):
        if (type(access) is not SerializedExchangeAccess
                or not isinstance(checkpoint, ExchangeSnapshotCheckpoint)
                or not isinstance(journal, DurableEXOperationJournal)):
            raise CheckpointedOperationRefused("original access, snapshot store and operation journal required")
        # Reuse the original store's exact scope contract without selecting one.
        checkpoint.store._scope(checkpoint_scope)
        self.access = access
        self.checkpoint = checkpoint
        self.journal = journal
        self.checkpoint_scope = checkpoint_scope

    def pre_effect_scope(self, binding):
        scope = original_operation_scope(binding)
        # A stable original-operation data key, not a new tenant or resource.
        # Later operations must not overwrite this operation's recovery preimage.
        encoded = json.dumps({"instanceScope": self.checkpoint_scope, "operation": scope},
                             sort_keys=True, separators=(",", ":"), allow_nan=False)
        return "pre-effect:" + hashlib.sha256(encoded.encode("ascii")).hexdigest()

    def invoke(self, binding, *, expected_operation_revision,
               enquire_original, execute_original):
        if not callable(enquire_original) or not callable(execute_original):
            raise CheckpointedOperationRefused("installed original enquiry and checked native gate required")
        scope = original_operation_scope(binding)
        pre_effect_error = None
        saved_checkpoint = None

        def dispatch(checked_scope):
            nonlocal pre_effect_error, saved_checkpoint
            try:
                raw = self.access.snapshot_bytes()
                facts = decode_exchange_snapshot(raw)
                receipt = facts.receipts.get(checked_scope["receiptId"])
                if (receipt is None or checked_scope["chainId"] != receipt.asset.chain_id
                        or checked_scope["contract"] != receipt.asset.contract
                        or checked_scope["tokenId"] != str(receipt.asset.token_id)):
                    raise CheckpointedOperationRefused("original operation asset differs from captured EX facts")
                # One immutable byte set is validated and persisted. A second
                # capture must not silently substitute another domain version.
                saved_checkpoint = self.checkpoint.save(self.pre_effect_scope(checked_scope), raw,
                    expected_generation=0)
            except Exception as error:
                pre_effect_error = error
                raise
            return execute_original(deepcopy(checked_scope))

        with self.access._lock:
            try:
                observed = self.journal.invoke_once(scope, expected_operation_revision,
                                                    enquire_original, dispatch)
            except DurableNativeOutcomeUnknown:
                if pre_effect_error is not None:
                    # Original invoke_once conservatively retains UNKNOWN for
                    # every dispatch-closure failure. Preserve the more precise
                    # snapshot refusal/commit UNKNOWN: the native gate was not
                    # called. Do not clear or reconcile that original claim.
                    raise pre_effect_error from None
                raise
        return {"operation": observed, "preEffectCheckpoint": saved_checkpoint,
                "snapshotMeaning": "EX-owned facts before original native gate, not its outcome",
                "executionAuthorized": False, "completeRecovery": False, "replayAllowed": False}
