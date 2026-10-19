"""Retain reverse-hop sequence progress through the original snapshot CAS."""
import hashlib

from .exchange_fact_snapshot import decode_exchange_snapshot
from .exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint
from .operational_facts_codec import encode_operational_facts
from .rollback import RollbackStep


class RollbackSequenceCheckpointRefused(ValueError):
    pass


IDENTITY_FIELDS = ("authorityId", "source", "refusedLegIndex", "trigger", "triggerKind",
                   "boundaryIndex", "boundaryAccount", "finalizedPrefixLegs",
                   "affectedLegs", "openedAt", "sequenceId", "assetHops")


def _sequences(facts):
    result = {}
    for receipt_id in facts.receipts:
        states = [(item["state"], True) for item in facts.domain["_rollback_history"][receipt_id]]
        current = facts.domain["_rollbacks"][receipt_id]
        if current is not None:
            states.append((current, False))
        for state, archived in states:
            if type(state) is not dict:
                raise RollbackSequenceCheckpointRefused("original rollback state required")
            sequence = state.get("sequenceId")
            if sequence is None:
                # Preserve historical data without interpreting it as a new
                # sequence or authorizing its direct-return operation.
                sequence = "legacy:" + hashlib.sha256(encode_operational_facts(state)).hexdigest()
                item = {"legacy": True, "state": state, "archived": archived}
            else:
                path, cursor, steps = state.get("assetHops"), state.get("hopCursor"), state.get("steps")
                if (type(sequence) is not str or not sequence
                        or type(path) is not list or not path
                        or type(cursor) is not int or not 0 <= cursor <= len(path)
                        or type(steps) is not list or any(type(step) is not RollbackStep for step in steps)
                        or state.get("state") not in ("in-progress", "blocked", "complete")
                        or type(state.get("conflicts")) is not list):
                    raise RollbackSequenceCheckpointRefused("original typed hop sequence and cursor required")
                hops = [step for step in steps if step.kind == "asset-return"]
                if (len(hops) != len(path) or len({step.key for step in steps}) != len(steps)
                        or any(type(hop) is not dict or hop.get("key") != step.key
                               or hop.get("legIndex") != step.leg_index
                               or (index < cursor) != (step.status == "done")
                               or step.receipt_id != receipt_id
                               or (step.status == "done" and
                                   not (type(dict(step.detail).get("reference")) is str
                                        and bool(dict(step.detail)["reference"])))
                               for index, (hop, step) in enumerate(zip(path, hops)))
                        or any(field not in state for field in IDENTITY_FIELDS)
                        or ((archived or state.get("state") == "complete") and
                            (state.get("state") != "complete" or cursor != len(path)
                             or any(step.status != "done" for step in steps)))):
                    raise RollbackSequenceCheckpointRefused("original hop results or closed sequence conflict")
                item = {"legacy": False, "state": state, "archived": archived}
            key = (receipt_id, sequence)
            if key in result:
                raise RollbackSequenceCheckpointRefused("duplicate active or archived sequence identity")
            result[key] = item
    return result


def _retain(previous, candidate):
    for key, before in previous.items():
        after = candidate.get(key)
        if after is None or (before["archived"] and not after["archived"]):
            raise RollbackSequenceCheckpointRefused("retained sequence disappeared or was reactivated")
        old, new = before["state"], after["state"]
        if before["legacy"]:
            if new != old:
                raise RollbackSequenceCheckpointRefused("historical operation evidence cannot be reinterpreted")
            continue
        if (after["legacy"] or any(new[field] != old[field] for field in IDENTITY_FIELDS)
                or new["hopCursor"] < old["hopCursor"]
                or (old["state"] == "complete" and new["state"] != "complete")):
            raise RollbackSequenceCheckpointRefused("original path, cursor or closed-state identity regressed")
        old_steps = {step.key: step for step in old["steps"]}
        new_steps = {step.key: step for step in new["steps"]}
        if set(old_steps) != set(new_steps):
            raise RollbackSequenceCheckpointRefused("original refund or hop identities changed")
        for identity, step in old_steps.items():
            current = new_steps[identity]
            if ((step.kind, step.receipt_id, step.leg_index, step.step_id) !=
                    (current.kind, current.receipt_id, current.leg_index, current.step_id)
                    or (step.status == "done" and current != step)):
                raise RollbackSequenceCheckpointRefused("confirmed refund or hop outcome cannot be replaced")
        if new["conflicts"][:len(old["conflicts"])] != old["conflicts"]:
            raise RollbackSequenceCheckpointRefused("retained conflict history changed")


class RollbackSequenceCheckpoint:
    """Storage composition, not a wallet approval or live restart dispatcher.

    Caller captures through the original writer boundary. This adapter validates
    detached bytes and retains progress while the existing complete-snapshot
    adapter and original store retain their generation CAS and durability rules.
    It does not select a database, restore sessions, reconcile a native journal,
    advance a hop, refund money or retry a commit with unknown outcome.
    """

    def __init__(self, checkpoint):
        if type(checkpoint) is not ExchangeSnapshotCheckpoint:
            raise RollbackSequenceCheckpointRefused("original complete snapshot adapter required")
        self.checkpoint = checkpoint

    def read(self, scope):
        row = self.checkpoint.read(scope)
        if row is None:
            return None
        _sequences(row["facts"])
        return row

    def save(self, scope, snapshot_bytes, *, expected_generation):
        candidate = _sequences(decode_exchange_snapshot(snapshot_bytes))
        previous = self.read(scope)
        if previous is not None:
            _retain(_sequences(previous["facts"]), candidate)
        # Never replace the caller's expected generation with this preflight
        # read. An intervening writer is refused by the same original CAS.
        return self.checkpoint.save(scope, snapshot_bytes, expected_generation=expected_generation)
