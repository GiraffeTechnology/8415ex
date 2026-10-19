"""Atomic storage of one receipt's declared fact collections, without execution."""
from .aggregate_checkpoint import AggregateCheckpointStore, CheckpointRefused
from .ledger import Transfer
from .model import Asset, WarehouseReceipt
from .operational_facts_codec import encode_operational_facts, decode_operational_facts
from .receipt_checkpoint_codec import encode_receipt_facts, decode_receipt_facts
from .registration import RegistrationRequest, RegistrationEvidence
from .rollback import RollbackStep
from .settlement import EscrowPosition


class ReceiptFactCheckpointRefused(ValueError):
    pass


GROUPS = {
    "transfers": (Transfer, "transfer_id"),
    "registrationRequests": (RegistrationRequest, "request_id"),
    "registrationEvidence": (RegistrationEvidence, "result_id"),
    "escrows": (EscrowPosition, "escrow_id"),
    "rollbackSteps": (RollbackStep, "step_id"),
}


def _validate(receipt, facts):
    if type(receipt) is not WarehouseReceipt or type(facts) is not dict or set(facts) != set(GROUPS):
        raise ReceiptFactCheckpointRefused("exact receipt and declared fact groups required")
    by_group = {}
    for group, (cls, identity) in GROUPS.items():
        records = facts[group]
        if type(records) is not tuple:
            raise ReceiptFactCheckpointRefused("immutable ordered fact collections required")
        index = {}
        for record in records:
            if (type(record) is not cls or record.receipt_id != receipt.receipt_id
                    or getattr(record, identity) in index):
                raise ReceiptFactCheckpointRefused("fact type, receipt or identity conflict")
            index[getattr(record, identity)] = record
        by_group[group] = index
    transfers = by_group["transfers"]
    by_leg = {}
    for record in transfers.values():
        if type(record.leg_index) is not int or record.leg_index < 0 or record.leg_index in by_leg:
            raise ReceiptFactCheckpointRefused("unique original transfer occurrence required")
        by_leg[record.leg_index] = record
    for record in transfers.values():
        previous_id = record.predecessor_transfer_id
        if previous_id is not None:
            previous = transfers.get(previous_id)
            if previous is None or previous.leg_index >= record.leg_index or previous.buyer != record.seller:
                raise ReceiptFactCheckpointRefused("original transfer predecessor conflict")
    for request in by_group["registrationRequests"].values():
        transfer = transfers.get(request.transfer_id)
        if (request.asset != receipt.asset or request.adapter != receipt.registration_path
                or transfer is None or transfer.leg_index != request.leg_index
                or request.predecessor_transfer_id != transfer.predecessor_transfer_id):
            raise ReceiptFactCheckpointRefused("registration request binding conflict")
    for observation in by_group["registrationEvidence"].values():
        request = by_group["registrationRequests"].get(observation.request_id)
        if (request is None or observation.asset != receipt.asset
                or observation.transfer_id != request.transfer_id
                or observation.leg_index != request.leg_index
                or observation.adapter != request.adapter):
            raise ReceiptFactCheckpointRefused("registration observation binding conflict")
    escrow_legs = {}
    for position in by_group["escrows"].values():
        transfer = by_leg.get(position.leg_index)
        if (transfer is None or position.leg_index in escrow_legs
                or position.payer != transfer.buyer or position.payee != transfer.seller
                or position.principal != transfer.price or position.quote_asset != transfer.quote_asset):
            raise ReceiptFactCheckpointRefused("original segment principal binding conflict")
        escrow_legs[position.leg_index] = position
    for step in by_group["rollbackSteps"].values():
        if type(step.leg_index) is not int or step.leg_index not in by_leg:
            raise ReceiptFactCheckpointRefused("rollback occurrence binding conflict")
        if step.kind == "refund" and step.leg_index not in escrow_legs:
            raise ReceiptFactCheckpointRefused("refund step has no original escrow")
        if step.kind == "refund":
            position = escrow_legs[step.leg_index]
            if position.status == "released" or position.payment_intent == "release":
                raise ReceiptFactCheckpointRefused("original release cannot become a refund")


class ReceiptFactCheckpoint:
    """Two codecs saved in one original generation; no live Exchange mutation.

    The caller supplies a stable original fact snapshot. This adapter does not
    capture one from live objects, restore operational authority or claim that
    these five groups cover all Exchange state and original native journals.
    """

    COMPONENTS = ("declaration", "operations")

    def __init__(self, store):
        self.store = store
        self._contract()

    def _contract(self):
        if (type(self.store) is not AggregateCheckpointStore
                or self.store.components != self.COMPONENTS):
            raise ReceiptFactCheckpointRefused("dedicated exact two-component store required")

    def save(self, receipt, facts, *, expected_generation):
        self._contract()
        # Decode detached immutable bytes before validation; do not persist a
        # mutable input after validating an earlier version of its nested data.
        try:
            declaration = encode_receipt_facts(receipt)
            operations = encode_operational_facts(facts)
            original = decode_receipt_facts(declaration).receipt
            snapshot = decode_operational_facts(operations).value
            _validate(original, snapshot)
        except (TypeError, ValueError, KeyError, AttributeError):
            raise ReceiptFactCheckpointRefused("receipt checkpoint facts conflict") from None
        # CommitUnknown deliberately propagates unchanged. Never retry here.
        return self.store.save(original.receipt_id,
                               {"declaration": declaration, "operations": operations},
                               expected_generation=expected_generation)

    def read(self, receipt_id, *, expected_asset):
        self._contract()
        if type(expected_asset) is not Asset:
            raise ReceiptFactCheckpointRefused("original expected asset identity required")
        record = self.store.read(receipt_id)
        if record is None:
            return None
        try:
            receipt = decode_receipt_facts(record["components"]["declaration"]).receipt
            facts = decode_operational_facts(record["components"]["operations"]).value
            if receipt.receipt_id != receipt_id or receipt.asset != expected_asset:
                raise ValueError()
            _validate(receipt, facts)
        except (TypeError, ValueError, KeyError, AttributeError):
            raise ReceiptFactCheckpointRefused("stored receipt checkpoint conflicts") from None
        return {"receipt": receipt, "facts": facts, "generation": record["generation"],
                "digest": record["digest"], "executionAuthorized": False,
                "nativeReconciliation": "NOT_PERFORMED", "completeExchangeRecovery": False}
