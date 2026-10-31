"""Explicit production composition; capabilities belong to the trusted host.

This module supplies no authority, credential, login, database initialization or
network fallback. Runtime callbacks are process-owned inputs, never JSON/HTTP
module names or self-declared verification flags. Missing inputs remain UNBOUND.
"""
from copy import deepcopy
from dataclasses import dataclass, fields, replace
import inspect
import json
from pathlib import PurePosixPath
import re
from urllib.parse import urlsplit

from .aggregate_checkpoint import AggregateCheckpointStore
from .cross_product_composition import compose_cross_product_service
from .deferred_runtime_composition import OriginalDeferredPorts
from .exchange_fact_snapshot import decode_exchange_snapshot, encode_exchange_snapshot
from .errors import DomainError
from .ledger import Exchange
from .model import AuthorizationReference
from .linked_operation_controller import OriginalLinkedCaller, LinkedOperationController
from .oracle_admission_evidence import OracleAdmissionEvidenceClient
from .original_task_journal_reader import OriginalTaskJournalReader
from .original_task_journal_wire import OriginalTaskJournalWire, PATH
from .service_runtime import validate_binding
from .wallet_api_client import WalletAPIClient
from .wallet_execution_attempts import WalletExecutionAttempts
from .wallet_v3_composition import WalletV3Connection


class ProductionHostRefused(ValueError):
    pass


class ProductionHostUnbound(ProductionHostRefused):
    def __init__(self, names):
        self.names = tuple(names)
        super().__init__('EX_PRODUCTION_HOST_UNBOUND:' + ','.join(self.names))


def _require(value, reason):
    if not value:
        raise ProductionHostRefused('EX_PRODUCTION_HOST_' + reason)


def _exact(value, keys):
    return type(value) is dict and set(value) == set(keys)


def _hex(value, size):
    return type(value) is str and re.fullmatch('[0-9a-f]{%d}' % size, value) is not None


def _identity(value):
    return type(value) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', value) is not None


@dataclass(frozen=True)
class AggregateBinding:
    scope: str
    components: tuple
    source_commit: str
    source_tree: str

    def __post_init__(self):
        _require(_identity(self.scope) and type(self.components) is tuple
                 and all(type(x) is str and re.fullmatch('[a-z][a-z0-9_-]{0,63}', x) for x in self.components)
                 and self.components == tuple(sorted(set(self.components))) and len(self.components) <= 64
                 and {'owned-facts', 'deferred-settlement'} <= set(self.components)
                 and _hex(self.source_commit, 40) and _hex(self.source_tree, 40), 'AGGREGATE_BINDING_REFUSED')

    def read(self, store):
        _require(type(store) is AggregateCheckpointStore
                 and store.components == self.components
                 and store.source == {'commit': self.source_commit, 'tree': self.source_tree}, 'STORE_PROVENANCE_REFUSED')
        row = store.read(self.scope)
        _require(row is not None, 'CHECKPOINT_MISSING')
        _require(_exact(row, ('scope', 'generation', 'components', 'digest', 'executionAuthorized'))
                 and row['scope'] == self.scope and type(row['generation']) is int
                 and row['generation'] >= 1 and _hex(row['digest'], 64)
                 and type(row['components']) is dict and set(row['components']) == set(self.components)
                 and all(type(x) is bytes for x in row['components'].values())
                 and row['executionAuthorized'] is False, 'CHECKPOINT_REFUSED')
        return row

    def match(self, store, supplied):
        current = self.read(store)
        _require(type(supplied) is dict and supplied == current, 'CHECKPOINT_CHANGED')
        return current


@dataclass(frozen=True)
class CurrentAuthorityContext:
    scope: str
    generation: int
    digest: str
    source_commit: str
    source_tree: str
    authorization_ids: tuple


@dataclass(frozen=True)
class RuntimeCapabilities:
    clock: object
    payment_adapter: object
    asset_control: object
    registrars: object
    voucher_desk: object
    eth_gas_gate: object
    price_balance_gate: object
    priority_store: object
    release_sources: tuple
    rollback_sources: tuple
    funding_required: bool
    read_current_sessions: object
    read_current_authorizations: object
    read_current_gas_budgets: object

    def check(self):
        callbacks = ('clock', 'read_current_sessions', 'read_current_authorizations', 'read_current_gas_budgets')
        missing = [name for name in callbacks if not callable(getattr(self, name))]
        missing += [name for name in ('payment_adapter', 'asset_control', 'registrars',
            'voucher_desk', 'eth_gas_gate', 'price_balance_gate', 'priority_store') if getattr(self, name) is None]
        if missing:
            raise ProductionHostUnbound(missing)
        _require(type(self.funding_required) is bool, 'FUNDING_POLICY_REFUSED')
        for sources in (self.release_sources, self.rollback_sources):
            _require(type(sources) is tuple and all(_identity(x) for x in sources)
                     and len(set(sources)) == len(sources), 'AUTHORITY_SOURCES_REFUSED')


