"""Read-only audit reports over the domain's single event contract.

Vocabulary, identities, effect accounting and replay belong to exchange.audit;
this module adapts their results for scenario reports. Source conformance checks
capabilities rather than assuming an obsolete domain shape. Caller context is
explicitly separate from carried evidence and never changes replay identity.
"""
import ast
import pathlib

from exchange import audit, audit_projection
from exchange.errors import DomainError
from exchange.ids import digest

LEDGER_SOURCE = 'exchange/ledger.py'
AUDIT_GROUPS = audit.AUDIT_GROUPS
ANCILLARY_KINDS = audit.ANCILLARY_KINDS
DECLARED_KINDS = audit.EVENT_KINDS
MOVEMENT_KINDS = audit.MOVEMENT_KINDS
CONDITIONAL_MOVEMENT_KINDS = audit.CONDITIONAL_MOVEMENT_KINDS
CORRELATION_KEYS = audit.CORRELATION_KEYS
CHAIN_KEYS = audit.CHAIN_KEYS
CHAIN_ONLY_KINDS = tuple(
    {'kind': kind, 'why': group['whyNotLocal']}
    for group in AUDIT_GROUPS if not group['locallyEvidenced']
    for kind in group['kinds'] if kind.endswith('-observed'))
CORRELATION_SOURCES = {key: 'event correlation when present; otherwise reported missing or explicitly resolved'
                       for key in CORRELATION_KEYS + CHAIN_KEYS}
# Compatibility export: actual gaps are calculated per source in conformance().
INTERFACE_GAPS = ()


def _source(root):
    path = pathlib.Path(root) / LEDGER_SOURCE
    if not path.is_file():
        return None
    try:
        return ast.parse(path.read_text(encoding='utf-8'))
    except (OSError, SyntaxError):
        return None


def domain_recorded_kinds(root='.'):
    """Inspect actual recording call sites, including conditional event kinds."""
    tree = _source(root)
    if tree is None:
        return {'source': LEDGER_SOURCE, 'readable': False, 'kinds': [],
                'error': 'EX_LEDGER_SOURCE_UNREADABLE'}
    def literal_branches(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return {node.value}
        if isinstance(node, ast.IfExp):
            return literal_branches(node.body) | literal_branches(node.orelse)
        return set()
    found = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == '_record' and len(node.args) >= 2):
            found.update(literal_branches(node.args[1]))
    return {'source': LEDGER_SOURCE, 'readable': True, 'kinds': sorted(found),
            'kindCount': len(found), 'error': None,
            'scope': 'literal and conditional kinds at recorder call sites; dynamic observation API inspected separately'}


