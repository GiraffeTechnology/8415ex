"""Explicit same-aggregate EX / Wallet V3 / Oracle composition.

This is the original host's assembly entry, not an initializer or a second
service. Original store, native task journal, evidence authorities and caller
authentication remain explicit. Construction never logs in or dispatches.
"""
from dataclasses import replace
from .wallet_task_preparation import WalletTaskPreparation
from .wallet_dispatch_fence import WalletDispatchFence
from .original_deferred_proposal_source import OriginalDeferredProposalSource
from .ledger import Exchange
from .joint_deferred_transition import JointTransitionInput
from .oracle_admission_evidence import OracleAdmissionEvidenceClient
from .oracle_registration_mapping import OracleRegistrationMapping
from .oracle_registration_reader import OracleRegistrationReader
from .wallet_v3_composition import compose_wallet_v3_deferred_runtime
from .linked_checkpoint_view import LinkedCheckpointView
from .linked_operation_controller import LinkedOperationController
from .mixed_suffix_recovery import MixedSuffixRecovery
from .linked_recovery_workflow import LinkedRecoveryWorkflow
from .service_runtime import LinkedOriginalServiceBinding


def original_runtime_row(store, scope, context):
    """Normalize original coordinator inputs without dropping any component."""
    row = store.read(scope)
    if row is None:
        raise ValueError('original aggregate unavailable')
    if type(context) is JointTransitionInput:
        matches = (context.source_commit == store.source['commit'] and context.source_tree == store.source['tree']
            and context.deferred_before == row['components']['deferred-settlement']
            and context.scope == scope and context.generation == row['generation']
            and context.aggregate_digest == row['digest']
            and context.owned_before == row['components']['owned-facts'])
    elif type(context) is dict:
        matches = (context.get('scope') == scope and context.get('generation') == row['generation']
            and context.get('digest') == row['digest'] and context.get('components') == row['components'])
    else:
        matches = False
    if not matches:
        raise ValueError('fresh runtime context differs from original aggregate')
    return row