class OriginalRuntimeFactory:
    """Construct a fresh Exchange from actual configured ports, not a clone.

    Saved grants remain references for the original rehydrator. Sessions and
    current authorizations ONLY come from live host-owned readers. This factory
    never restores snapshot sessions, dispatches, or mutates the checkpoint.
    """
    def __init__(self, store, binding, capabilities):
        _require(type(binding) is AggregateBinding and type(capabilities) is RuntimeCapabilities, 'RUNTIME_INPUT_REFUSED')
        capabilities.check()
        self.store, self.binding, self.capabilities = store, binding, capabilities

    def __call__(self, row, *, mint_verifier):
        _require(callable(mint_verifier), 'MINT_VERIFIER_REFUSED')
        c, binding = self.capabilities, self.binding
        c.check()
        captured = binding.match(self.store, row)
        facts = decode_exchange_snapshot(captured['components']['owned-facts'])
        original = {ref.authorization_id: ref for ref in facts.wallet['authorizations']}
        context = CurrentAuthorityContext(binding.scope, captured['generation'], captured['digest'],
                                          binding.source_commit, binding.source_tree, tuple(sorted(original)))
        try:
            sessions = c.read_current_sessions(context)
            authorizations = c.read_current_authorizations(context)
            budgets = c.read_current_gas_budgets(context)
        except Exception:
            raise ProductionHostRefused('EX_PRODUCTION_HOST_CURRENT_AUTHORITY_UNAVAILABLE') from None
        _require(type(sessions) is dict and type(authorizations) in (tuple, list)
                 and type(budgets) is dict, 'CURRENT_AUTHORITY_REFUSED')
        sessions, authorizations, budgets = dict(sessions), tuple(authorizations), dict(budgets)
        _require(all(type(ref) is AuthorizationReference for ref in authorizations), 'CURRENT_AUTHORIZATION_TYPE_REFUSED')
        current = {ref.authorization_id: ref for ref in authorizations}
        _require(len(current) == len(authorizations), 'DUPLICATE_AUTHORIZATION_REFUSED')
        # Saved grants are references, not proof they remain valid. Omission
        # must never let the rehydrator resurrect a revoked/unknown old grant.
        _require(set(original) <= set(current), 'CURRENT_AUTHORIZATION_COVERAGE_REFUSED')
        for identity, prior in original.items():
            observed = current[identity]
            _require(not prior.revoked or observed.revoked, 'AUTHORIZATION_REVOCATION_REFUSED')
            _require(replace(observed, revoked=prior.revoked) == prior, 'AUTHORIZATION_CONSTRAINTS_REFUSED')
        binding.match(self.store, captured)
        runtime = Exchange(c.clock, payment_adapter=c.payment_adapter, asset_control=c.asset_control,
            release_sources=c.release_sources, rollback_sources=c.rollback_sources,
            funding_required=c.funding_required, gas_budgets=budgets, voucher_desk=c.voucher_desk,
            mint_verifier=mint_verifier, eth_gas_gate=c.eth_gas_gate,
            price_balance_gate=c.price_balance_gate, priority_store=c.priority_store)
        runtime.registrars = c.registrars
        for account, session in sessions.items():
            runtime.connect_wallet(account, session)
        for authorization in authorizations:
            runtime.register_authorization(authorization)
        _require(type(runtime) is Exchange and runtime._mint_book is not None
                 and runtime._mint_book.verify is mint_verifier, 'MINT_VERIFIER_IDENTITY_REFUSED')
        encode_exchange_snapshot(runtime)
        binding.match(self.store, captured)
        return runtime


@dataclass(frozen=True)
class NativeAuthorityPorts:
    read_admission: object
    verify_admission: object
    read_rollback_authority: object
    verify_terminal: object
    resolve_native_task: object
    verify_prepared_cancel: object

    def check(self):
        missing = [f.name for f in fields(self) if not callable(getattr(self, f.name))]
        if missing:
            raise ProductionHostUnbound(missing)


class ScopedCaller:
    """Scope guard around the existing authenticated-caller capability.

    The authenticator must verify the real request each time. This is not an
    authentication scheme, identity issuer, service-login fallback or HTTP flag.
    """
    def __init__(self, authenticate, *, scope, receipt_id, tenant, account):
        if not callable(authenticate):
            raise ProductionHostUnbound(('authenticate_caller',))
        self.authenticate = authenticate
        self.expected = (scope, receipt_id, tenant, account.lower())

    def __call__(self, request):
        try:
            caller = self.authenticate(request)
        except Exception:
            raise ProductionHostRefused('EX_PRODUCTION_HOST_CALLER_UNAVAILABLE') from None
        _require(type(caller) is OriginalLinkedCaller
                 and (caller.scope, caller.receipt_id, caller.tenant, caller.account) == self.expected
                 and type(caller.allowed_actions) is frozenset
                 and caller.allowed_actions <= LinkedOperationController.ACTIONS, 'CALLER_REFUSED')
        return caller


