"""Compose existing deferred/owned recovery against one original physical row.

No schema, state, Wallet grant, task binding or proof authority is created.
Pure callback implementations remain explicitly owned by the original host.
"""
from dataclasses import dataclass
import inspect
from .aggregate_checkpoint import AggregateCheckpointStore
from .deferred_checkpoint import DeferredCheckpoint
from .deferred_owned_transition import DeferredOwnedTransition
from .deferred_wallet_ports import DeferredWalletPorts
from .exchange_fact_snapshot import decode_exchange_snapshot
from .joint_deferred_transition import JointDeferredTransition, JointTransitionInput, OriginalLegBinding
from .mixed_suffix_recovery import MixedSuffixRecovery


class DeferredCompositionRefused(ValueError):
    pass


def resolve_owned_leg(context):
    """Derive an occurrence only from the exact coordinator-read original bytes.

    This is not registration/payment authority. The coordinator independently
    validates the returned leg against its deferred model and original digest.
    """
    if type(context) is not JointTransitionInput:
        raise DeferredCompositionRefused('original joint transition context required')
    facts = decode_exchange_snapshot(context.owned_before)
    matches = [(receipt, leg) for receipt, legs in facts.domain['_legs'].items()
               for leg in legs if leg.deferred_obligation_id == context.obligation_id]
    if len(matches) != 1:
        raise DeferredCompositionRefused('original obligation must identify exactly one owned occurrence')
    receipt, leg = matches[0]
    return OriginalLegBinding(context.aggregate_digest, context.obligation_id,
                              receipt, leg.leg_index, leg.transfer_id)


@dataclass(frozen=True)
class OriginalDeferredPorts:
    fresh_readonly_runtime: object
    fresh_recovery_runtime: object
    read_admission: object
    verify_admission: object
    read_registration: object
    read_rollback_authority: object
    verify_terminal: object
    resolve_native_task: object
    verify_prepared_cancel: object


@dataclass(frozen=True)
class DeferredRuntime:
    checkpoint: DeferredCheckpoint
    owned_transition: DeferredOwnedTransition
    joint: JointDeferredTransition
    recovery: MixedSuffixRecovery
    wallet: DeferredWalletPorts
    generation: int
    digest: str
    principal_allocation_configured: bool


def compose_deferred_runtime(store, scope, profile, verifier, *, ports,
        settlement_client, collateral_client, expected_generation, expected_digest,
        principal_component=None, principal_allocator=None, verify_staged_allocation=None):
    if type(ports) is not OriginalDeferredPorts or not all(callable(getattr(ports,name))
            for name in OriginalDeferredPorts.__dataclass_fields__):
        raise DeferredCompositionRefused('all original authority and native reader ports required')
    if type(expected_generation) is not int or expected_generation < 1:
        raise DeferredCompositionRefused('exact original generation required')
    supplied = (principal_component is not None, principal_allocator is not None,
                verify_staged_allocation is not None)
    if any(supplied) and (not all(supplied) or not callable(verify_staged_allocation)):
        raise DeferredCompositionRefused('principal allocation ports must be supplied together')
    # Do not run descriptor getters merely to discover a native capability.
    # The physical store is the existing concrete implementation, not an
    # arbitrary reader supplied through a property or a projected generation.
    if type(store) is not AggregateCheckpointStore:
        raise DeferredCompositionRefused('original concrete physical aggregate store required')
    verify_method = inspect.getattr_static(verifier, 'verify', None)
    if isinstance(verify_method, property) or not callable(verify_method):
        raise DeferredCompositionRefused('explicit verifier method required without descriptor discovery')
    for client in (settlement_client, collateral_client):
        for name in ('_chain', '_execution_attempts'):
            if isinstance(inspect.getattr_static(client, name, None), property):
                raise DeferredCompositionRefused('native client descriptor discovery refused')
    checkpoint = DeferredCheckpoint(store, scope, profile, verifier)
    row, _ = checkpoint.read()
    if row['generation'] != expected_generation or row['digest'] != expected_digest:
        raise DeferredCompositionRefused('original aggregate changed')
    if 'owned-facts' not in store.components:
        raise DeferredCompositionRefused('original owned-facts component required')
    decode_exchange_snapshot(row['components']['owned-facts'])
    owned = DeferredOwnedTransition(profile, verifier,
        fresh_readonly_runtime=ports.fresh_readonly_runtime,
        read_admission=ports.read_admission, verify_admission=ports.verify_admission,
        read_registration=ports.read_registration, read_rollback_authority=ports.read_rollback_authority)
    joint = JointDeferredTransition(checkpoint, resolve_original_binding=resolve_owned_leg,
        transition_owned_facts=owned.transition_owned_facts, transition_admission=owned.transition_admission,
        principal_component=principal_component, principal_allocator=principal_allocator,
        verify_staged_allocation=verify_staged_allocation, verify_prepared_cancel=ports.verify_prepared_cancel)
    recovery = MixedSuffixRecovery(checkpoint, fresh_readonly_runtime=ports.fresh_recovery_runtime,
                                   verify_terminal=ports.verify_terminal)
    wallet = DeferredWalletPorts(profile, settlement_client, collateral_client, ports.resolve_native_task)
    return DeferredRuntime(checkpoint, owned, joint, recovery, wallet, row['generation'],row['digest'],all(supplied))
