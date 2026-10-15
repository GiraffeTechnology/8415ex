"""Bounded read model rebuilt from domain events, never a command-state restore.

The view deliberately omits live clocks, authorizations, adapter internals and
undecided product policies. ``live`` independently reads domain state; it is an
acceptance oracle, not input to ``project``. A complete single-receipt timeline
starting with mint is required. Repeated exact events are harmless; conflicting
or reordered unique events are refused rather than producing a misleading view.
"""
from .errors import require
from .ids import digest


def _base(receipt_id, origin):
    return {'receiptId': receipt_id,
            'owner': {'account': origin, 'position': 0},
            'holder': {'account': origin, 'position': 0},
            'recordedLegs': 0, 'assetReturnedByRollback': False,
            'escrows': {}, 'legs': [], 'rollback': None, 'exit': None}


def project(timeline):
    """Derive the supported business view using only immutable event facts."""
    from .audit import declared_kind
    state, seen, positions = None, {}, {}
    next_sequence = 0
    stream_run = None
    for event in timeline:
        declared_kind(event['kind'])
        sequence = event['sequence']
        require(isinstance(sequence, int) and not isinstance(sequence, bool),
                'EX_PROJECTION_SEQUENCE_REFUSED', str(sequence))
        receipt_id = event.get('receiptId')
        correlation = event.get('correlation') or {}
        require(correlation.get('receiptId') == receipt_id and receipt_id is not None,
                'EX_PROJECTION_STREAM_REFUSED', str(receipt_id))
        if state is None:
            stream_run = correlation.get('runId')
        require(correlation.get('runId') == stream_run, 'EX_PROJECTION_STREAM_REFUSED', 'runId changed')
        identity = (receipt_id, sequence)
        content = digest(event)
        if identity in seen:
            require(seen[identity] == content, 'EX_PROJECTION_EVENT_CONFLICT', str(sequence))
            continue
        require(sequence == next_sequence, 'EX_PROJECTION_SEQUENCE_REFUSED', str(sequence))
        seen[identity] = content
        next_sequence += 1
        kind, d = event['kind'], event['detail']
        if state is None:
            require(kind == 'receipt-minted', 'EX_PROJECTION_MINT_REQUIRED', kind)
            state = _base(receipt_id, d['origin'])
            positions[0] = d['origin']
        require(receipt_id == state['receiptId'], 'EX_PROJECTION_STREAM_REFUSED', str(receipt_id))
        if kind == 'transfer-executed':
            positions[d['ownerIndex']] = d['buyer']
            state['owner'] = {'account': d['buyer'], 'position': d['ownerIndex']}
            state['recordedLegs'] += 1
            state['legs'].append({
                'legIndex': d['legIndex'], 'transferId': d['transferId'],
                'registrationStatus': d['registrationStatus'],
                'fundingStatus': d['fundingStatus'],
                'rollbackStatus': d.get('rollbackStatus', 'available' if d['fundingStatus'] == 'locked' else 'none')})
        elif kind == 'registration-submitted':
            leg = state['legs'][d['legIndex']]
            if leg['registrationStatus'] == 'not-submitted':
                leg['registrationStatus'] = 'pending'
        elif kind == 'registration-result' and d['disposition'] == 'rejected':
            state['legs'][d['legIndex']]['registrationStatus'] = 'rejected'
        elif kind == 'final-prefix-advanced':
            state['holder'] = {'account': positions[d['to']], 'position': d['to']}
            state['legs'][d['legIndex']]['registrationStatus'] = 'confirmed'
        elif kind == 'escrow-locked':
            state['escrows'][d['escrowId']] = {
                key: d[key] for key in ('legIndex', 'payer', 'payee', 'quoteAsset', 'principal', 'status')}
            state['escrows'][d['escrowId']].update(
                paymentKey=None, paymentIntent=None, paymentStatus=None)
        elif kind == 'payment-attempt-started':
            state['escrows'][d['escrowId']].update(
                paymentKey=d['paymentKey'], paymentIntent=d['intent'], paymentStatus=d['paymentStatus'])
            if d['intent'] == 'release':
                index = state['escrows'][d['escrowId']]['legIndex']
                state['legs'][index]['fundingStatus'] = 'release-outcome-unknown'
        elif kind in ('segment-release-attempt', 'segment-refunded', 'segment-refund-attempt'):
            escrow = state['escrows'][d['escrowId']]
            intent = 'release' if kind == 'segment-release-attempt' else 'refund'
            escrow.update(paymentIntent=intent, paymentStatus=d['paymentStatus'])
            if 'paymentKey' in d:
                escrow['paymentKey'] = d['paymentKey']
            if kind == 'segment-release-attempt':
                escrow['status'] = d['escrowStatus']
                leg = state['legs'][escrow['legIndex']]
                leg['fundingStatus'] = ('released' if d['paymentStatus'] == 'settled'
                                        else 'release-failed' if d['paymentStatus'] == 'failed'
                                        else 'release-outcome-unknown')
                leg['rollbackStatus'] = d['rollbackStatus']
            elif kind == 'segment-refunded':
                escrow['status'] = 'refunded'
                state['legs'][escrow['legIndex']].update(fundingStatus='refunded', rollbackStatus='returned')
        elif kind == 'payment-enquiry':
            # A nonterminal enquiry does not mutate escrow in the current
            # domain. Settlement uses the original attempted operation intent.
            if d['paymentStatus'] == 'settled':
                escrow = state['escrows'][d['escrowId']]
                intent = d.get('paymentIntent', escrow['paymentIntent'])
                require(intent in ('release', 'refund'), 'EX_PROJECTION_PAYMENT_INTENT_REQUIRED', d['escrowId'])
                escrow.update(paymentStatus='settled',
                              status='released' if intent == 'release' else 'refunded')
                state['legs'][escrow['legIndex']].update(
                    fundingStatus=escrow['status'], rollbackStatus='detached' if intent == 'release' else 'returned')
        elif kind == 'rollback-opened':
            state['rollback'] = {key: d[key] for key in
                                 ('authorityId', 'boundaryIndex', 'boundaryAccount', 'affectedLegs')}
            state['rollback']['affectedLegs'] = list(d['affectedLegs'])
            state['rollback']['state'] = 'in-progress'
            for index in d['affectedLegs']:
                state['legs'][index]['rollbackStatus'] = 'in-progress'
        elif kind == 'rollback-advanced':
            state['rollback']['state'] = d['state']
        elif kind == 'asset-returned':
            state['owner'] = {'account': d['toAccount'], 'position': d['boundaryIndex']}
            state['assetReturnedByRollback'] = True
            for index in state['rollback']['affectedLegs']:
                leg = state['legs'][index]
                if d['operations'] == 0 or leg['rollbackStatus'] == 'in-progress':
                    leg['rollbackStatus'] = 'returned'
        elif kind == 'redemption-requested':
            state['exit'] = {'requestId': d['requestId'], 'requester': d['requester'],
                             'state': 'requested', 'burned': False,
                             'steps': {name: {'status': 'pending', 'completedAt': None}
                                       for name in d['plannedSteps']}}
        elif kind in ('exit-step-done', 'exit-step-blocked'):
            exit_state = state['exit']
            exit_state['steps'][d['step']] = {
                'status': 'done' if kind == 'exit-step-done' else 'blocked',
                'completedAt': d.get('completedAt')}
            statuses = [step['status'] for step in exit_state['steps'].values()]
            exit_state['state'] = ('complete' if all(s == 'done' for s in statuses)
                                   else 'blocked' if 'blocked' in statuses else 'in-progress')
            exit_state['burned'] = exit_state['steps'].get('burn', {}).get('status') == 'done'
        elif kind == 'receipt-burned':
            state['exit']['burned'] = True
    require(state is not None, 'EX_PROJECTION_MINT_REQUIRED', 'empty timeline')
    return state