def _https_origin(value):
    if type(value) is not str or any(c.isspace() or ord(c) < 32 for c in value):
        return False
    try:
        u = urlsplit(value)
        return (u.scheme == 'https' and bool(u.hostname) and not u.username and not u.password
                and not u.path and not u.query and not u.fragment and u.port != 0)
    except ValueError:
        return False


def validate_production_configuration(value):
    # Reject arbitrary objects/getters before copying. Only operator JSON data.
    def json_value(v, depth=0):
        _require(depth <= 12, 'CONFIGURATION_REFUSED')
        if type(v) in (str, int, bool) or v is None:
            return
        if type(v) is list:
            for x in v:
                json_value(x, depth + 1)
            return
        _require(type(v) is dict and all(type(k) is str for k in v), 'CONFIGURATION_REFUSED')
        for x in v.values():
            json_value(x, depth + 1)
    json_value(value)
    _require(_exact(value, ('schema', 'source', 'aggregate', 'receiptId', 'wallet', 'journal', 'oracle', 'executionMode', 'service'))
             and value['schema'] == '8415ex-production-host/1', 'CONFIGURATION_REFUSED')
    c = deepcopy(value)
    _require(_exact(c['source'], ('commit', 'tree')) and all(_hex(x, 40) for x in c['source'].values()), 'SOURCE_REFUSED')
    a = c['aggregate']
    _require(_exact(a, ('scope', 'components', 'sourceCommit', 'sourceTree', 'generation', 'digest'))
             and type(a['components']) is list and all(type(x) is str for x in a['components'])
             and type(a['generation']) is int and 1 <= a['generation'] < 2**63 and _hex(a['digest'], 64), 'AGGREGATE_CONFIGURATION_REFUSED')
    AggregateBinding(a['scope'], tuple(a['components']), a['sourceCommit'], a['sourceTree'])
    _require(_identity(c['receiptId']) and c['executionMode'] in ('observe-only', 'native-enabled'), 'EXECUTION_CONFIGURATION_REFUSED')
    w = c['wallet']
    _require(_exact(w, ('origin', 'tenant', 'account', 'basePath', 'attemptPath')) and _https_origin(w['origin']), 'WALLET_CONFIGURATION_REFUSED')
    _require(type(w['attemptPath']) is str and str(PurePosixPath(w['attemptPath'])) == w['attemptPath']
             and PurePosixPath(w['attemptPath']).is_absolute() and '..' not in PurePosixPath(w['attemptPath']).parts, 'ATTEMPT_PATH_REFUSED')
    # Original client validation only; construction does not log in or request.
    try:
        WalletAPIClient(w['origin'], w['tenant'], w['account'], 11155111, base_path=w['basePath'])
    except (ValueError, DomainError):
        raise ProductionHostRefused('EX_PRODUCTION_HOST_WALLET_CONFIGURATION_REFUSED') from None
    w['account'] = w['account'].lower()
    j = c['journal']
    _require(_exact(j, ('endpoint', 'peerId')) and type(j['endpoint']) is str
             and type(j['peerId']) is str and 0 < len(j['peerId']) <= 256, 'JOURNAL_CONFIGURATION_REFUSED')
    try:
        u = urlsplit(j['endpoint'])
        _require(u.path == PATH and not u.username and not u.password and not u.query and not u.fragment
                 and _https_origin('https://' + u.netloc), 'JOURNAL_CONFIGURATION_REFUSED')
        _require(u.scheme == 'https', 'JOURNAL_CONFIGURATION_REFUSED')
    except ValueError:
        raise ProductionHostRefused('EX_PRODUCTION_HOST_JOURNAL_CONFIGURATION_REFUSED') from None
    o = c['oracle']
    _require(_exact(o, ('origin', 'source', 'finalityPolicy')) and _https_origin(o['origin']), 'ORACLE_CONFIGURATION_REFUSED')
    try:
        OracleAdmissionEvidenceClient(o['origin'], o['source'], finality_policy=o['finalityPolicy'])
    except (ValueError, DomainError):
        raise ProductionHostRefused('EX_PRODUCTION_HOST_ORACLE_CONFIGURATION_REFUSED') from None
    _require(o['source']['chainId'] == '11155111', 'ORACLE_SETTLEMENT_CHAIN_REFUSED')
    _require(_exact(c['service'], ('port',)) and type(c['service']['port']) is int
             and 1 <= c['service']['port'] <= 65535, 'SERVICE_CONFIGURATION_REFUSED')
    return c


