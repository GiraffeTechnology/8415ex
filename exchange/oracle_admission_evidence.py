"""Read original admitted-chain evidence through Oracle only.

The Oracle/Kit adapter authenticates the original configured EVM admission
profile. This client validates the exact app correlation; it does not sign,
claim an Ethereum state proof, or authorize funds from an observation.
"""
from copy import deepcopy
import re
from .errors import require
from .ids import digest
from .oracle_http_transport import OracleHTTPTransport, OracleHTTPRefused

CODE = 'EX_ORACLE_ADMISSION_REFUSED'
PREFIX = '/v1/oracle/admission-evidence'
HEX32 = re.compile(r'\A0x[0-9a-f]{64}\Z')
ADDRESS = re.compile(r'\A0x[0-9a-f]{40}\Z')


def uint(value, bits=64):
    require(type(value) is str and re.fullmatch(r'0|[1-9][0-9]{0,77}', value)
            and int(value) < 2**bits, CODE, 'canonical unsigned decimal required')
    return value


def word(value):
    require(type(value) is str and HEX32.fullmatch(value), CODE, 'canonical bytes32 required')
    return value


class OracleAdmissionHTTPTransport(OracleHTTPTransport):
    ROUTE = re.compile(r'\A/v1/oracle/admission-evidence/(0|[1-9][0-9]{0,77})/'
                       r'(0x[0-9a-f]{64})/(0|[1-9][0-9]{0,19})/'
                       r'([1-9][0-9]{0,19})/(admission-block|0|[1-9][0-9]{0,19})\Z')
    def validate_path(self, path):
        match = self.ROUTE.fullmatch(path)
        if (match is None or int(match[1]) >= 2**256
                or any(int(match[i]) >= 2**64 for i in (3,4))
                or (match[5] != 'admission-block' and int(match[5]) >= 2**64)):
            raise OracleHTTPRefused('ORACLE_HTTP_ROUTE_REFUSED')


