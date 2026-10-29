"""Explicit V3 Wallet ports for the existing EX deferred business runtime.

Construction is inert. Existing owner session/login signers and the original
persistent attempt stores belong to the host, never browser request bodies.
No test or simulation implementation is a fallback for an unavailable Wallet.
"""
from dataclasses import dataclass
from copy import deepcopy
from .deferred_settlement import DeferredRefused
from .wallet_api_client import WalletAPIClient
from .wallet_execution_attempts import WalletExecutionAttempts
from .deferred_wallet_ports import HoodiCollateralWalletClient
from .deferred_runtime_composition import compose_deferred_runtime


@dataclass(frozen=True)
class WalletV3Connection:
    origin: str
    tenant: str
    account: str
    base_path: str
    execution_attempts: WalletExecutionAttempts

    def client(self, *, collateral=False):
        if type(collateral) is not bool:
            raise ValueError('explicit Wallet chain role required')
        if not isinstance(self.execution_attempts, WalletExecutionAttempts):
            raise ValueError('original durable Wallet attempt store required')
        cls, chain = (HoodiCollateralWalletClient, 560048) if collateral else (WalletAPIClient, 11155111)
        return cls(self.origin, self.tenant, self.account, chain,
                   base_path=self.base_path, execution_attempts=self.execution_attempts)


@dataclass(frozen=True)
class WalletV3LinkedRuntime:
    runtime: object
    settlement: WalletAPIClient
    collateral: HoodiCollateralWalletClient
    execution_mode: str

    def _operation(self, operation_id, expected_generation):
        row, model = self.runtime.checkpoint.read()
        if type(expected_generation) is not int or row['generation'] != expected_generation:
            raise DeferredRefused('stale original operation generation')
        operation = model.operations.get(operation_id)
        if operation is None:
            raise DeferredRefused('original operation unavailable')
        return deepcopy(operation)

    def observe_operation(self, operation_id, *, expected_generation):
        # Observation remains evidence to verify, never an automatic Fact/confirm.
        operation = self._operation(operation_id, expected_generation)
        return self.runtime.wallet.observe_original(operation)

    def operation_review_url(self, operation_id, *, expected_generation):
        """Public locator: Wallet's own owner session prepares/confirms review.

        No callback URL, signature, account, grant reference, cookie, or OTP is
        transferred. A URL grants nothing and never changes the selected chain.
        """
        import json
        from urllib.parse import quote
        operation = self._operation(operation_id, expected_generation)
        if operation.status != 'PREPARED':
            raise DeferredRefused('prepared original operation required')
        client, binding = self.runtime.wallet._bound(operation)
        locator = {'schema': '8415-ex-operation-locator/1', 'tenant': client._tenant,
                   'chainId': client._chain, **binding.payload()}
        # The V3 root entry and exact tenant entry use the same original service;
        # neither is a guessed alternate origin or an automatic route fallback.
        path = client._base_path or '/v3'
        return client._origin + path + '#wallet-operation=' + quote(
            json.dumps(locator, separators=(',', ':')), safe='')

    def dispatch_once(self, operation_id, *, expected_generation, now):
        # Explicit host mode and explicit business command are both required.
        # No construction, login, status read, or model UI invokes this method.
        if self.execution_mode != 'native-enabled':
            raise DeferredRefused('native execution disabled for this runtime')
        return self.runtime.checkpoint.dispatch_once(operation_id, self.runtime.wallet,
            expected_generation=expected_generation, now=now)

    def login_settlement(self, original_login_message_signer):
        return self.settlement.login(original_login_message_signer)

    def login_collateral(self, original_login_message_signer):
        return self.collateral.login(original_login_message_signer)


def compose_wallet_v3_deferred_runtime(store, scope, profile, verifier, *,
        ports, settlement, collateral, execution_mode, expected_generation, expected_digest,
        principal_component=None, principal_allocator=None, verify_staged_allocation=None):
    """Connect V3 directly to original deferred prepare/execute/observe ports.

    The returned runtime.wallet is consumed by the existing deferred controller:
    prepare_original resolves the original task, dispatch_once persists UNKNOWN
    before its callback, and observe_original reconciles the same operation.
    This function neither claims an operation nor starts a server or signs in.
    The caller must use the original aggregate and native mapping, not a copied
    model checkpoint. Wallet public registration alone grants no task authority.
    """
    if execution_mode not in ('observe-only', 'native-enabled'):
        raise ValueError('explicit native Wallet execution mode required; no simulation fallback')
    if type(settlement) is not WalletV3Connection or type(collateral) is not WalletV3Connection:
        raise ValueError('explicit V3 settlement and collateral connections required')
    settlement_client = settlement.client()
    collateral_client = collateral.client(collateral=True)
    runtime = compose_deferred_runtime(store, scope, profile, verifier, ports=ports,
        settlement_client=settlement_client, collateral_client=collateral_client,
        expected_generation=expected_generation, expected_digest=expected_digest,
        principal_component=principal_component, principal_allocator=principal_allocator,
        verify_staged_allocation=verify_staged_allocation)
    return WalletV3LinkedRuntime(runtime, settlement_client, collateral_client, execution_mode)
