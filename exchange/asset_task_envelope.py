"""Recheck the original Wallet's exact ERC721 normalized envelope digests.

Order follows Wallet src/agent/taskContract.ts, not sorted EX JSON. This grants
nothing: the original Wallet service still validates policy and active grant.
"""
import json
from .original_keccak import keccak256

def ordered(value, keys):
    if type(value) is not dict or set(value)!=set(keys):
        raise ValueError('exact original Wallet envelope fields required')
    return {key:value[key] for key in keys}

def check(task, child):
    ordered(task,('policy','digest'));ordered(child,('child','digest'))
    p=ordered(task['policy'],('schema','taskId','tenant','origin','chainId','actor','expiresAt','fees','intent'))
    p['fees']=ordered(p['fees'],('perOperationWei','totalWei'))
    p['intent']=ordered(p['intent'],('kind','operation'))
    op=ordered(p['intent']['operation'],('chainId','actor','kind','contract','recipient','tokenId'))
    if op['kind']!='erc721-transfer' or p['intent']['kind']!='exact-operation':raise ValueError('only original exact ERC721 supported')
    p['intent']['operation']=op
    c=ordered(child['child'],('schema','operationId','taskDigest','operation','nonce','expiresAt','wire','fees','market'))
    c['operation']=ordered(c['operation'],('chainId','actor','kind','contract','recipient','tokenId'))
    c['wire']=ordered(c['wire'],('to','calldataHash','valueWei'))
    c['fees']=ordered(c['fees'],('gasLimit','maxFeePerGasWei'))
    if c['market'] is not None or c['operation']!=op or c['taskDigest']!=task['digest']:
        raise ValueError('original asset child identity differs')
    for body,digest in ((p,task['digest']),(c,child['digest'])):
        raw=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode()
        if keccak256(raw)!=digest:raise ValueError('original Wallet normalized digest differs')
    return p,c
