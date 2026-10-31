"""Fixed-version Paxos PYUSD proxy evidence binding, not deployment approval.

Original source: paxosglobal/paxos-token-contracts commit below. Its historical
Zeppelinos slots are NOT EIP-1967. All deployment addresses/code/build provenance
must be supplied by the original authorized host; nothing is guessed/discovered.
"""
from copy import deepcopy
from types import MappingProxyType
import hashlib
import re
from .original_keccak import keccak256
from .direct_erc20_observation import need,address,word_address,TRANSFER
from .receipt_gas_observer import _quantity,_hash

SOURCE_COMMIT='674ac1046a0a40bfd2b6b892192998af9ac3b171'
SOURCE_REVIEW_MANIFEST='e5f33c11a6c5f1d519bbc182943c5a45c48468495832f13648cbfd28ebb2f455'
IMPLEMENTATION_SLOT='0x7050c9e0f4ca769c69bd3a8ef740bc37934f8e2c036e5a723fd8ee048ed3f8c3'
ADMIN_SLOT='0x10d6a54a4754c8869d6886b5f5d7fbfa5b4522237ea5c60d11bc4e7a1ff9390b'


class PaxosPYUSDProxy:
    def __init__(self, binding):
        fields={'schema','sourceCommit','sourceReviewManifestSha256','buildSourceClosureSha256',
                'proxy','proxyRuntimeCode','implementation','implementationRuntimeCode','admin'}
        need(type(binding) is dict and set(binding)==fields,'complete original PYUSD proxy binding required')
        b=deepcopy(binding)
        need(b['schema']=='paxos-pyusd-zeppelinos-v2/1' and b['sourceCommit']==SOURCE_COMMIT
             and b['sourceReviewManifestSha256']==SOURCE_REVIEW_MANIFEST,'reviewed fixed official source required')
        for key in ('proxy','implementation','admin'):address(b[key])
        need(len({b['proxy'],b['implementation'],b['admin']})==3,'distinct proxy implementation admin required')
        for key in ('proxyRuntimeCode','implementationRuntimeCode'):
            need(type(b[key]) is str and re.fullmatch(r'0x(?:[0-9a-f]{2}){1,24576}',b[key]) is not None,'original compiled runtime required')
        need(type(b['buildSourceClosureSha256']) is str and re.fullmatch(r'[0-9a-f]{64}',b['buildSourceClosureSha256']) is not None,
             'original complete build source closure pin required')
        self._binding=MappingProxyType(b)

    def approval_terms(self):
        b=self._binding
        return {k:v for k,v in b.items() if not k.endswith('RuntimeCode')} | {
            'proxyRuntimeCodeSha256':hashlib.sha256(bytes.fromhex(b['proxyRuntimeCode'][2:])).hexdigest(),
            'implementationRuntimeCodeSha256':hashlib.sha256(bytes.fromhex(b['implementationRuntimeCode'][2:])).hexdigest()}

    def matches(self,pin):
        b=self._binding
        return (pin['contract']==b['proxy'] and pin['runtimeCode']==b['proxyRuntimeCode']
                and pin['sourceSha256']==b['buildSourceClosureSha256'])

    def verify(self,query,block,*,actor,recipient,transaction_hash,receipt_logs):
        b=self._binding;n=_quantity(block['number']);h=_hash(block['hash'])
        need(n>0 and actor!=b['admin'],'supported non-admin direct EOA route required')
        parent=query('eth_getBlockByNumber',[hex(n-1),False])
        need(type(parent) is dict and _quantity(parent.get('number'))==n-1
             and _hash(parent.get('hash'))==block.get('parentHash'),'original parent block differs')
        selectors={'decimals':'0x313ce567','paused':keccak256(b'paused()')[:10],
                   'isFrozen':keccak256(b'isFrozen(address)')[:10]}
        for header in (parent,block):
            tag={'blockHash':header['hash'],'requireCanonical':True}
            need(query('eth_getCode',[b['proxy'],tag])==b['proxyRuntimeCode']
                 and query('eth_getCode',[b['implementation'],tag])==b['implementationRuntimeCode'],
                 'original proxy/implementation code changed')
            need(word_address(query('eth_getStorageAt',[b['proxy'],IMPLEMENTATION_SLOT,tag]))==b['implementation']
                 and word_address(query('eth_getStorageAt',[b['proxy'],ADMIN_SLOT,tag]))==b['admin'],
                 'original proxy implementation/admin binding changed')
            def call(data):return query('eth_call',[{'to':b['proxy'],'data':data},tag])
            need(call(selectors['decimals'])=='0x'+format(6,'064x'),'PYUSD six-decimal source differs')
            need(call(selectors['paused'])=='0x'+'0'*64,'paused boundary unsupported')
            for account in (actor,recipient):
                need(call(selectors['isFrozen']+account[2:].rjust(64,'0'))=='0x'+'0'*64,'frozen boundary unsupported')
        logs=query('eth_getLogs',[{'address':b['proxy'],'blockHash':h}])
        need(type(logs) is list and len(logs)<=4096,'complete bounded proxy block logs required')
        matching=[];indices=set()
        for log in logs:
            need(type(log) is dict and log.get('address')==b['proxy'] and log.get('removed') is False
                 and log.get('blockHash')==h and _quantity(log.get('blockNumber'))==n,'proxy block log membership differs')
            index=_quantity(log.get('logIndex'));need(index not in indices,'duplicate block log index');indices.add(index)
            txhash=_hash(log.get('transactionHash'));txindex=_quantity(log.get('transactionIndex'))
            need(type(block.get('transactions')) is list and txindex<len(block['transactions'])
                 and block['transactions'][txindex]==txhash,'proxy log transaction membership differs')
            need(type(log.get('data')) is str and re.fullmatch(r'0x[0-9a-f]{64}',log['data']) is not None,
                 'proxy Transfer uint256 word required')
            topics=log.get('topics')
            # Conservative supported block: no upgrades/admin changes, pauses,
            # freezes/wipes, approvals or supply-control events. An unsupported
            # block is NOT terminal failure/nonexecution and cannot authorize retry.
            need(type(topics) is list and len(topics)==3 and topics[0]==TRANSFER,'complex same-block token/admin mutation unsupported')
            sender,receiver=word_address(topics[1]),word_address(topics[2])
            if log.get('transactionHash')==transaction_hash:matching.append(log)
            else:need(not ({sender,receiver}&{actor,recipient}),'other same-block relevant balance effect unsupported')
        original=[log for log in receipt_logs if log.get('address')==b['proxy']]
        need(matching==original,'complete proxy block/receipt logs disagree')
        # Full receipt/canonical block are reread by the caller; this second
        # invocation also rereads parent state, slots, code and whole-block logs.
        return {'sourceCommit':SOURCE_COMMIT,'implementation':b['implementation'],
                'admin':b['admin'],'blockHash':h,'parentHash':parent['hash']}
