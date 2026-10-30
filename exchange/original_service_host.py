"""Code-owned operator entry for the existing production composition.

The source binding module is reviewed application code, never a JSON import,
an identity issuer, or a substitute for actual original providers.
"""
from dataclasses import dataclass, fields
from importlib import import_module
from types import ModuleType

from exchange.production_host import (
    NativeAuthorityPorts, ProductionHostUnbound, RuntimeCapabilities,
    compose_production_service,
)
from exchange.service_runtime import ServiceRefused


PROVIDER_MODULE = 'exchange.original_provider_bindings'
PROVIDER_EXPORT = 'load_original_host_inputs'


class OriginalHostInputsUnavailable(ServiceRefused):
    """Safe runtime error with static input names for private diagnostics."""
    def __init__(self, names):
        self.names = tuple(names)
        super().__init__('EX_SERVICE_HOST_INPUTS_UNAVAILABLE')


@dataclass(frozen=True)
class OriginalHostInputs:
    configuration: dict
    store: object
    runtime_capabilities: object
    native_authority: object
    deferred_profile: object
    deferred_verifier: object
    original_mint_verifier: object
    authenticate_caller: object
    journal_transport: object
    with_journal_capability: object
    gas_page: object
    registration_sources: object
    features: object = None


def original_host_requirements():
    """Describe code contracts without opening configuration or credentials."""
    return {
        'providerModule': PROVIDER_MODULE,
        'providerExport': PROVIDER_EXPORT,
        'requiredInputs': [f.name for f in fields(OriginalHostInputs)
                           if f.name != 'features'],
        'currentRuntimeInputs': [f.name for f in fields(RuntimeCapabilities)],
        'nativeAuthorityInputs': [f.name for f in fields(NativeAuthorityPorts)],
        'configurationSchema': '8415ex-production-host/1',
        'hostSchema': '8415ex-host/1',
    }


def compose_original_host_inputs(inputs):
    """Use real provided ports; existing composition enforces their semantics.

    No database constructor, current-runtime clone, login, grant, certificate,
    listener, or transaction is created here. Type/shape is not authority proof.
    """
    if type(inputs) is not OriginalHostInputs:
        raise ServiceRefused('EX_SERVICE_HOST_INPUT_TYPE_REFUSED')
    required = original_host_requirements()['requiredInputs']
    missing = [name for name in required if getattr(inputs, name) is None]
    if missing:
        raise OriginalHostInputsUnavailable(missing)
    arguments = {f.name: getattr(inputs, f.name) for f in fields(inputs)
                 if f.name != 'configuration'}
    try:
        return compose_production_service(inputs.configuration, **arguments)
    except ProductionHostUnbound as error:
        allowed = set(required)
        allowed.update(original_host_requirements()['currentRuntimeInputs'])
        allowed.update(original_host_requirements()['nativeAuthorityInputs'])
        names = tuple(name for name in error.names if name in allowed)
        raise OriginalHostInputsUnavailable(names or ('original_providers',)) from None
    except Exception:
        # Provider/DB exceptions can contain credentials or private paths.
        # Keep original validation failures fatal without printing their values.
        raise ServiceRefused('EX_SERVICE_HOST_COMPOSITION_REFUSED') from None


def create_original_service_binding():
    """The zero-argument export consumed by service_runtime.load_host.

    The application integration owner supplies the fixed source module below
    from actual approved providers. Its absence is an unavailable real input,
    not permission to manufacture a receipt, authority, session, or checkpoint.
    The module must be part of the reviewed installed source/version.
    """
    try:
        module = import_module(PROVIDER_MODULE)
    except Exception:
        raise OriginalHostInputsUnavailable(('original_provider_bindings',)) from None
    if type(module) is not ModuleType:
        raise ServiceRefused('EX_SERVICE_HOST_PROVIDER_TYPE_REFUSED')
    provider = vars(module).get(PROVIDER_EXPORT)
    if not callable(provider):
        raise OriginalHostInputsUnavailable(('load_original_host_inputs',))
    try:
        inputs = provider()
    except Exception:
        raise OriginalHostInputsUnavailable(('original_provider_initialization',)) from None
    return compose_original_host_inputs(inputs)