class OracleAdmissionEvidenceClient:
    def __init__(self, origin, source, *, finality_policy, timeout_ms=5000):
        require(finality_policy == "rpc-finalized-tag", CODE, "explicit supported original finality policy required")
        self.finality_policy = finality_policy
        keys = {'chainId','projectionContract','settlementContract','registerId',
                'verificationProfile','verifier','attestor','codeHashes'}
        require(type(source) is dict and set(source) == keys, CODE, 'exact original source binding required')
        uint(source['chainId'], 256)
        for key in ('projectionContract','settlementContract','verifier','attestor'):
            require(type(source[key]) is str and ADDRESS.fullmatch(source[key])
                    and source[key] != '0x'+'0'*40, CODE, 'original source address required')
        for key in ('registerId','verificationProfile'): word(source[key])
        require(type(source['codeHashes']) is dict and set(source['codeHashes']) ==
                {'projection','settlement','verifier'}, CODE, 'original runtime identities required')
        for value in source['codeHashes'].values(): word(value)
        self.source = deepcopy(source)
        self.transport = OracleAdmissionHTTPTransport(origin, timeout_ms)

    def read(self, *, token_id, transaction_hash, log_index, version, instant,
             settlement_id, snapshot_hash, expected_holder):
        uint(token_id,256); word(transaction_hash); uint(log_index); uint(version)
        if instant != 'admission-block': uint(instant)
        require(version != '0', CODE, 'original admission version required')
        word(settlement_id); word(snapshot_hash)
        path = '/'.join((PREFIX,token_id,transaction_hash,log_index,version,instant))
        status, body = self.transport('GET',path)
        require(status == 200 and type(body) is dict, CODE, 'original Oracle admission unavailable')
        require(set(body) == {'schema','readOnly','trust','profileKind','source','observationBlock',
                'admission','entry','instant','holderAsOf','finalAsOf','blockSafety'} and
                body['schema'] == 'erc8415-admission-observation/1' and body['readOnly'] is True and
                body['trust'] == 'configured-rpc-not-state-proof' and
                body['profileKind'] == 'solidity-eip191-secp256k1' and body['source'] == self.source,
                CODE, 'original source/profile evidence differs')
        block, admission, entry = body['observationBlock'], body['admission'], body['entry']
        require(type(block) is dict and set(block) == {'number','hash','timestamp'},CODE,'original block required')
        uint(block['number']); uint(block['timestamp']); word(block['hash'])
        if instant == 'admission-block': instant = block['timestamp']
        require(type(admission) is dict and set(admission) == {'transactionHash','transactionIndex','logIndex',
            'projectionLogIndex','blockNumber','blockHash','settlementId','bindingDigest','proofData',
            'snapshotHash','expectedHolder','tokenId','version'}, CODE,'exact admission trace required')
        for key in ('transactionIndex','logIndex','projectionLogIndex','blockNumber','version'): uint(admission[key])
        require((admission['transactionHash'],admission['logIndex'],admission['tokenId'],admission['version'],
                 admission['blockNumber'],admission['blockHash'],admission['settlementId'],
                 admission['snapshotHash'],admission['expectedHolder']) ==
                (transaction_hash,log_index,token_id,version,block['number'],block['hash'],settlement_id,
                 snapshot_hash,expected_holder),CODE,'original request/transaction/settlement differs')
        word(admission['bindingDigest'])
        require(type(admission['proofData']) is str and re.fullmatch(r'0x[0-9a-f]{130}',admission['proofData']),
                CODE,'original profile proof required')
        require(int(admission['projectionLogIndex']) < int(log_index),CODE,'original log order differs')
        require(type(entry) is dict and set(entry) == {'recordCommitment','previousCommitment','registryReference',
                'holder','version','effectiveAt','supersededAt'},CODE,'exact admitted entry required')
        for key in ('recordCommitment','previousCommitment','registryReference'): word(entry[key])
        for key in ('version','effectiveAt','supersededAt'): uint(entry[key])
        require(entry['version'] == version and entry['holder'] == expected_holder
                and body['holderAsOf'] == expected_holder and body['instant'] == instant
                and type(body['finalAsOf']) is bool
                and int(entry['effectiveAt']) <= int(instant) <= int(block['timestamp'])
                and (entry['supersededAt'] == '0' or int(instant) < int(entry['supersededAt'])),
                CODE,'entry does not cover original observed instant')
        safety = body['blockSafety']
        require(type(safety) is dict and set(safety) == {'policy','trust','status',
                'finalizedHeadNumber','finalizedHeadHash','admissionAtOrBelowFinalized'}
                and safety['policy'] == self.finality_policy
                and safety['trust'] == 'configured-rpc-not-ancestry-proof',
                CODE, 'exact original block-safety report required')
        if safety['status'] == 'UNAVAILABLE':
            require(all(safety[k] is None for k in ('finalizedHeadNumber','finalizedHeadHash',
                    'admissionAtOrBelowFinalized')), CODE, 'unknown finality cannot assert facts')
        else:
            require(safety['status'] == 'AVAILABLE', CODE, 'unsupported finality report')
            uint(safety['finalizedHeadNumber']); word(safety['finalizedHeadHash'])
            require(type(safety['admissionAtOrBelowFinalized']) is bool and
                    safety['admissionAtOrBelowFinalized'] ==
                    (int(block['number']) <= int(safety['finalizedHeadNumber'])),
                    CODE, 'finalized head ordering differs')
            if block['number'] == safety['finalizedHeadNumber']:
                require(block['hash'] == safety['finalizedHeadHash'], CODE, 'same-height finalized hash differs')
        return deepcopy(body)

    def require_finalized(self, body):
        # Fresh read is mandatory. This is the explicitly configured trusted-RPC
        # policy, not a cryptographic ancestry proof or temporal finalAsOf.
        safety = body['blockSafety']
        require(safety['policy'] == self.finality_policy and safety['status'] == 'AVAILABLE'
                and safety['admissionAtOrBelowFinalized'] is True,
                CODE, 'original observation finality unavailable or pending')

    @staticmethod
    def reference(body):
        # Finalized head may advance; immutable admission identity must not.
        # This never caches acceptance: require_finalized rechecks each read.
        return 'oracle-admission:' + digest({k:v for k,v in body.items() if k != 'blockSafety'})
