"""Original aggregate companion for new registration-task correlations.

No second ledger, migration guessing, task creation or dispatch. New request and
mapping commit in one CAS; original journal GET and Oracle evidence are reads.
"""
from copy import deepcopy
from dataclasses import asdict
import json

from .aggregate_checkpoint import AggregateCheckpointStore
from .errors import require
from .ids import canonical_json, digest
from .exchange_fact_snapshot import decode_exchange_snapshot
from .exchange_fact_rehydration import rehydrate_exchange_facts
from .original_task_journal_reader import OriginalTaskJournalReader
from .oracle_admission_evidence import OracleAdmissionEvidenceClient, word, uint
from .principal_journal_contract import PrincipalBinding
from .model import Asset
from .settlement import EscrowPosition
from .registration import RegistrationEvidence
from .oracle_registration_reader import OriginalOracleRegistration

CODE = 'EX_ORACLE_MAPPING_REFUSED'
SCHEMA = '8415ex-registration-task-mapping/1'
COMPONENT = 'registration-task-mapping'


def empty_mapping():
    return canonical_json({'schema':SCHEMA,'records':{}}).encode()


def decode_mapping(raw):
    require(type(raw) is bytes and len(raw) <= 2*1024*1024,CODE,'bounded original mapping bytes required')
    value = json.loads(raw.decode('utf-8'))
    require(type(value) is dict and set(value) == {'schema','records'} and value['schema'] == SCHEMA
            and type(value['records']) is dict and canonical_json(value).encode() == raw,
            CODE,'canonical mapping companion required')
    return value


def principal_from(value):
    require(type(value) is dict,CODE,'original principal binding required')
    fields = dict(value)
    fields['asset'] = Asset(**fields['asset'])
    fields['position'] = EscrowPosition(**fields['position'])
    return PrincipalBinding(**fields)


def registration_snapshot_hash(request, principal, source):
    """EX-specific original settlement snapshot, not a second registration receipt.

    Generated before the original source task opens its settlement. The existing
    Kit profile signs this exact snapshotHash, thereby binding EX asset/leg,
    request and original financial operation to the admitted record.
    """
    return digest({'schema':'8415ex-registration-snapshot/1',
                   'requestDigest':request.content_digest,
                   'principalBinding':principal.terms,'oracleSource':source})


