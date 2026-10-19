"""Persist original late conflict observations without changing closed returns."""
from copy import deepcopy
from dataclasses import replace

from .exchange_fact_snapshot import decode_exchange_snapshot
from .exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint, ExchangeCheckpointRefused, _continuity


def _conflict_continuity(previous, candidate):
    """Permit only the two original append-only conflict projections to grow."""
    domain = dict(candidate.domain)
    histories = dict(domain["_rollback_history"])
    for receipt_id, prior_history in previous.domain["_rollback_history"].items():
        current_history = histories.get(receipt_id)
        if (type(prior_history) is not list or type(current_history) is not list
                or len(current_history) < len(prior_history)):
            raise ExchangeCheckpointRefused("closed rollback history prefix disappeared")
        normalized = list(current_history)
        for index, old in enumerate(prior_history):
            current = current_history[index]
            if current == old:
                continue
            if (type(old) is not dict or type(current) is not dict
                    or set(old) != set(current)
                    or type(old.get("state")) is not dict
                    or type(current.get("state")) is not dict
                    or type(old.get("report")) is not dict
                    or type(current.get("report")) is not dict):
                raise ExchangeCheckpointRefused("original closed archive shape differs")
            before = old["state"].get("conflicts")
            after = current["state"].get("conflicts")
            if (old["state"].get("state") != "complete"
                    or current["state"].get("state") != "complete"
                    or type(before) is not list or type(after) is not list
                    or after[:len(before)] != before
                    or old["report"].get("conflicts") != tuple(before)
                    or current["report"].get("conflicts") != tuple(after)):
                raise ExchangeCheckpointRefused("original closed conflict observations differ")
            cleaned = deepcopy(current)
            cleaned["state"]["conflicts"] = deepcopy(before)
            cleaned["report"]["conflicts"] = tuple(deepcopy(before))
            if cleaned != old:
                raise ExchangeCheckpointRefused("closed history changed outside conflict append")
            normalized[index] = old
        histories[receipt_id] = normalized
    domain["_rollback_history"] = histories
    # Reuse every other original continuity rule, including events, nonce,
    # signed terms, mint uniqueness and applied-result identity retention.
    _continuity(previous, replace(candidate, domain=domain))


class ClosedRollbackConflictCheckpoint(ExchangeSnapshotCheckpoint):
    """Original store and CAS with a narrow late-observation continuity rule.

    No state migration, controller calls, sequence reopening or operation replay
    occurs here. This adapter is a separate composition choice; existing generic
    snapshot adapters are not modified by its presence.
    """

    def save(self, scope, snapshot_bytes, *, expected_generation):
        if (type(expected_generation) is not int
                or not 0 <= expected_generation < 2 ** 63 - 1
                or type(snapshot_bytes) is not bytes):
            raise ExchangeCheckpointRefused("exact snapshot bytes and bounded generation required")
        candidate = decode_exchange_snapshot(snapshot_bytes)
        previous = self.read(scope)
        actual = previous["generation"] if previous is not None else 0
        if actual != expected_generation:
            raise ExchangeCheckpointRefused("preflight belongs to another generation")
        if previous is not None:
            _conflict_continuity(previous["facts"], candidate)
        result = self.store.save(scope, {"owned-facts": snapshot_bytes},
                                 expected_generation=expected_generation)
        return {**result, "executionAuthorized": False, "completeRecovery": False}