def parse_production_configuration(raw):
    _require(type(raw) is bytes and len(raw) <= 65536, 'CONFIGURATION_REFUSED')
    def unique(pairs):
        d = {}
        for k, v in pairs:
            _require(k not in d, 'DUPLICATE_CONFIGURATION_KEY')
            d[k] = v
        return d
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise ProductionHostRefused('EX_PRODUCTION_HOST_CONFIGURATION_REFUSED') from None
    return validate_production_configuration(value)


def compose_production_service(configuration, *, store, runtime_capabilities,
        native_authority, deferred_profile, deferred_verifier, original_mint_verifier,
        authenticate_caller, journal_transport, with_journal_capability,
        gas_page, registration_sources, features=None):
    """Compose the existing real service without binding HTTP or initializing DBs.

    External ports must already carry their original authority. Callable shape
    and source hashes are not proof of identity, truth or deployment admission.
    This function does not mint credentials/grants, log in, replay, or activate.
    """
    c = validate_production_configuration(configuration)
    _require(type(runtime_capabilities) is RuntimeCapabilities and type(native_authority) is NativeAuthorityPorts, 'CAPABILITY_TYPE_REFUSED')
    runtime_capabilities.check()
    native_authority.check()
    required = {'original_mint_verifier': original_mint_verifier, 'authenticate_caller': authenticate_caller,
                'journal_transport': journal_transport, 'with_journal_capability': with_journal_capability}
    missing = [k for k, v in required.items() if not callable(v)]
    verify = inspect.getattr_static(deferred_verifier, 'verify', None)
    if isinstance(verify, property) or not callable(verify):
        missing.append('deferred_verifier')
    if gas_page is None:
        missing.append('gas_page')
    if registration_sources is None:
        missing.append('registration_sources')
    if missing:
        raise ProductionHostUnbound(missing)
    a = c['aggregate']
    pin = AggregateBinding(a['scope'], tuple(a['components']), a['sourceCommit'], a['sourceTree'])
    row = pin.read(store)
    _require(row['generation'] == a['generation'] and row['digest'] == a['digest'], 'CHECKPOINT_CHANGED')
    _require(c['receiptId'] in decode_exchange_snapshot(row['components']['owned-facts']).receipts, 'RECEIPT_MISSING')
    _require(getattr(deferred_profile, 'checkpoint_scope', None) == pin.scope, 'PROFILE_SCOPE_REFUSED')
    allowed_features = {'principal_component', 'principal_allocator', 'verify_staged_allocation',
        'original_task_proposal', 'original_task_configuration', 'original_economic_configuration',
        'original_asset_return_configuration', 'original_recovery_proofs'}
    features = {} if features is None else dict(features) if type(features) is dict else None
    _require(type(features) is dict and set(features) <= allowed_features, 'FEATURE_CONFIGURATION_REFUSED')
    factory = OriginalRuntimeFactory(store, pin, runtime_capabilities)
    # PR244: an observation/host startup must never create a fresh attempt DB.
    attempts = WalletExecutionAttempts.open_existing(c['wallet']['attemptPath'])
    w = c['wallet']
    connection = WalletV3Connection(w['origin'], w['tenant'], w['account'], w['basePath'], attempts)
    j = c['journal']
    wire = OriginalTaskJournalWire(endpoint=j['endpoint'], peer_id=j['peerId'],
        transport=journal_transport, with_capability=with_journal_capability)
    journal = OriginalTaskJournalReader(wire)
    caller = ScopedCaller(authenticate_caller, scope=pin.scope, receipt_id=c['receiptId'],
                          tenant=w['tenant'], account=w['account'])
    ports = OriginalDeferredPorts(factory, factory, native_authority.read_admission,
        native_authority.verify_admission, None, native_authority.read_rollback_authority,
        native_authority.verify_terminal, native_authority.resolve_native_task,
        native_authority.verify_prepared_cancel)
    binding = compose_cross_product_service(store=store, scope=pin.scope,
        expected_components=pin.components, expected_generation=a['generation'], expected_digest=a['digest'],
        profile=deferred_profile, deferred_verifier=deferred_verifier,
        original_mint_verifier=original_mint_verifier, create_original_runtime=factory, ports=ports,
        original_journal=journal, oracle_origin=c['oracle']['origin'], oracle_source=c['oracle']['source'],
        finality_policy=c['oracle']['finalityPolicy'], settlement=connection, collateral=connection,
        execution_mode=c['executionMode'], receipt_id=c['receiptId'], authenticate_caller=caller,
        service_options={'gas_page': gas_page, 'registration_sources': registration_sources,
            'current_time': runtime_capabilities.clock, 'commit': c['source']['commit'],
            'tree': c['source']['tree'], 'port': c['service']['port']}, **features)
    pin.match(store, row)
    validate_binding(binding, commit=c['source']['commit'], tree=c['source']['tree'])
    return binding
