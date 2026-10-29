"""Versioned original mixed-plan attempt metadata, never a second journal."""
from copy import deepcopy
import hashlib
from .ids import canonical_json

def need(ok,reason):
    if not ok:raise ValueError(reason)
def sha(value):return hashlib.sha256(canonical_json(value).encode()).hexdigest()

def markers(domain):
    found={}
    identities={}
    nonces={}
    def visit(value):
        if isinstance(value,dict):
            if 'assetAttempt' in value:
                a=value['assetAttempt']
                need(set(value)>= {'binding','commitment','confirmed'},'asset attempt outside original mixed plan')
                validate(value,a)
                key=a['claim']['digest']
                need(key not in found or found[key]==a,'conflicting original asset attempt')
                identity=(a['task']['digest'],a['child']['digest'],a['child']['child']['operationId'])
                need(identity not in identities or identities[identity]==key,'asset task child cannot be reused across plans')
                identities[identity]=key
                binding=a['claim']['binding']
                nonce=(binding['chainId'],binding['actor'],binding['nonce'])
                need(nonce not in nonces or nonces[nonce]==key,'original asset nonce cannot be reused by another claim')
                nonces[nonce]=key
                found[key]=deepcopy(a)
            for x in value.values():visit(x)
        elif isinstance(value,(list,tuple)):
            for x in value:visit(x)
    visit(domain)
    return found

def validate(plan,a):
    need(type(a) is dict and set(a)=={'schema','status','plan','receipt','index','step','task','child','scope','authority','affected','claim'},'exact asset attempt schema required')
    need(a['schema']=='ex-mixed-asset-attempt/1' and a['status']=='UNKNOWN','immutable original UNKNOWN required')
    b=plan['binding'];i=a['index']
    need(type(i) is int and 0<=i<len(b['steps']) and b['steps'][i]==a['step']
         and a['step']['kind']=='asset-return' and a['step']['from']!=a['step']['recipient']
         and a['plan']==plan['commitment']==sha(b) and a['receipt']==b['receipt']
         and a['affected']==b['affected'],'asset attempt original plan differs')
    c=a['claim']
    need(type(c) is dict and set(c)=={'schema','scope','operation','commitment','generation','binding','digest'}
         and c['schema']=='8415-ex-dispatch-claim/1' and c['scope']==b['scope']
         and c['operation']==a['scope']['nativeOperationId'] and c['commitment']=='0x'+sha({k:v for k,v in a.items() if k!='claim'})
         and type(c['generation']) is int and c['generation']>0 and c['digest']==sha({k:v for k,v in c.items() if k!='digest'}),
         'original asset claim bytes differ')
    need(type(a['task']) is dict and set(a['task'])=={'policy','digest'} and type(a['child']) is dict and set(a['child'])=={'child','digest'},'original frozen task child required')
    from .asset_task_envelope import check
    from .rollback import RollbackAuthority
    from .model import Asset
    from .wallet_direct_return_operation import bind_wallet_direct_return
    from .wallet_task_preparation import _digest
    policy,child=check(a['task'],a['child']);op=policy['intent']['operation'];binding=c['binding']
    need(type(binding) is dict and set(binding)=={'taskDigest','childDigest','operationId','chainId','actor','nonce','executorDigest','grantPolicyVersion'}
         and all(_digest(binding[k]) for k in ('taskDigest','childDigest','executorDigest')),'exact original asset executor identity required')
    auth=deepcopy(a['authority']);auth['asset']=Asset(**auth['asset'])
    authority=RollbackAuthority(**auth)
    need(authority.authority_id==b['authority'] and authority.receipt_id==a['receipt']==a['scope']['receiptId']
         and child['operationId']==a['scope']['nativeOperationId'],'original plan authority/receipt/operation differs')
    bind_wallet_direct_return(a['scope'],authority,a['step']['from'],a['affected'],op)
    expected={'kind':'erc721-transfer','chainId':str(a['step']['asset'][0]),'actor':a['step']['from'],
              'contract':a['step']['asset'][1],'recipient':a['step']['recipient'],'tokenId':str(a['step']['asset'][2])}
    need(op==expected and child['operation']==op and child['taskDigest']==a['task']['digest']
         and binding['taskDigest']==a['task']['digest'] and binding['childDigest']==a['child']['digest']
         and binding['operationId']==child['operationId'] and binding['nonce']==child['nonce']
         and binding['actor']==op['actor'] and binding['chainId']==op['chainId'],'original asset task binding differs')

def snapshot_markers(raw):
    if b'assetAttempt' not in raw:return {}
    from .exchange_fact_snapshot import decode_exchange_snapshot, SCHEMA
    from .operational_facts_codec import decode_operational_facts
    try: value=decode_operational_facts(raw).value
    except ValueError:return {}
    if type(value) is not dict or value.get('schema')!=SCHEMA:return {}
    # Recognized original snapshots must validate; malformed markers never
    # become generic bytes merely because their schema check fails.
    return markers(decode_exchange_snapshot(raw).domain)

def preserve(previous_raw,current_raw,generation):
    # Generic aggregate users without this versioned field remain unaffected.
    if not snapshot_markers(previous_raw) and not snapshot_markers(current_raw):return False
    from .exchange_fact_snapshot import decode_exchange_snapshot
    before=decode_exchange_snapshot(previous_raw);after=decode_exchange_snapshot(current_raw)
    old,new=markers(before.domain),markers(after.domain)
    # An audit copy cannot replace the live original rollback fence. Until a
    # separate, explicitly versioned archival protocol exists, retain this
    # exact receipt/plan location even after confirmation (never auto-migrate).
    for rid,state in before.domain.get('_rollbacks',{}).items():
        plan={} if state is None else state.get('mixedRecovery',{})
        if 'assetAttempt' in plan:
            current_state=after.domain.get('_rollbacks',{}).get(rid)
            current={} if current_state is None else current_state.get('mixedRecovery',{})
            need(current.get('assetAttempt')==plan['assetAttempt']
                 and current.get('binding')==plan['binding']
                 and current.get('commitment')==plan['commitment'],
                 'live original asset fence cannot be archived away or replanned')
    need(all(new.get(k)==v for k,v in old.items()),'original asset UNKNOWN cannot be erased or replaced')
    added=set(new)-set(old)
    need(len(added)<=1,'one original asset claim per CAS')
    for key in added:
        a=new[key];rid=a['receipt'];oldstate=before.domain['_rollbacks'].get(rid)
        need(oldstate is not None and oldstate['state']!='complete' and 'mixedRecovery' in oldstate,'claim cannot manufacture original plan')
        oldplan=oldstate['mixedRecovery'];newplan=after.domain['_rollbacks'][rid]['mixedRecovery']
        need('assetAttempt' not in oldplan and {k:v for k,v in newplan.items() if k!='assetAttempt'}==oldplan,
             'claim cannot replace original recovery progress')
        need(a['claim']['generation']==generation and all(str(i) in oldplan['confirmed'] for i in range(a['index']))
             and str(a['index']) not in oldplan['confirmed'],'asset claim first-step/generation differs')
        detached=deepcopy(after.domain);del detached['_rollbacks'][rid]['mixedRecovery']['assetAttempt']
        need(detached==before.domain and before.wallet==after.wallet and before.receipts==after.receipts
             and before.mint_indexes==after.mint_indexes and before.priority_books==after.priority_books,
             'asset UNKNOWN claim must not change original business facts')

    return bool(added)