def compose_cross_product_service(*, store, scope, expected_components,
        expected_generation, expected_digest, profile, deferred_verifier,
        original_mint_verifier, create_original_runtime, ports, original_journal,
        oracle_origin, oracle_source, finality_policy, settlement, collateral,
        execution_mode, receipt_id, authenticate_caller, service_options,
        principal_component=None, principal_allocator=None, verify_staged_allocation=None, original_task_proposal=None, original_task_configuration=None, original_economic_configuration=None, original_asset_return_configuration=None, original_recovery_proofs=None):
    """Assemble the concrete readers/coordinators and existing HTTP lifecycle.

    create_original_runtime(context, mint_verifier=...) creates a detached
    original Exchange with the same original registrar/Wallet authorities. Its
    exact mint verifier is checked, so merely returning an old unwired runtime
    cannot silently omit the canonical Oracle evidence check.
    """
    if not callable(create_original_runtime) or not callable(original_mint_verifier):
        raise ValueError('original fresh runtime constructor and mint authority required')
    view = LinkedCheckpointView(store, expected_components=expected_components)
    evidence = OracleAdmissionEvidenceClient(oracle_origin, oracle_source,
                                             finality_policy=finality_policy)
    # These closures are inert during construction. The mapping is assigned
    # before any original-runtime constructor is invoked.
    def fresh(context):
        row = original_runtime_row(store, scope, context)
        runtime = create_original_runtime(row, mint_verifier=mint_verifier)
        if (type(runtime) is not Exchange or runtime._mint_book is None
                or runtime._mint_book.verify is not mint_verifier):
            raise ValueError('original runtime must install the exact linked mint verifier')
        return runtime
    mapping = OracleRegistrationMapping(store, scope, journal=original_journal,
                                       client=evidence, fresh_runtime=fresh)
    mint_verifier = mapping.mint_verifier(original_mint_verifier)
    projection_source = {'chainId':oracle_source['chainId'],
        'contract':oracle_source['projectionContract'], 'registerId':oracle_source['registerId']}
    reader = OracleRegistrationReader.from_http(origin=oracle_origin, source=projection_source,
        verify_mapping=mapping.verify_mapping, resolve_original=mapping.resolve_original)
    linked_ports = reader.install(replace(ports, fresh_readonly_runtime=fresh, fresh_recovery_runtime=fresh))
    linked = compose_wallet_v3_deferred_runtime(store, scope, profile, deferred_verifier,
        ports=linked_ports, settlement=settlement, collateral=collateral,
        execution_mode=execution_mode, expected_generation=expected_generation,
        expected_digest=expected_digest, principal_component=principal_component,
        principal_allocator=principal_allocator, verify_staged_allocation=verify_staged_allocation)
    if original_task_configuration is not None:
        if original_task_proposal is not None or type(original_task_configuration) is not dict or set(original_task_configuration) != {'records','asset','custody'}:
            raise ValueError('one exact original native configuration required')
        original_task_proposal = OriginalDeferredProposalSource(linked.runtime.checkpoint,linked.settlement,
            receipt_id=receipt_id,original_records=original_task_configuration['records'],
            asset_binding=original_task_configuration['asset'],custody_binding=original_task_configuration['custody'])
    preparation = None if original_task_proposal is None else WalletTaskPreparation(
        store, scope, linked.settlement, original_task_proposal, receipt_id=receipt_id)
    if preparation is not None:
        # The concrete original proposal source now supplies reserved native
        # identity through existing DeferredWalletPorts funding checks.
        prior_native_source = linked.runtime.wallet.resolve_original
        def native_source(operation):
            if preparation.owns_operation(operation):
                return preparation.native_binding(operation)
            return prior_native_source(operation)
        linked.runtime.wallet.resolve_original = native_source
        preparation.fence = WalletDispatchFence(preparation, linked.runtime.checkpoint, now=service_options['current_time'], original_ports=linked.runtime.wallet)
    economic = None
    if original_economic_configuration is not None:
        from .direct_erc20_observation import DirectERC20Observation
        from .direct_terminal_verifier import DirectTerminalVerifier
        cfg = original_economic_configuration
        if (preparation is None or type(cfg) is not dict or set(cfg) not in (
                {'rpc','token_pin','finality_policy','executor_binding','approved_profile'},
                {'rpc','token_pin','finality_policy','executor_binding','approved_profile','proxy_binding'})):
            raise ValueError('explicit original economic reader configuration required')
        observer = DirectERC20Observation(linked.runtime.checkpoint, preparation, cfg['rpc'],
            token_pin=cfg['token_pin'], finality_policy=cfg['finality_policy'], executor_binding=cfg['executor_binding'], proxy_binding=cfg.get('proxy_binding'))
        economic = DirectTerminalVerifier(observer, linked.runtime.checkpoint.verifier,
            approved_profile=cfg['approved_profile'])
        linked.runtime.checkpoint.verifier = economic
    def unbound_terminal(*args):
        raise ValueError('original production terminal verifier UNBOUND')
    recovery_core = MixedSuffixRecovery(linked.runtime.checkpoint,
        fresh_readonly_runtime=mapping.fresh_runtime, verify_terminal=unbound_terminal)
    asset_return = None
    if original_asset_return_configuration is not None:
        from .asset_return_observation import AssetReturnObservation
        from .mixed_asset_return import MixedAssetReturn
        cfg = original_asset_return_configuration
        if preparation is None or type(cfg) is not dict or set(cfg) != {'records','rpc','approved_profile','executor_binding'}:
            raise ValueError('explicit original asset source configuration required')
        observation = AssetReturnObservation(cfg['rpc'],cfg['approved_profile'],executor_binding=cfg['executor_binding'])
        asset_return = MixedAssetReturn(recovery_core,linked.settlement,receipt_id=receipt_id,
            original_records=cfg['records'],observation=observation,now=service_options['current_time'])
        recovery_core.verify_terminal = asset_return.verify_terminal
        preparation.fence.install_asset_return(asset_return)
    native_preparation = None
    if original_recovery_proofs is not None:
        from .native_recovery_preparation import NativeRecoveryPreparation
        native_preparation = NativeRecoveryPreparation(recovery_core, receipt_id,
            proofs=original_recovery_proofs, original_verifier=linked.runtime.checkpoint.verifier)
    recovery = LinkedRecoveryWorkflow(recovery_core,receipt_id,economic_verifier=economic,
        asset_verifier=asset_return,native_preparation=native_preparation)
    controller = LinkedOperationController(linked, mapping, receipt_id=receipt_id,
        authenticate=authenticate_caller, current_time=service_options['current_time'], task_preparation=preparation, recovery_workflow=recovery, economic_verifier=economic)
    row = view.read(scope)
    if row is None or row['generation'] != expected_generation or row['digest'] != expected_digest:
        raise ValueError('original aggregate changed during assembly')
    return LinkedOriginalServiceBinding(checkpoint=view, scope=scope, runtime=fresh(row),
        receipt_id=receipt_id, options=dict(service_options), expected_generation=expected_generation,
        expected_checkpoint_digest=expected_digest, expected_store_commit=store.source['commit'],
        expected_store_tree=store.source['tree'], linked_controller=controller,
        expected_components=expected_components)
