"""Read-only original single-transfer evidence, NEVER a terminal economic Fact.

RPC finality is configured-RPC trust, not a state proof. Code/source pins do not
prove token semantics. The missing original production EvidenceVerifier remains
UNBOUND; this module cannot release/refund/confirm funds or mint proof authority.
"""
from copy import deepcopy
import hashlib
import json
import re
from types import MappingProxyType
from .receipt_gas_observer import _pairs, _quantity, _hash
from .exchange_fact_snapshot import decode_exchange_snapshot
from .ids import canonical_json
from .wallet_task_preparation import WalletTaskPreparation
from .original_keccak import keccak256

TRANSFER='0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'


class DirectObservationRefused(ValueError): pass


def need(ok, reason):
    if not ok: raise DirectObservationRefused(reason)


def address(value):
    need(type(value) is str and re.fullmatch(r'0x[0-9a-f]{40}',value) is not None
         and int(value[2:],16)>0,'exact nonzero address required')
    return value


def word_address(value):
    need(type(value) is str and re.fullmatch(r'0x0{24}[0-9a-f]{40}',value) is not None,
         'canonical address topic required')
    return address('0x'+value[-40:])


class DirectERC20Observation:
    def __init__(self, checkpoint, preparation, original_rpc, *, token_pin, finality_policy, executor_binding, proxy_binding=None):
        need(type(preparation) is WalletTaskPreparation and checkpoint.store is preparation.store
             and checkpoint.scope==preparation.scope and callable(original_rpc), 'same original store and RPC required')
        need(finality_policy=='rpc-finalized-tag','explicit original finality policy required')
        need(type(token_pin) is dict and set(token_pin)=={'chainId','contract','runtimeCode','sourceSha256'}
             and token_pin['chainId']==11155111,'original Sepolia token pin required')
        address(token_pin['contract'])
        need(type(token_pin['runtimeCode']) is str and re.fullmatch(r'0x(?:[0-9a-f]{2}){1,24576}',token_pin['runtimeCode']) is not None,
             'original bounded runtime code required')
        need(type(token_pin['sourceSha256']) is str and re.fullmatch(r'[0-9a-f]{64}',token_pin['sourceSha256']) is not None,
             'original source byte pin required')
        self.checkpoint,self.preparation,self.rpc=checkpoint,preparation,original_rpc
        self.pin=MappingProxyType(deepcopy(token_pin))
        need(type(executor_binding) is dict and set(executor_binding)=={'digest','maxPriorityFeePerGasWei'},
             'original fixed executor fee identity required')
        _hash(executor_binding['digest'])
        priority=executor_binding['maxPriorityFeePerGasWei']
        need(type(priority) is str and re.fullmatch(r'0|[1-9][0-9]{0,77}',priority) is not None
             and int(priority)<2**256,'original executor priority required')
        self.executor=MappingProxyType(deepcopy(executor_binding))
        self.proxy = None
        if proxy_binding is not None:
            from .paxos_pyusd_proxy import PaxosPYUSDProxy
            self.proxy = PaxosPYUSDProxy(proxy_binding)
            need(self.proxy.matches(self.pin),'original proxy/source token pin differs')

    def read(self, operation_id, *, expected_generation):
        row,model=self.checkpoint.read()
        need(type(expected_generation) is int and row['generation']==expected_generation,'original generation changed')
        op=model.operations.get(operation_id)
        need(op is not None and op.status in ('UNKNOWN','CONFIRMED')
             and op.kind in ('seller-payment','excess-refund','rollback')
             and op.chain==11155111 and op.units>0,'supported issued direct principal operation required')
        _,state=self.preparation._row(expected_generation)
        matches=[r for r in state['proposals'].values() if r['proposal']['commitment']==op.commitment]
        need(len(matches)==1,'one original proposal required')
        record=matches[0];p=record['proposal'];claim=record['dispatchClaim'];child=record['resolvedChild']
        need(self.preparation._proposal(p['id'])==p and child is not None and claim is not None
             and record['reserveClaimed'] is True,'original persisted child and dispatch claim required')
        self.preparation._child(p,child)
        binding=claim['binding'];policy=p['task']['policy'];c=child['child']
        need(claim['operation']==op.identity and claim['commitment']==op.commitment
             and binding['childDigest']==child['digest'] and binding['taskDigest']==p['task']['digest']
             and binding['operationId']==c['operationId'] and binding['nonce']==c['nonce']
             and binding['executorDigest']==self.executor['digest'] and binding['actor']==policy['actor'] and binding['chainId']=='11155111', 'original claim differs')
        facts=decode_exchange_snapshot(row['components']['owned-facts'])
        need(p['receiptId']==self.preparation.receipt_id and any(
            leg.deferred_obligation_id==op.obligation for leg in facts.domain['_legs'].get(p['receiptId'],())),
            'original receipt obligation differs')
        actor=address(policy['actor']);recipient=address(op.recipient);token=self.pin['contract']
        need(actor!=recipient,'self-transfer cannot establish payment')
        expected={'kind':'erc20-transfer','chainId':'11155111','actor':actor,'contract':token,
                  'recipient':recipient,'amount':str(op.units)}
        need(policy['intent']=={'kind':'exact-operation','operation':expected} and c['operation']==expected
             and c['wire']['to']==token and c['wire']['valueWei']=='0','exact original direct transfer required')
        status=self.preparation._view(p,self.preparation.client.task('status',{'taskDigest':p['task']['digest']}))
        reservations=status.get('budget',{}).get('reservations',[])
        need(len(reservations)==1,'one original reservation; historical/multi-attempt route unsupported')
        reservation=reservations[0]
        need(reservation.get('status')=='submitted' and reservation.get('operationId')==c['operationId']
             and reservation.get('childDigest')==child['digest'],'original submitted attempt required')
        txhash=_hash(reservation.get('transactionHash'))
        reads=[]
        def query(method,params):
            raw=self.rpc(method,params)
            need(type(raw) is bytes and 0<len(raw)<=1048576,'bounded original RPC result required')
            value=json.loads(raw.decode('utf8'),object_pairs_hook=_pairs,
                             parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
            reads.append({'method':method,'params':params,'sha256':hashlib.sha256(raw).hexdigest()})
            return value
        need(_quantity(query('eth_chainId',[]))==11155111,'wrong chain')
        tx=query('eth_getTransactionByHash',[txhash]);receipt=query('eth_getTransactionReceipt',[txhash])
        need(type(tx) is dict and type(receipt) is dict,'mined original transaction required; retain UNKNOWN')
        number=_quantity(receipt.get('blockNumber'));blockhash=_hash(receipt.get('blockHash'))
        index=_quantity(receipt.get('transactionIndex'))
        calldata='0xa9059cbb'+recipient[2:].rjust(64,'0')+format(op.units,'064x')
        need(c['wire']['calldataHash']==keccak256(bytes.fromhex(calldata[2:])),'original child calldata commitment differs')
        need(tx.get('hash')==txhash and tx.get('from')==actor and tx.get('to')==token
             and _quantity(tx.get('nonce'))==int(c['nonce']) and _quantity(tx.get('value'))==0
             and _quantity(tx.get('type'))==2 and tx.get('accessList')==[]
             and _quantity(tx.get('gas'))==int(c['fees']['gasLimit'])
             and _quantity(tx.get('maxFeePerGas'))==int(c['fees']['maxFeePerGasWei'])
             and _quantity(tx.get('maxPriorityFeePerGas'))==int(self.executor['maxPriorityFeePerGasWei'])
             and int(self.executor['maxPriorityFeePerGasWei'])<=int(c['fees']['maxFeePerGasWei'])
             and tx.get('input')==calldata and _quantity(tx.get('chainId'))==11155111
             and tx.get('blockHash')==blockhash and _quantity(tx.get('blockNumber'))==number
             and _quantity(tx.get('transactionIndex'))==index,'original transaction/calldata differs')
        need(receipt.get('transactionHash')==txhash and receipt.get('from')==actor and receipt.get('to')==token
             and _quantity(receipt.get('status'))==1,'receipt is not successful exact transfer')
        finalized=query('eth_getBlockByNumber',['finalized',False])
        need(type(finalized) is dict and _quantity(finalized.get('number'))>=number,'not finalized')
        finalnumber=_quantity(finalized.get('number'));finalhash=_hash(finalized.get('hash'))
        need(finalnumber!=number or finalhash==blockhash,'same-height finalized hash differs')
        finalcanonical=query('eth_getBlockByNumber',[hex(finalnumber),False])
        need(type(finalcanonical) is dict and finalcanonical.get('hash')==finalhash
             and _quantity(finalcanonical.get('number'))==finalnumber,'finalized tag is not canonical')
        block=query('eth_getBlockByNumber',[hex(number),False])
        need(type(block) is dict and block.get('hash')==blockhash and _quantity(block.get('number'))==number
             and type(block.get('transactions')) is list and index<len(block['transactions'])
             and block['transactions'][index]==txhash,'transaction not in canonical block')
        need(query('eth_getCode',[token,hex(number)])==self.pin['runtimeCode'],'original token code differs')
        need(query('eth_getCode',[actor,hex(number)])=='0x','direct EOA route required')
        logs=receipt.get('logs');need(type(logs) is list and len(logs)<=4096,'complete bounded receipt logs required')
        seen=set();net=0;debit=0;transfers=[]
        for log in logs:
            need(type(log) is dict and log.get('removed') is False and log.get('transactionHash')==txhash
                 and log.get('blockHash')==blockhash and _quantity(log.get('blockNumber'))==number
                 and _quantity(log.get('transactionIndex'))==index,'log membership differs')
            li=_quantity(log.get('logIndex'));need(li not in seen,'duplicate log index');seen.add(li)
            if log.get('address')!=token: continue
            topics=log.get('topics')
            # Unknown token events are unsupported, never ignored as fee/rebase proof.
            need(type(topics) is list and len(topics)==3 and topics[0]==TRANSFER,'unsupported token behavior/event')
            sender,receiver=word_address(topics[1]),word_address(topics[2])
            need(type(log.get('data')) is str and re.fullmatch(r'0x[0-9a-f]{64}',log['data']) is not None,'exact Transfer uint256 required')
            amount=int(log['data'],16)
            need(sender==actor and receiver==recipient,'fee/multi-route/additional transfer unsupported')
            net+=amount;debit+=amount;transfers.append(li)
        proxy_report = None
        if self.proxy is not None:
            proxy_report = self.proxy.verify(query,block,actor=actor,recipient=recipient,transaction_hash=txhash,receipt_logs=logs)
        need(len(transfers)==1 and net==op.units and debit==op.units,'complete single-transfer log effect differs')
        need(query('eth_getTransactionReceipt',[txhash])==receipt and query('eth_getTransactionByHash',[txhash])==tx
             and query('eth_getBlockByNumber',[hex(number),False])==block
             and query('eth_getCode',[token,hex(number)])==self.pin['runtimeCode']
             and query('eth_getCode',[actor,hex(number)])=='0x'
             and _quantity(query('eth_chainId',[]))==11155111,'original observation changed')
        finalagain=query('eth_getBlockByNumber',['finalized',False])
        need(type(finalagain) is dict and _quantity(finalagain.get('number'))>=finalnumber
             and (_quantity(finalagain.get('number'))!=finalnumber or finalagain.get('hash')==finalhash)
             and query('eth_getBlockByNumber',[hex(finalnumber),False])==finalcanonical,
             'finality source changed')
        if self.proxy is not None:
            need(self.proxy.verify(query,block,actor=actor,recipient=recipient,transaction_hash=txhash,receipt_logs=logs)==proxy_report,
                 'original proxy observation changed')
        finalrow=self.checkpoint.store.read(self.checkpoint.scope)
        need(finalrow['generation']==row['generation'] and finalrow['digest']==row['digest'],'original aggregate changed during read')
        identity=hashlib.sha256(canonical_json({'chain':11155111,'tx':txhash,'logs':transfers}).encode()).hexdigest()
        return {'schema':'ex-direct-erc20-observation/1','evidenceIdentity':identity,
                'scope':self.checkpoint.scope,'receipt':p['receiptId'],'operation':op.identity,'commitment':op.commitment,
                'taskDigest':p['task']['digest'],'childDigest':child['digest'],'dispatchClaimDigest':claim['digest'],
                'generation':row['generation'],'observedAt':_quantity(block.get('timestamp')),'transactionHash':txhash,'blockHash':blockhash,'blockNumber':number,
                'logIndices':transfers,'observedTransferUnits':net,'sourceSha256':self.pin['sourceSha256'],
                'runtimeCodeSha256':hashlib.sha256(bytes.fromhex(self.pin['runtimeCode'][2:])).hexdigest(),
                'finality':'rpc-finalized-tag','trust':'configured-rpc-not-state-proof','reads':reads,
                'proxyBindingObserved':self.proxy is not None,'tokenSemantics':'UNBOUND','economicFinality':'UNBOUND','isEconomicFact':False,'dispatched':False}
