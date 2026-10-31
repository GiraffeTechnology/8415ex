"""Read-only fixed-source ERC721 ownership observation, not a grant or Fact.

The original host must approve the exact source/runtime profile. RPC responses
are trusted configured observations, not cryptographic state proofs. Registration
holder is independent of owner and is never inferred or updated here.
"""
from copy import deepcopy
import hashlib
import json
import re
from .direct_erc20_observation import need, address, word_address, TRANSFER
from .receipt_gas_observer import _pairs, _quantity, _hash
from .original_keccak import keccak256
from .ids import canonical_json, identifier

SOURCE_SHA256 = 'da628c8cb09dbcbbbe1bfa3f90f65acdcae96f5de37054365359389ceede2ad3'
SOURCE_TREE = '6d5da00e54d98417b7b2f1a53b67b2d0aa9c4718'
SEMANTICS = ['non-proxy', 'erc721-owner-transfer-only', 'holder-independent']


def uint(value):
    need(type(value) is str and re.fullmatch(r'0|[1-9][0-9]{0,77}', value) is not None
         and int(value) < 2**256, 'exact uint256 decimal required')
    return int(value)


class AssetReturnObservation:
    def __init__(self, original_rpc, approved_profile=None, *, executor_binding):
        need(callable(original_rpc), 'original fixed RPC required')
        need(type(executor_binding) is dict and set(executor_binding) == {'digest', 'maxPriorityFeePerGasWei'},
             'original executor fee binding required')
        _hash(executor_binding['digest']); uint(executor_binding['maxPriorityFeePerGasWei'])
        self._rpc = original_rpc
        self._executor = deepcopy(executor_binding)
        self._approved = deepcopy(approved_profile)
        if approved_profile is None:
            return
        p = self._approved
        need(type(p) is dict and set(p) == {'schema','approvalReference','profileSha256','profile'}
             and p['schema'] == 'ex-approved-projection-return/1', 'exact original approved profile required')
        identifier(p['approvalReference'])
        body = p['profile']
        need(type(body) is dict and set(body) == {'chainId','contract','sourceSha256','runtimeCode','finalityPolicy','semantics','sourceTree'},
             'exact source profile required')
        need(type(body['chainId']) is int and body['chainId'] == 11155111
             and body['sourceSha256'] == SOURCE_SHA256 and body['sourceTree'] == SOURCE_TREE
             and body['finalityPolicy'] == 'rpc-finalized-tag' and body['semantics'] == SEMANTICS,
             'unsupported original source semantics/finality')
        address(body['contract'])
        need(type(body['runtimeCode']) is str and re.fullmatch(r'0x(?:[0-9a-f]{2}){1,24576}', body['runtimeCode']) is not None,
             'bounded original approved runtime required')
        need(p['profileSha256'] == hashlib.sha256(canonical_json(body).encode()).hexdigest(), 'profile byte pin differs')

    @property
    def bound(self):
        return self._approved is not None

    @property
    def executor_binding(self):
        return deepcopy(self._executor)

    def read(self, task, child, transaction_hash, now):
        need(self.bound, 'original asset source/profile/finality UNBOUND')
        need(type(now) is int and 0 <= now < 2**64, 'original observation time required')
        task, child = deepcopy(task), deepcopy(child)
        pin = self._approved['profile']
        need(type(task) is dict and set(task) == {'policy','digest'} and type(child) is dict
             and set(child) == {'child','digest'}, 'original frozen envelopes required')
        _hash(task['digest']); _hash(child['digest'])
        policy, c = task['policy'], child['child']
        need(type(policy) is dict and type(c) is dict and c.get('schema') == '8415-agent-child/1'
             and c.get('taskDigest') == task['digest'] and c.get('market') is None,
             'original exact child binding required')
        op = c.get('operation')
        need(type(op) is dict and set(op) == {'kind','chainId','actor','contract','recipient','tokenId'}
             and op['kind'] == 'erc721-transfer' and op['chainId'] == '11155111'
             and op['contract'] == pin['contract'] and policy.get('chainId') == '11155111'
             and policy.get('actor') == op['actor']
             and policy.get('intent') == {'kind':'exact-operation','operation':op}, 'exact original asset operation required')
        actor, recipient = address(op['actor']), address(op['recipient'])
        need(actor != recipient, 'NOOP is not supported by transfer observation')
        token_id, nonce = uint(op['tokenId']), uint(c['nonce'])
        wire, fees = c['wire'], c['fees']
        gas, cap = uint(fees['gasLimit']), uint(fees['maxFeePerGasWei'])
        priority = uint(self._executor['maxPriorityFeePerGasWei'])
        need(gas > 0 and cap > 0 and priority <= cap, 'original fee bounds differ')
        calldata = '0x42842e0e' + actor[2:].rjust(64,'0') + recipient[2:].rjust(64,'0') + format(token_id,'064x')
        need(wire == {'to':pin['contract'],'valueWei':'0','calldataHash':keccak256(bytes.fromhex(calldata[2:]))},
             'original safeTransferFrom wire differs')
        txhash = _hash(transaction_hash)
        reads = []
        def query(method, params):
            raw = self._rpc(method, params)
            need(type(raw) is bytes and 0 < len(raw) <= 1048576, 'bounded original RPC bytes required')
            value = json.loads(raw.decode('utf8'), object_pairs_hook=_pairs,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite RPC')))
            reads.append({'method':method,'params':deepcopy(params),'sha256':hashlib.sha256(raw).hexdigest()})
            return value
        need(_quantity(query('eth_chainId', [])) == 11155111, 'wrong chain')
        tx = query('eth_getTransactionByHash', [txhash]); receipt = query('eth_getTransactionReceipt', [txhash])
        need(type(tx) is dict and type(receipt) is dict, 'unmined/unknown original attempt')
        number, blockhash = _quantity(receipt.get('blockNumber')), _hash(receipt.get('blockHash'))
        index = _quantity(receipt.get('transactionIndex'))
        need(number > 0, 'parent ownership observation required')
        need(tx.get('hash') == txhash and tx.get('from') == actor and tx.get('to') == pin['contract']
             and _quantity(tx.get('chainId')) == 11155111 and _quantity(tx.get('nonce')) == nonce
             and _quantity(tx.get('value')) == 0 and tx.get('input') == calldata
             and _quantity(tx.get('type')) == 2 and tx.get('accessList') == []
             and _quantity(tx.get('gas')) == gas and _quantity(tx.get('maxFeePerGas')) == cap
             and _quantity(tx.get('maxPriorityFeePerGas')) == priority
             and tx.get('blockHash') == blockhash and _quantity(tx.get('blockNumber')) == number
             and _quantity(tx.get('transactionIndex')) == index, 'original signed transaction differs')
        need(receipt.get('transactionHash') == txhash and receipt.get('from') == actor
             and receipt.get('to') == pin['contract'] and _quantity(receipt.get('status')) == 1,
             'successful original transfer receipt required')
        block = query('eth_getBlockByNumber', [hex(number), False])
        need(type(block) is dict and block.get('hash') == blockhash and _quantity(block.get('number')) == number
             and type(block.get('transactions')) is list and index < len(block['transactions'])
             and block['transactions'][index] == txhash, 'canonical transaction membership differs')
        parent = query('eth_getBlockByNumber', [hex(number-1), False])
        parenthash = _hash(block.get('parentHash'))
        need(type(parent) is dict and parent.get('hash') == parenthash and _quantity(parent.get('number')) == number-1,
             'canonical parent differs')
        observed = _quantity(block.get('timestamp')); need(observed <= now, 'future block observation')
        finalized = query('eth_getBlockByNumber', ['finalized', False])
        need(type(finalized) is dict and _quantity(finalized.get('number')) >= number, 'not finalized')
        fn, fh = _quantity(finalized['number']), _hash(finalized.get('hash'))
        need(fn != number or fh == blockhash, 'same-height finalized hash differs')
        fc = query('eth_getBlockByNumber', [hex(fn), False])
        need(type(fc) is dict and fc.get('hash') == fh and _quantity(fc.get('number')) == fn, 'finalized block not canonical')
        refs = [{'blockHash':parenthash,'requireCanonical':True}, {'blockHash':blockhash,'requireCanonical':True}]
        owner_call = {'to':pin['contract'],'data':'0x6352211e'+format(token_id,'064x')}
        def ownership():
            for ref, owner in zip(refs, (actor,recipient)):
                need(query('eth_getCode', [pin['contract'],ref]) == pin['runtimeCode'], 'approved runtime differs')
                need(query('eth_getCode', [actor,ref]) == '0x' and query('eth_getCode', [recipient,ref]) == '0x',
                     'only direct EOA route supported')
                need(word_address(query('eth_call',[owner_call,ref])) == owner, 'original parent/terminal owner differs')
        ownership()
        logs = receipt.get('logs')
        need(type(logs) is list and len(logs) <= 4096, 'bounded complete receipt logs required')
        def membership(log, *, target=False):
            need(type(log) is dict and log.get('removed') is False and log.get('blockHash') == blockhash
                 and _quantity(log.get('blockNumber')) == number, 'log block membership differs')
            li, ti = _quantity(log.get('logIndex')), _quantity(log.get('transactionIndex'))
            th = _hash(log.get('transactionHash'))
            need(ti < len(block['transactions']) and block['transactions'][ti] == th,
                 'log transaction membership differs')
            if target: need(th == txhash and ti == index, 'receipt log transaction differs')
            return li
        seen = set(); selected = []
        for log in logs:
            li = membership(log,target=True); need(li not in seen,'duplicate receipt log'); seen.add(li)
            if log.get('address') == pin['contract']: selected.append(log)
        block_logs = query('eth_getLogs',[{'blockHash':blockhash,'address':pin['contract']}])
        need(type(block_logs) is list and len(block_logs) <= 4096, 'bounded complete source block logs required')
        seen = set()
        for log in block_logs:
            li = membership(log); need(li not in seen, 'duplicate block log'); seen.add(li)
            topics = log.get('topics')
            need(log.get('address') == pin['contract'] and type(topics) is list and len(topics) == 4
                 and topics[0] == TRANSFER and log.get('data') == '0x', 'unsupported source event/registration change')
            word_address(topics[1]); word_address(topics[2]); _hash(topics[3])
        expected_topics = [TRANSFER,'0x'+actor[2:].rjust(64,'0'),'0x'+recipient[2:].rjust(64,'0'),'0x'+format(token_id,'064x')]
        # Deliberately conservative: one source-contract event in the whole block.
        need(len(block_logs) == 1 and block_logs == selected and selected[0]['topics'] == expected_topics,
             'single original return effect required; multi-hop/other activity unsupported')
        ownership()
        need(query('eth_getLogs',[{'blockHash':blockhash,'address':pin['contract']}]) == block_logs
             and query('eth_getTransactionByHash',[txhash]) == tx
             and query('eth_getTransactionReceipt',[txhash]) == receipt
             and query('eth_getBlockByNumber',[hex(number),False]) == block
             and query('eth_getBlockByNumber',[hex(number-1),False]) == parent
             and query('eth_getBlockByNumber',[hex(fn),False]) == fc
             and _quantity(query('eth_chainId',[])) == 11155111, 'original observation changed')
        again = query('eth_getBlockByNumber',['finalized',False])
        need(type(again) is dict and _quantity(again.get('number')) >= fn
             and (_quantity(again['number']) != fn or again.get('hash') == fh), 'finality changed')
        identity = hashlib.sha256(canonical_json({'chain':11155111,'contract':pin['contract'],'tx':txhash,
                                                 'logs':[selected[0]['logIndex']]}).encode()).hexdigest()
        return {'schema':'ex-asset-return-observation/1','evidenceIdentity':identity,'observedAt':observed,
                'transactionHash':txhash,'blockHash':blockhash,'blockNumber':number,
                'taskDigest':task['digest'],'childDigest':child['digest'],
                'executorDigest':self._executor['digest'],'reads':reads,
                'holderInferred':False,'dispatched':False,'isEconomicFact':False,
                'trust':'original-host-configured-rpc-not-state-proof'}
