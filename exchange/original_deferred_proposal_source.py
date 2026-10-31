"""Concrete, bounded original deferred-payment/native-policy correlation.

Configured asset/custody bindings are facts supplied by the original host, not
new deployment, trust roots or inferred capabilities. Missing bindings refuse.
This source supports existing principal payments/refunds only. It does not turn
collateral locking, liquidation or NFT return into an ERC-20 transfer.
"""
from copy import deepcopy
from .wallet_api_client import WalletAPIClient
from .wallet_task_preparation import _require
from .exchange_fact_snapshot import decode_exchange_snapshot
from .ids import address


class OriginalDeferredProposalSource:
    def __init__(self, checkpoint, client, *, receipt_id, original_records,
                 asset_binding, custody_binding):
        _require(isinstance(client,WalletAPIClient) and type(original_records) is dict
                 and type(asset_binding) is dict and set(asset_binding)=={'chainId','asset','contract','standard'}
                 and asset_binding['standard']=='ERC-20' and asset_binding['chainId']==11155111
                 and asset_binding['asset']==checkpoint.profile.principal_asset
                 and type(custody_binding) is dict and set(custody_binding)=={'scope','location','chainId','account'}
                 and custody_binding=={'scope':checkpoint.scope,'location':checkpoint.profile.escrow,
                                       'chainId':11155111,'account':client._account}, 'EX_ORIGINAL_NATIVE_CONFIGURATION_REQUIRED')
        address(asset_binding['contract']);address(custody_binding['account'])
        self.checkpoint,self.client,self.receipt_id=checkpoint,client,receipt_id
        # Fixed capture: HTTP and later caller dict mutation cannot replace an
        # approved source mapping or silently change a policy under its ID.
        self.records=deepcopy(original_records)
        self.asset,self.custody=deepcopy(asset_binding),deepcopy(custody_binding)

    def __call__(self, identifier):
        row,model=self.checkpoint.read()
        _require(identifier in self.records, 'EX_ORIGINAL_PROPOSAL_UNBOUND')
        proposal=deepcopy(self.records[identifier])
        _require(type(proposal) is dict and proposal.get('id')==identifier
                 and proposal.get('scope')==self.checkpoint.scope
                 and proposal.get('receiptId')==self.receipt_id, 'EX_ORIGINAL_PROPOSAL_SCOPE_DIFFERS')
        matches=[op for op in model.operations.values() if op.commitment==proposal.get('commitment')]
        _require(len(matches)==1, 'EX_ORIGINAL_DEFERRED_OPERATION_UNBOUND')
        op=matches[0]
        _require(op.kind in ('seller-payment','excess-refund','rollback') and op.chain==11155111
                 and op.asset==self.asset['asset'] and op.units>0, 'EX_ORIGINAL_NATIVE_ACTION_UNSUPPORTED')
        facts=decode_exchange_snapshot(row['components']['owned-facts'])
        _require(any(leg.deferred_obligation_id==op.obligation for leg in facts.domain['_legs'].get(self.receipt_id,())), 'EX_ORIGINAL_RECEIPT_BINDING_DIFFERS')
        expected={'kind':'erc20-transfer','chainId':'11155111','actor':self.client._account,
                  'contract':self.asset['contract'],'recipient':op.recipient,'amount':str(op.units)}
        policy=proposal.get('task',{}).get('policy',{})
        _require(policy.get('intent')=={'kind':'exact-operation','operation':expected}
                 and policy.get('origin')==self.client._origin and policy.get('tenant')==self.client._tenant
                 and policy.get('actor')==self.client._account and policy.get('chainId')=='11155111', 'EX_ORIGINAL_NATIVE_TERMS_DIFFER')
        funding=op.normal_funding
        _require(type(funding) is dict and funding.get('chain')==11155111 and funding.get('asset')=='ETH'
                 and type(funding.get('terms')) is dict, 'EX_ORIGINAL_NATIVE_FUNDING_UNBOUND')
        cap=funding['terms'].get('capWei');fees=policy.get('fees')
        _require(type(cap) is int and cap>0 and type(fees) is dict and set(fees)=={'perOperationWei','totalWei'}
                 and all(type(v) is str and v.isascii() and v.isdecimal() and str(int(v))==v for v in fees.values())
                 and 0<int(fees['perOperationWei'])<=int(fees['totalWei'])<=cap, 'EX_ORIGINAL_NATIVE_FEE_CAP_DIFFERS')
        # Original canonical Wallet prepare validates digest, full policy,
        # expiry and immutable scope. This correlation creates no grant.
        return proposal