def live(exchange, receipt_id):
    """Independent normalized view of current domain state for comparison."""
    receipt = exchange.receipt(receipt_id)
    state = _base(receipt_id, receipt.origin_account)
    state['owner'] = {'account': exchange.owner_of(receipt_id),
                      'position': exchange.owner_index(receipt_id)}
    state['holder'] = {'account': exchange.holder_of(receipt_id),
                       'position': exchange.holder_index(receipt_id)}
    state['recordedLegs'] = exchange.recorded_legs(receipt_id)
    state['legs'] = [{'legIndex': leg.leg_index, 'transferId': leg.transfer_id,
                      'registrationStatus': leg.registration_status,
                      'fundingStatus': leg.funding_status, 'rollbackStatus': leg.rollback_status}
                     for leg in exchange.legs(receipt_id)]
    state['assetReturnedByRollback'] = exchange._returned_to[receipt_id] is not None
    for escrow_id in exchange._escrow_by_leg[receipt_id].values():
        escrow = exchange.escrow(escrow_id)
        state['escrows'][escrow_id] = {
            'legIndex': escrow.leg_index, 'payer': escrow.payer, 'payee': escrow.payee,
            'quoteAsset': escrow.quote_asset, 'principal': str(escrow.principal),
            'status': escrow.status, 'paymentKey': escrow.payment_key,
            'paymentIntent': escrow.payment_intent, 'paymentStatus': escrow.payment_status}
    rollback = exchange._rollbacks[receipt_id]
    if rollback is not None:
        state['rollback'] = {key: rollback[key] for key in
                             ('authorityId', 'boundaryIndex', 'boundaryAccount', 'state')}
        state['rollback']['affectedLegs'] = list(rollback['affectedLegs'])
    exit_state = exchange._exits[receipt_id]
    if exit_state is not None:
        state['exit'] = {'requestId': exit_state['request'].request_id,
                         'requester': exit_state['request'].requester,
                         'state': exit_state['state'],
                         'steps': {step.name: {'status': step.status, 'completedAt': step.completed_at}
                                   for step in exit_state['steps']},
                         'burned': any(step.name == 'burn' and step.status == 'done'
                                       for step in exit_state['steps'])}
    return state
