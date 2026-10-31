"""Foreground lifecycle for an explicitly supplied original runtime binding.

The binding is trusted host code, not data received from HTTP. This entry does
not choose providers, create credentials, initialize state, migrate generations,
replay operations or manage an external service.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import signal

from .exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint
from .ledger import Exchange
from .recovered_operation_observation import compose_recovered_operation_observation


class ServiceRefused(ValueError):
    pass


@dataclass(frozen=True)
class OriginalServiceBinding:
    checkpoint: ExchangeSnapshotCheckpoint
    scope: str
    runtime: Exchange
    receipt_id: str
    options: dict
    expected_generation: int
    expected_checkpoint_digest: str
    expected_store_commit: str
    expected_store_tree: str


@dataclass(frozen=True)
class LinkedOriginalServiceBinding(OriginalServiceBinding):
    linked_controller: object
    expected_components: tuple


def validate_binding(binding, *, commit, tree):
    from .linked_checkpoint_view import LinkedCheckpointView
    from .linked_operation_controller import LinkedOperationController
    if type(binding) not in (OriginalServiceBinding, LinkedOriginalServiceBinding):
        raise ServiceRefused('EX_SERVICE_BINDING_TYPE_REFUSED')
    if not all(type(v) is str and re.fullmatch('[0-9a-f]{40}', v) for v in (commit, tree)):
        raise ServiceRefused('EX_SERVICE_VERSION_REFUSED')
    if not isinstance(binding.checkpoint, ExchangeSnapshotCheckpoint) or type(binding.runtime) is not Exchange:
        raise ServiceRefused('EX_SERVICE_RUNTIME_REFUSED')
    if not all(type(v) is str and re.fullmatch('[0-9a-f]{40}', v) for v in
               (binding.expected_store_commit, binding.expected_store_tree)):
        raise ServiceRefused('EX_SERVICE_STORE_VERSION_REFUSED')
    if binding.checkpoint.store.source != {'commit': binding.expected_store_commit, 'tree': binding.expected_store_tree}:
        raise ServiceRefused('EX_SERVICE_STORE_VERSION_REFUSED')
    if type(binding) is LinkedOriginalServiceBinding:
        controller = binding.linked_controller
        if (type(binding.checkpoint) is not LinkedCheckpointView
                or binding.checkpoint.expected_components != binding.expected_components
                or type(controller) is not LinkedOperationController
                or controller.linked.runtime.checkpoint.store is not binding.checkpoint.store
                or controller.linked.runtime.checkpoint.scope != binding.scope
                or controller.mapping.store is not binding.checkpoint.store
                or controller.mapping.scope != binding.scope
                or controller.receipt_id != binding.receipt_id):
            raise ServiceRefused('EX_SERVICE_LINKED_BINDING_REFUSED')
        # Original single-component command adapters cannot save this full row.
        # Linked commands enter their explicit joint CAS ports instead.
        forbidden = {'remint_action', 'operation_observation', 'collateral_selection', 'scenario_selection'}
        if forbidden & set(binding.options):
            raise ServiceRefused('EX_SERVICE_LINKED_OPTIONS_REFUSED')
        for _, detail_options in binding.options.get('detail_receipts', ()):
            if detail_options.get('gateway') is not None:
                raise ServiceRefused('EX_SERVICE_LINKED_OPTIONS_REFUSED')
        if binding.options.get('runtime_options', {}).get('gateway') is not None:
            raise ServiceRefused('EX_SERVICE_LINKED_OPTIONS_REFUSED')
    elif isinstance(binding.checkpoint, LinkedCheckpointView):
        raise ServiceRefused('EX_SERVICE_LINKED_BINDING_REFUSED')
    options = binding.options
    if type(options) is not dict or options.get('commit') != commit or options.get('tree') != tree:
        raise ServiceRefused('EX_SERVICE_OPTIONS_VERSION_REFUSED')
    if type(options.get('port')) is not int or not 1 <= options['port'] <= 65535:
        raise ServiceRefused('EX_SERVICE_PORT_REFUSED')
    if type(binding.expected_generation) is not int or binding.expected_generation < 1:
        raise ServiceRefused('EX_SERVICE_GENERATION_REFUSED')
    if type(binding.expected_checkpoint_digest) is not str or not re.fullmatch('[0-9a-f]{64}', binding.expected_checkpoint_digest):
        raise ServiceRefused('EX_SERVICE_CHECKPOINT_DIGEST_REFUSED')
    try:
        row = binding.checkpoint.read(binding.scope)
    except Exception as error:
        raise ServiceRefused('EX_SERVICE_STORE_UNAVAILABLE') from error
    if row is None:
        raise ServiceRefused('EX_SERVICE_CHECKPOINT_MISSING')
    if row['generation'] != binding.expected_generation or row['digest'] != binding.expected_checkpoint_digest:
        raise ServiceRefused('EX_SERVICE_CHECKPOINT_CHANGED')
    from .checkpoint_runtime_load import load_exchange_checkpoint
    try:
        restored = load_exchange_checkpoint(binding.checkpoint, binding.scope, binding.runtime)
    except Exception as error:
        raise ServiceRefused('EX_SERVICE_RESTORE_REFUSED') from error
    if restored is None or restored.generation != binding.expected_generation or restored.digest != binding.expected_checkpoint_digest:
        raise ServiceRefused('EX_SERVICE_CHECKPOINT_CHANGED')
    required_options = {'gas_page', 'registration_sources', 'current_time', 'commit', 'tree', 'port'}
    if not required_options <= set(options) or not callable(options['current_time']):
        raise ServiceRefused('EX_SERVICE_OPTIONS_REFUSED')
    return {'status': 'CONFIGURATION_VALIDATED', 'sourceCommit': commit, 'sourceTree': tree,
            'generation': row['generation'], 'nativeAcceptance': 'NOT_VERIFIED'}


def prepare_service(binding, *, commit, tree):
    health = validate_binding(binding, commit=commit, tree=tree)
    loaded = compose_recovered_operation_observation(binding.checkpoint, binding.scope,
        binding.runtime, binding.receipt_id, **binding.options)
    # Detect an intervening generation change; a read is not a writer lease.
    if (loaded.checkpoint.generation != binding.expected_generation
            or loaded.checkpoint.digest != binding.expected_checkpoint_digest):
        loaded.server.server_close()
        raise ServiceRefused('EX_SERVICE_CHECKPOINT_CHANGED')
    if type(binding) is LinkedOriginalServiceBinding:
        from .linked_operation_workbench import mount_linked_operations
        try:
            mount_linked_operations(loaded.server, binding.linked_controller)
        except Exception:
            loaded.server.server_close()
            raise
        health['linkedExecutionMode'] = binding.linked_controller.linked.execution_mode
        health['publicNativeAccess'] = 'NOT_ENABLED'
    return loaded, health


def run_service(binding, *, commit, tree):
    loaded, health = prepare_service(binding, commit=commit, tree=tree)
    previous = signal.getsignal(signal.SIGTERM)
    def terminate(*_):
        raise KeyboardInterrupt
    try:
        signal.signal(signal.SIGTERM, terminate)
        print(json.dumps(health, sort_keys=True), flush=True)
        loaded.server.serve_forever()
    finally:
        signal.signal(signal.SIGTERM, previous)
        loaded.server.server_close()


def load_host(config_path):
    """Load only the operator's explicitly pinned and separately approved host.

    A matching hash proves bytes, not that host code is safe or authorized.
    No template host or synthetic fallback is substituted for a missing one.
    """
    config = json.loads(Path(config_path).read_text())
    if type(config) is not dict or set(config) != {'schema','hostPath','hostSha256','commit','tree'} or config['schema'] != '8415ex-host/1':
        raise ServiceRefused('EX_SERVICE_CONFIG_REFUSED')
    for key, size in (('hostSha256',64),('commit',40),('tree',40)):
        if type(config[key]) is not str or not re.fullmatch('[0-9a-f]{%d}'%size,config[key]):
            raise ServiceRefused('EX_SERVICE_CONFIG_REFUSED')
    from .service_install import verify_installation
    verify_installation(Path(__file__).resolve().parents[1], commit=config['commit'], tree=config['tree'])
    path = Path(config['hostPath'])
    if not path.is_absolute() or path.resolve() != path or not path.is_file():
        raise ServiceRefused('EX_SERVICE_HOST_MISSING')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != config['hostSha256']:
        raise ServiceRefused('EX_SERVICE_HOST_DIGEST_REFUSED')
    # Execute exactly the inspected bytes, not a second racy path read.
    namespace = {'__name__':'_8415ex_original_host','__file__':str(path)}
    exec(compile(raw, str(path), 'exec'), namespace)
    factory = namespace.get('create_original_service_binding')
    if not callable(factory):
        raise ServiceRefused('EX_SERVICE_HOST_FACTORY_MISSING')
    return factory(), config


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Existing EX runtime foreground service')
    parser.add_argument('--config', required=True)
    parser.add_argument('--check', action='store_true', help='validate configured host and original checkpoint; do not bind HTTP')
    args = parser.parse_args(argv)
    try:
        binding, config = load_host(args.config)
        if args.check:
            print(json.dumps(validate_binding(binding, commit=config['commit'], tree=config['tree']), sort_keys=True))
        else:
            run_service(binding, commit=config['commit'], tree=config['tree'])
        return 0
    except Exception as error:
        code = str(error) if isinstance(error, ServiceRefused) else 'EX_SERVICE_CONFIGURATION_UNAVAILABLE'
        if re.fullmatch(r'EX_SERVICE_[A-Z_]{1,64}', code) is None:
            code = 'EX_SERVICE_CONFIGURATION_UNAVAILABLE'
        print(json.dumps({'status':'UNAVAILABLE','reason':code,'nativeAcceptance':'NOT_VERIFIED'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