def _capabilities(root):
    tree = _source(root)
    functions = {} if tree is None else {node.name: node for node in ast.walk(tree)
                                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    recorder = functions.get('_record')
    calls = set() if recorder is None else {node.func.attr for node in ast.walk(recorder)
                                           if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    initializer = functions.get('__init__')
    run = initializer is not None and 'run_id' in {arg.arg for arg in initializer.args.args}
    return {'intentDecision': 'decide_intent' in functions,
            'carriedCorrelation': 'correlation' in calls,
            'runIdentity': run and 'correlation' in calls,
            'chainPositionAPI': 'record_chain_observation' in functions and 'correlation' in calls,
            'vocabularyEnforced': 'declared_kind' in calls}


def conformance(root='.'):
    recorded = domain_recorded_kinds(root)
    capabilities = _capabilities(root)
    chain = {entry['kind'] for entry in CHAIN_ONLY_KINDS}
    unrecorded = sorted(set(DECLARED_KINDS) - chain - set(recorded['kinds']))
    gaps = []
    for capability, needed in (
            ('intentDecision', 'the intent-decision audit group'),
            ('carriedCorrelation', 'correlation carried by the event'),
            ('runIdentity', 'correlating events with a supplied run identity'),
            ('chainPositionAPI', 'carrying caller-reported chain positions'),
            ('vocabularyEnforced', 'refusing undeclared kinds at recording')):
        if not capabilities[capability]:
            gaps.append({'gap': capability + ' capability not found in inspected domain source',
                         'neededFor': needed, 'whyNotLocal': 'the read-only report cannot change domain recording',
                         'owner': 'the domain and ledger owner',
                         'nextStep': 'verify and implement the missing domain capability'})
    undeclared = sorted(set(recorded['kinds']) - set(DECLARED_KINDS))
    return {'schema': '8415ex-event-conformance/2', 'domain': recorded,
            'declaredKinds': list(DECLARED_KINDS), 'declaredKindCount': len(DECLARED_KINDS),
            'chainOnlyKinds': [dict(entry) for entry in CHAIN_ONLY_KINDS],
            'undeclaredKindsRecorded': undeclared, 'declaredKindsNotRecorded': unrecorded,
            'accountedFor': recorded['readable'] and not undeclared,
            'localContractComplete': recorded['readable'] and not undeclared and not unrecorded and not gaps,
            'capabilities': capabilities, 'interfaceGaps': gaps, 'interfaceGapCount': len(gaps),
            'isNot': ['not an enforcement point: this reader reports source capabilities; the domain owns enforcement',
                      'not execution proof: static source inspection does not prove every branch ran']}


def derive_correlation(event, run_id=None, asset_key=None):
    """Prefer carried values, including explicit null; label contextual fallbacks."""
    carried = event.get('correlation') or {}
    detail = event.get('detail') or {}
    block, sources, domain, resolved = {}, {}, [], []
    for key in CORRELATION_KEYS + CHAIN_KEYS:
        if key in carried:
            block[key] = carried[key]
            sources[key] = 'event.correlation (carried by domain; null means unknown)'
            domain.append(key)
        elif key == 'receiptId' and key in event:
            block[key] = event[key]
            sources[key] = 'event.receiptId'
            domain.append(key)
        elif key in ('transferId', 'requestId') and key in detail:
            block[key] = detail[key]
            sources[key] = 'event.detail.' + key
            domain.append(key)
        elif key == 'assetKey' and asset_key is not None:
            block[key] = list(asset_key)
            sources[key] = 'reader supplied asset context; not carried by domain'
            resolved.append(key)
        elif key == 'runId' and run_id is not None:
            block[key] = run_id
            sources[key] = 'reader supplied run context; not carried by domain'
            resolved.append(key)
        else:
            block[key] = None
            sources[key] = 'not carried by the domain; unknown'
    return {'derived': bool(resolved) or not bool(carried), 'correlation': block,
            'carriedByDomain': sorted(domain), 'resolvedHere': sorted(resolved),
            'missing': sorted(key for key, value in block.items() if value is None),
            'observedOnChain': False,
            'chainPositionComplete': all(block[key] is not None for key in CHAIN_KEYS),
            'whyNotObserved': 'caller-reported chain coordinates are not independently verified chain evidence',
            'sources': sources,
            'readerContext': {'runId': run_id, 'assetKey': list(asset_key) if asset_key is not None else None}}


def event_identity(event, run_id=None, asset_key=None):
    """Shared identity; optional reader context never rewrites domain identity."""
    return audit.event_identity(event)


def coverage(timeline):
    """Shared coverage with exclusive report statuses; real prefix events count."""
    base = audit.coverage(list(timeline))
    chain = {entry['kind'] for entry in CHAIN_ONLY_KINDS}
    groups = []
    for entry in base['groups']:
        kinds = entry['declaredKinds']
        local = [kind for kind in kinds if kind not in chain]
        needs_chain = sorted(set(kinds) & chain)
        counts = entry['observedCounts']
        all_local = bool(local) and all(counts[kind] for kind in local)
        status = ('awaiting-chain-observation' if needs_chain else
                  'recorded' if all_local else 'partly-recorded' if entry['anyObserved'] else 'not-observed')
        groups.append(dict(entry, evidence='recorded', status=status,
                           locallyRecordableKinds=local, kindsNeedingAChain=needs_chain,
                           allLocallyObserved=all_local, localHalfObserved=all_local if local else None,
                           derivedValue=None, derivedFrom=[], derivedBy=None))
    result = dict(base, schema='8415ex-event-coverage/3', groups=groups,
                  byStatus={status: sorted(g['group'] for g in groups if g['status'] == status)
                            for status in sorted({g['status'] for g in groups})},
                  statusesAreExclusive=True, derivedGroups=[])
    for key, status in (('recordedGroups', 'recorded'), ('partlyRecordedGroups', 'partly-recorded'),
                        ('notObserved', 'not-observed'), ('groupsAwaitingChainObservation', 'awaiting-chain-observation')):
        result[key] = sorted(g['group'] for g in groups if g['status'] == status)
    result['isNot'] = list(base['isNot']) + ['not a derivation presented as a record: final-prefix advances are recorded events']
    return result


def replay(timeline, run_id=None, asset_key=None):
    """Delegate accounting and business projection; invalid input stays a report."""
    timeline = list(timeline)
    unknown = [{'kind': event['kind'], 'sequence': event['sequence']}
               for event in timeline if event['kind'] not in DECLARED_KINDS]
    try:
        result = audit.replay(timeline)
    except DomainError as error:
        return {'schema': '8415ex-event-replay/3', 'validReplay': False,
                'error': error.code, 'undeclaredKinds': unknown,
                'undeclaredKindCount': len(unknown), 'consumed': 0,
                'businessView': None, 'businessViewDigest': None, 'digest': None}
    result.update(schema='8415ex-event-replay/3', validReplay=True,
                  undeclaredKinds=[], undeclaredKindCount=0,
                  readerContext={'runId': run_id, 'assetKey': list(asset_key) if asset_key is not None else None},
                  businessView=None, businessViewDigest=None, projectionError=None)
    try:
        result['businessView'] = audit_projection.project(timeline)
        result['businessViewDigest'] = digest(result['businessView'])
    except DomainError as error:
        result['validReplay'] = False
        result['projectionError'] = error.code
    return result


def rebuilt_identically(timeline, run_id=None, asset_key=None):
    timeline = list(timeline)
    validation = replay(timeline, run_id, asset_key)
    if not validation['validReplay']:
        return {'schema': '8415ex-event-rebuild/3', 'validReplay': False, 'identical': False,
                'digest': None, 'repeatedDigest': None,
                'error': validation.get('error') or validation.get('projectionError')}
    result = audit.rebuilt_identically(timeline)
    repeated_view = audit_projection.project(timeline + timeline)
    result.update(schema='8415ex-event-rebuild/3', validReplay=True,
                  businessViewDigest=validation['businessViewDigest'],
                  repeatedBusinessViewDigest=digest(repeated_view))
    result['identical'] = result['identical'] and validation['businessView'] == repeated_view
    return result


def contract():
    result = audit.contract()
    result.update(schema='8415ex-event-contract/3', readOnly=True,
                  chainOnlyKinds=[dict(entry) for entry in CHAIN_ONLY_KINDS],
                  correlationSources=dict(CORRELATION_SOURCES),
                  whyReadOnly='Scenario reports read the domain contract; recording and vocabulary enforcement remain in the domain.',
                  implementation='exchange.audit')
    return result


def demonstration_timeline():
    """One local model timeline; no chain evidence or external operations."""
    from exchange import fixtures as F
    exchange, _ = F.funded_chain_to_d()
    requests = F.submit_all(exchange)
    for position in (0, 1):
        F.confirm(exchange, requests[position], 'res-%d' % position)
    exchange.release_segment('rcpt-8415-0001', 0,
                             F.release_authority(exchange, 0, 'rel-0'))
    return exchange, 'rcpt-8415-0001'


def build(exchange=None, receipt_id=None, root='.', run_id=None):
    report = {'schema': '8415ex-event-report/2', 'contract': contract(),
              'conformance': conformance(root), 'timelineRead': False,
              'coverage': None, 'replay': None, 'rebuild': None, 'validReplay': None}
    if exchange is None or receipt_id is None:
        return report
    timeline = list(exchange.receipt_timeline(receipt_id))
    asset_key = exchange.receipt(receipt_id).asset.key
    report.update(timelineRead=True, receiptId=receipt_id,
                  coverage=coverage(timeline), replay=replay(timeline, run_id, asset_key),
                  rebuild=rebuilt_identically(timeline, run_id, asset_key))
    report['liveView'] = audit_projection.live(exchange, receipt_id)
    report['matchesLive'] = report['replay']['validReplay'] and report['replay']['businessView'] == report['liveView']
    report['liveViewDigest'] = digest(report['liveView'])
    report['validReplay'] = report['matchesLive'] and report['rebuild']['identical']
    return report
