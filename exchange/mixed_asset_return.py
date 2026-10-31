"""Original mixed-plan asset claim and terminal consumer; no send authority."""
from copy import deepcopy
from dataclasses import asdict
from .mixed_asset_attempt import need,sha,validate
from .wallet_api_client import WalletAPIClient
from .wallet_task_status_reader import WalletTaskStatusReader
from .wallet_direct_return_operation import bind_wallet_direct_return
from .wallet_dispatch_fence import BINDING_KEYS
from .wallet_task_preparation import _digest
from .rollback import RollbackAuthority
from .asset_return_observation import AssetReturnObservation
from .asset_task_envelope import check

PREFIX=b'EX-ASSET-RETURN/1\n'

class MixedAssetReturn:
    def __init__(self, core, client, *, receipt_id, original_records, observation, now):
        from .mixed_suffix_recovery import MixedSuffixRecovery
        need(type(core) is MixedSuffixRecovery and isinstance(client,WalletAPIClient)
             and type(original_records) is dict and type(observation) is AssetReturnObservation and callable(now),
             'original asset-return configuration required')
        self.core,self.checkpoint,self.client=core,core.service,client
        self.receipt_id,self.observation,self.now=receipt_id,observation,now
        self.records=deepcopy(original_records)

    @property
    def bound(self):return self.observation.bound

    def _load(self,generation=None):
        if generation is None:generation=self.checkpoint.store.read(self.checkpoint.scope)['generation']
        row,model,ex=self.core._load(generation)
        need(ex.asset_lifecycle(self.receipt_id)['state']=='ACTIVE','retired/pending asset UNBOUND')
        state=ex._rollbacks.get(self.receipt_id)
        need(state is not None and 'mixedRecovery' in state and state['state']!='complete','existing incomplete mixed asset plan required')
        step=self.core.next_required_step(self.receipt_id,expected_generation=generation)
        need(step['index'] is not None and step['requiredOutcome']['kind']=='asset-return','original first asset step required')
        outcome=step['requiredOutcome'];plan=state['mixedRecovery']
        need(outcome['from']!=outcome['recipient'] and outcome['units']==1,'NOOP asset boundary UNBOUND')
        return row,model,ex,state,plan,step

    def _context(self,event,generation=None):
        row,model,ex,state,plan,step=self._load(generation)
        need(self.bound,'asset source/profile UNBOUND')
        need(type(event) is dict and set(event)=={'task','child','binding'},'exact original asset event required')
        binding=event['binding'];task=event['task'];child=event['child']
        need(type(binding) is dict and set(binding)==BINDING_KEYS and all(_digest(binding[k]) for k in ('taskDigest','childDigest','executorDigest')),
             'asset executor binding refused')
        need(type(task) is dict and set(task)=={'policy','digest'} and task['digest'] in self.records,'original asset task mapping unavailable')
        record=self.records[task['digest']]
        need(type(record) is dict and set(record)=={'scope','authority','affectedLegs','task','child','executorDigest','grantPolicyVersion'}
             and task==record['task'] and child==record['child'] and type(record['authority']) is RollbackAuthority,'original asset mapping changed')
        policy,c=check(task,child);operation=policy['intent']['operation']
        need(policy['schema']=='8415-agent-task/1' and policy['intent']['kind']=='exact-operation'
             and policy['origin']==self.client._origin and policy['tenant']==self.client._tenant
             and policy['actor']==self.client._account and policy['chainId']==self.client._chain,'original asset owner session differs')
        need(c['schema']=='8415-agent-child/1' and c['taskDigest']==task['digest'] and c['operation']==operation and c['market'] is None,
             'original asset child differs')
        need(binding=={'taskDigest':task['digest'],'childDigest':child['digest'],'operationId':c['operationId'],
             'chainId':policy['chainId'],'actor':policy['actor'],'nonce':c['nonce'],
             'executorDigest':record['executorDigest'],'grantPolicyVersion':record['grantPolicyVersion']},'original asset event identity differs')
        need(binding['executorDigest']==self.observation.executor_binding['digest'],'original asset executor source differs')
        authority=record['authority'];outcome=step['requiredOutcome']
        need(authority.authority_id==state['authorityId'] and authority.source==state['source']
             and record['affectedLegs']==list(state['affectedLegs']),'original asset authority/interval differs')
        ex._check_rollback_authority(self.receipt_id,state['refusedLegIndex'],authority,
            {'affectedLegs':state['affectedLegs'],'boundaryAccount':state['boundaryAccount']})
        bind_wallet_direct_return(record['scope'],authority,outcome['from'],record['affectedLegs'],operation)
        need(operation=={'kind':'erc721-transfer','chainId':str(outcome['asset'][0]),'actor':outcome['from'],
             'contract':outcome['asset'][1],'recipient':outcome['recipient'],'tokenId':str(outcome['asset'][2])},'original asset step differs')
        return row,model,ex,state,plan,step,record

    def claim(self,event,*,expected_generation=None):
        row,model,ex,state,plan,step,record=self._context(event,expected_generation)
        prior=plan.get('assetAttempt')
        if prior is not None:
            validate(plan,prior)
            need(prior['task']==event['task'] and prior['child']==event['child'] and prior['claim']['binding']==event['binding'],
                 'original asset attempt cannot change')
            return self.assert_claim(event,prior['claim'])
        need(int(event['task']['policy']['expiresAt'])>self.now() and int(event['child']['child']['expiresAt'])>self.now(),
             'original asset task/child expired')
        attempt={'schema':'ex-mixed-asset-attempt/1','status':'UNKNOWN','plan':plan['commitment'],
            'receipt':self.receipt_id,'index':step['index'],'step':deepcopy(step['requiredOutcome']),
            'task':deepcopy(event['task']),'child':deepcopy(event['child']),'scope':deepcopy(record['scope']),
            'authority':asdict(record['authority']),'affected':deepcopy(record['affectedLegs'])}
        claim={'schema':'8415-ex-dispatch-claim/1','scope':self.checkpoint.scope,
            'operation':record['scope']['nativeOperationId'],'commitment':'0x'+sha(attempt),'generation':row['generation']+1,
            'binding':deepcopy(event['binding'])}
        claim['digest']=sha(claim);attempt['claim']=claim;plan['assetAttempt']=attempt
        validate(plan,attempt)
        self.core._save(row,model,ex)
        self.assert_claim(event,claim)
        return deepcopy(claim)

    def assert_claim(self,event,receipt):
        row,model,ex,state,plan,step,record=self._context(event)
        a=plan.get('assetAttempt');need(a is not None,'original asset UNKNOWN missing')
        validate(plan,a)
        need(a['claim']==receipt and a['task']==event['task'] and a['child']==event['child']
             and a['claim']['binding']==event['binding'] and row['generation']>=receipt['generation'],'asset claim no longer current')
        need(int(event['task']['policy']['expiresAt'])>self.now() and int(event['child']['child']['expiresAt'])>self.now(),
             'original asset send window expired')
        return deepcopy(receipt)

    def existing(self,generation):
        row,model,ex,state,plan,step=self._load(generation)
        a=plan.get('assetAttempt');need(self.bound and a is not None,'original issued asset proof UNBOUND')
        validate(plan,a)
        self._context({'binding':a['claim']['binding'],'task':a['task'],'child':a['child']},generation)
        return row,step,deepcopy(a)

    def verify_terminal(self,request,raw,now):
        row,step,a=self.existing(self.checkpoint.store.read(self.checkpoint.scope)['generation'])
        expected={'plan':step['plan'],'scope':self.checkpoint.scope,'receipt':self.receipt_id,'step':step['requiredOutcome']}
        need(request==expected and raw==PREFIX+a['claim']['digest'].encode(),'exact original claimed asset receipt required')
        observed=WalletTaskStatusReader(self.client).read(a['scope'],a['task']['digest'],a['child']['child']['operationId'],a['child']['digest'],a['task']['policy']['intent']['operation'])
        need(observed['reservationStatus']=='submitted','original asset submission unresolved')
        report=self.observation.read(a['task'],a['child'],observed['reservation']['transactionHash'],now)
        after=self.checkpoint.store.read(self.checkpoint.scope)
        need(after['generation']==row['generation'] and after['digest']==row['digest'],'original asset aggregate changed')
        return {'request':deepcopy(request),'status':'CONFIRMED','evidenceReference':'asset:'+report['evidenceIdentity']}

    def confirm(self,generation,now):
        row,step,a=self.existing(generation)
        need(getattr(self.core.verify_terminal,'__self__',None) is self,'original asset verifier not installed')
        return self.core.confirm(self.receipt_id,expected_generation=generation,now=now,
            confirmations={str(step['index']):{'raw':PREFIX+a['claim']['digest'].encode()}})