class OracleRegistrationMapping:
    def __init__(self, store, scope, *, journal, client, fresh_runtime):
        require(type(store) is AggregateCheckpointStore and COMPONENT in store.components
                and 'owned-facts' in store.components, CODE,'predeclared original aggregate companion required')
        require(type(journal) is OriginalTaskJournalReader and type(client) is OracleAdmissionEvidenceClient
                and callable(fresh_runtime),CODE,'original task journal, Oracle client and detached runtime required')
        self.store,self.scope,self.journal,self.client,self.fresh_runtime=store,scope,journal,client,fresh_runtime

    def _row(self, generation=None, aggregate_digest=None):
        row=self.store.read(self.scope)
        require(row is not None and (generation is None or row['generation']==generation)
                and (aggregate_digest is None or row['digest']==aggregate_digest),CODE,'original aggregate changed; reconcile')
        return row,decode_mapping(row['components'][COMPONENT])

    def _operation(self, record):
        p=principal_from(record['principal'])
        operation=self.journal.read(record['taskPrincipal'],record['operationId'],p.asset.chain_id,
                                    record['taskWallet'])['nativeOperation']
        require(operation['requestHash']==record['nativeRequestHash'],CODE,'original native request changed')
        return operation

    def prepare(self, *, expected_generation, receipt_id, leg_index, request_id,
                commitment_window, now, principal, task_principal, operation_id,
                task_wallet, settlement_id, snapshot_hash, registrar_source):
        """Original business command: persist new request + task mapping atomically.

        Called with the task that the original application already prepared,
        not with a browser-selected replacement operation. Does not execute it.
        """
        row,state=self._row(expected_generation)
        require(request_id not in state['records'],CODE,'mapping already exists; read/reconcile instead of preparing again')
        facts=decode_exchange_snapshot(row['components']['owned-facts'])
        require(request_id not in facts.domain['_requests'],CODE,'historical unbound request cannot be guessed/backfilled')
        require(type(principal) is PrincipalBinding,CODE,'original principal segment required')
        receipt=facts.receipts.get(receipt_id)
        legs=facts.domain['_legs'].get(receipt_id,())
        require(receipt is not None and type(leg_index) is int and 0<=leg_index<len(legs),CODE,'original leg missing')
        leg=legs[leg_index]
        p=principal.position
        require((p.receipt_id,p.leg_index,principal.transfer_id,principal.asset,p.payer,p.payee,p.principal,p.quote_asset)==
                (receipt_id,leg_index,leg.transfer_id,receipt.asset,leg.buyer,leg.seller,leg.price,leg.quote_asset),
                CODE,'original principal and owned leg differ')
        word(settlement_id);word(snapshot_hash)
        require(type(registrar_source) is str and registrar_source,CODE,'original registrar source required')
        operation=self.journal.read(task_principal,operation_id,principal.asset.chain_id,task_wallet)['nativeOperation']
        # Captured operation is a correlation only; not a successful execution.
        runtime=self.fresh_runtime(row)
        access=rehydrate_exchange_facts(row['components']['owned-facts'],runtime)
        require(access.snapshot_bytes()==row['components']['owned-facts'],CODE,'runtime authority differs from original generation')
        request=access.prepare_registration_request(receipt_id,leg_index,request_id,commitment_window,now)
        require(snapshot_hash==registration_snapshot_hash(request,principal,self.client.source),
                CODE,'original task must use the exact EX registration snapshot')
        access.record_prepared_registration_request(request)
        record={'requestId':request_id,'requestDigest':request.content_digest,'principal':asdict(principal),
                'taskPrincipal':deepcopy(task_principal),'operationId':operation_id,'taskWallet':task_wallet,
                'nativeRequestHash':operation['requestHash'],'settlementId':settlement_id,'snapshotHash':snapshot_hash,
                'registrarSource':registrar_source,'preparedAt':now,'observation':None}
        state['records'][request_id]=record
        values=dict(row['components']);values['owned-facts']=access.snapshot_bytes()
        values[COMPONENT]=canonical_json(state).encode()
        # Unknown commit outcome propagates. Never retry or dispatch here.
        return self.store.save(self.scope,values,expected_generation=row['generation'],
            immutable_components=tuple(k for k in values if k not in ('owned-facts',COMPONENT)))

    def _read_evidence(self, record, locator):
        principal=principal_from(record['principal'])
        operation=self._operation(record)
        require(operation.get('transactionHash','').lower()==locator['transactionHash'],
                CODE,'original task has not observed this transaction')
        body=self.client.read(token_id=str(principal.asset.token_id),transaction_hash=locator['transactionHash'],
            log_index=locator['logIndex'],version=locator['version'],instant='admission-block',
            settlement_id=record['settlementId'],snapshot_hash=record['snapshotHash'],expected_holder=principal.position.payer)
        require(self.client.source['chainId']==str(principal.asset.chain_id),
                CODE,'original asset and Oracle projection differ')
        return body

    def observe(self, request_id, *, expected_generation, log_index, version, now):
        """Read the same task and exact Oracle proof; HTTP success is insufficient."""
        row,state=self._row(expected_generation);record=state['records'].get(request_id)
        require(record is not None,CODE,'new original mapping missing; no historical inference')
        operation=self._operation(record)
        tx=operation.get('transactionHash')
        require(type(tx) is str,CODE,'original native transaction is still unknown')
        locator={'transactionHash':word(tx.lower()),'logIndex':uint(log_index),'version':uint(version)}
        body=self._read_evidence(record,locator)
        require(type(now) is int and int(body['observationBlock']['timestamp'])<=now,CODE,'observation clock precedes source block')
        if record['observation'] is not None:
            old=record['observation']
            require(old['locator']==locator and old['evidenceReference']==self.client.reference(body),
                    CODE,'different observation cannot overwrite original evidence')
            return row
        record['observation']={'locator':locator,'observedAt':now,'evidenceReference':self.client.reference(body)}
        values=dict(row['components']);values[COMPONENT]=canonical_json(state).encode()
        return self.store.save(self.scope,values,expected_generation=row['generation'],
            immutable_components=tuple(k for k in values if k!=COMPONENT))

    def _resolve(self, record, facts):
        observation=record['observation'];require(observation is not None,CODE,'original admission unobserved')
        request=facts.domain['_requests'].get(record['requestId'])
        require(request is not None and request.content_digest==record['requestDigest'],CODE,'original request differs')
        require(record['snapshotHash']==registration_snapshot_hash(request,principal_from(record['principal']),self.client.source),
                CODE,'EX request/asset/journal snapshot differs')
        body=self._read_evidence(record,observation['locator'])
        require(self.client.reference(body)==observation['evidenceReference'],CODE,'source evidence changed; reconcile')
        self.client.require_finalized(body)
        block,entry=body['observationBlock'],body['entry']
        evidence=RegistrationEvidence('oracle:'+body['admission']['transactionHash']+':'+body['admission']['logIndex'],
            request.request_id,request.receipt_id,request.transfer_id,request.leg_index,request.adapter,
            record['registrarSource'],'confirmed',request.asset,observation['observedAt'],
            result_version=1,record_commitment=entry['recordCommitment'],simulated=False,
            effective_at=int(entry['effectiveAt']),query_at=int(body['instant']),observation_block=int(block['number']),
            observation_block_hash=block['hash'],temporal_evidence_reference=observation['evidenceReference'])
        return OriginalOracleRegistration(evidence,principal_from(record['principal']),entry['version'])

    def resolve_original(self, context, binding):
        row,state=self._row(context.generation,context.aggregate_digest)
        require(row['components']['owned-facts']==context.owned_before,CODE,'original owned bytes differ')
        facts=decode_exchange_snapshot(context.owned_before)
        records=[r for r in state['records'].values() if r['principal']['position']['receipt_id']==binding.receipt_id
                 and r['principal']['position']['leg_index']==binding.leg_index
                 and r['principal']['transfer_id']==binding.transfer_id]
        require(len(records)==1,CODE,'exact original request mapping required')
        return self._resolve(records[0],facts)

    def verify_mapping(self, principal, projection):
        _,state=self._row()
        matches=[r for r in state['records'].values() if principal_from(r['principal'])==principal]
        if len(matches)!=1 or matches[0]['observation'] is None:return False
        body=self._read_evidence(matches[0],matches[0]['observation']['locator'])
        return (projection['source']=={'chainId':body['source']['chainId'],
            'contract':body['source']['projectionContract'],'registerId':body['source']['registerId']}
            and projection['entry']['recordCommitment']==body['entry']['recordCommitment']
            and projection['entry']['version']==body['entry']['version']
            and projection['entry']['effectiveAt']==body['entry']['effectiveAt'])

    def mint_verifier(self, original_verifier):
        require(callable(original_verifier),CODE,'existing mint verifier required')
        def verify(kind, binding):
            if kind!='registration-effective-time':return original_verifier(kind,binding)
            try:
                row,state=self._row();facts=decode_exchange_snapshot(row['components']['owned-facts'])
                matches=[r for r in state['records'].values() if r['requestDigest']==binding['requestDigest']]
                if len(matches)!=1:return False
                resolved=self._resolve(matches[0],facts);e=resolved.evidence;p=resolved.principal
                mint=facts.domain['_mint_declarations'][e.receipt_id]
                expected={'receiptId':e.receipt_id,'transferId':e.transfer_id,'legIndex':e.leg_index,
                    'asset':e.asset.key,'seller':p.position.payee,'buyer':p.position.payer,
                    'requestDigest':matches[0]['requestDigest'],'resultDigest':e.content_digest,
                    'source':e.source,'recordCommitment':e.record_commitment,'temporalProjection':e.temporal_projection,
                    'observedAt':e.observed_at,'mintDeclarationDigest':mint['declarationDigest'],
                    'mintTime':deepcopy(mint['canonicalDeclaration']['time'])}
                return binding==expected
            except Exception:return False
        return verify
