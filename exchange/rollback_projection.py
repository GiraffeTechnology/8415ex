"""Identity-excluding rollback observation; never an asset or financial writer."""
from .public_workbench import integer, amount, currency, state


class RollbackProjectionRefused(ValueError):
    pass


TRIGGERS = {'registrar refusal for that leg': 'registrar-refusal',
            'trading deadline passed with the holder behind the owner': 'deadline'}


def rollback_projection(exchange, receipt_id, *, now=None):
    """Read original domain recovery without publishing journals or party fields.

    Principal and consumed ETH stay separate. A domain completion report never
    establishes actual Wallet, Oracle, native journal or chain acceptance.
    """
    view = exchange.receipt_view(receipt_id, now)
    observed = view.get('observedAt')
    if view.get('receiptId') != receipt_id or integer(observed) is None:
        raise RollbackProjectionRefused('original receipt observation required')
    report = exchange.rollback_report(receipt_id, observed)
    if (type(report) is not dict or report.get('receiptId') != receipt_id
            or report.get('observedAt') != observed or type(report.get('open')) is not bool):
        raise RollbackProjectionRefused('original rollback observation binding required')
    return _project_report(report, view)


def _project_report(report, view):
    observed = report['observedAt']
    result = {'schema': '8415ex-domain-rollback/1', 'open': report['open'],
              'registeredPrefixLegs': integer(view.get('registeredPrefixLegs')),
              'outstandingLegs': integer(view.get('outstandingLegs')),
              'holderPosition': integer(view.get('holder', {}).get('position')),
              'ownerPosition': integer(view.get('owner', {}).get('position')),
              'observedAt': observed, 'state': state(report.get('state')),
              'domainReportedComplete': report.get('complete') is True,
              'domainReportConsistent': True, 'trigger': 'unknown',
              'returnBoundaryPosition': None, 'assetReturned': False,
              'affectedLegs': [], 'outstandingSteps': [], 'funds': [],
              'retryPolicy': 'original-operation-enquiry-no-repeat',
              'consumedGasRefunded': False, 'nativeCompletionVerified': False,
              'chainAcceptance': 'NOT_RUN'}
    if not report['open']:
        if report.get('complete') is True:
            raise RollbackProjectionRefused('closed observation cannot claim an open recovery completion')
        return result
    affected = report.get('affectedLegs')
    steps = report.get('outstandingSteps')
    funds = report.get('funds')
    control = report.get('assetControl')
    if (type(affected) not in (tuple, list) or any(integer(i) is None for i in affected)
            or len(set(affected)) != len(affected) or type(steps) not in (tuple, list)
            or type(funds) not in (tuple, list) or type(control) is not dict
            or integer(report.get('lastFinalizedPosition')) is None):
        raise RollbackProjectionRefused('original recovery interval and reports required')
    result['affectedLegs'] = list(affected)
    trigger = report.get('trigger')
    result['trigger'] = TRIGGERS.get(trigger, 'unknown') if type(trigger) is str else 'unknown'
    result['returnBoundaryPosition'] = report['lastFinalizedPosition']
    result['assetReturned'] = control.get('returned') is True
    for entry in steps:
        if (type(entry) is not dict or integer(entry.get('legIndex')) is None
                or entry['legIndex'] not in set(affected) | {report['lastFinalizedPosition']}):
            raise RollbackProjectionRefused('original outstanding step position required')
        result['outstandingSteps'].append({
            'legIndex': entry['legIndex'],
            'kind': entry.get('kind') if entry.get('kind') in ('refund', 'asset-return') else 'unknown',
            'status': state(entry.get('status'))})
    seen = set()
    for entry in funds:
        if (type(entry) is not dict or integer(entry.get('legIndex')) is None
                or entry['legIndex'] + 1 >= 2**256
                or entry['legIndex'] not in affected or entry['legIndex'] in seen):
            raise RollbackProjectionRefused('original affected financial leg required')
        seen.add(entry['legIndex'])
        result['funds'].append({
            'legIndex': entry['legIndex'], 'buyerPosition': entry['legIndex'] + 1,
            'principal': amount(entry.get('principal')),
            'principalAsset': currency(entry.get('principalAsset')),
            'principalUnit': 'base-units' if entry.get('principalUnit') == 'base-units' else None,
            'escrowStatus': state(entry.get('escrowStatus')),
            'paymentStatus': state(entry.get('paymentStatus')),
            'refundedToOriginalBuyer': entry.get('refundedToOriginalBuyer') is True,
            'netToOriginalBuyer': amount(entry.get('netToOriginalBuyer')),
            'gasTotal': amount(entry.get('gasTotal')),
            'gasAsset': 'ETH' if entry.get('gasAsset') == 'ETH' else None,
            'gasUnit': 'wei' if entry.get('gasUnit') == 'wei' else None,
            'rollbackStatus': state(entry.get('rollbackStatus'))})
    if seen != set(affected):
        raise RollbackProjectionRefused('original affected financial observations incomplete')
    money_complete = all(row['escrowStatus'] == 'not-funded' or (
        row['escrowStatus'] == 'refunded' and row['refundedToOriginalBuyer']
        and row['principal'] is not None and row['principalAsset'] is not None
        and row['principalUnit'] == 'base-units'
        and row['netToOriginalBuyer'] == row['principal']) for row in result['funds'])
    result['domainReportConsistent'] = not result['domainReportedComplete'] or (
        result['state'] == 'complete' and result['assetReturned']
        and not result['outstandingSteps'] and money_complete)
    return result


def rollback_history_projection(exchange, receipt_id, *, observed_at=None):
    """Keep archived report time and funds; never attach today's positions."""
    reader = getattr(exchange, 'historical_rollbacks', None)
    if not callable(reader):
        return {'available': False, 'reports': []}
    if observed_at is None:
        view = exchange.receipt_view(receipt_id, None)
        if view.get('receiptId') != receipt_id:
            raise RollbackProjectionRefused('original history observation required')
        observed_at = view.get('observedAt')
    if integer(observed_at) is None:
        raise RollbackProjectionRefused('original history observation time required')
    reports = reader(receipt_id)
    if type(reports) not in (tuple, list):
        raise RollbackProjectionRefused('original archived reports required')
    result = []
    previous_time = None
    for report in reports:
        if (type(report) is not dict or report.get('receiptId') != receipt_id
                or report.get('historical') is not True or report.get('open') is not True
                or report.get('complete') is not True
                or integer(report.get('observedAt')) is None
                or report['observedAt'] > observed_at
                or (previous_time is not None and report['observedAt'] < previous_time)):
            raise RollbackProjectionRefused('original archived receipt and time binding required')
        previous_time = report['observedAt']
        # Archived reports carry the original registered-prefix count, but not
        # a full historical owner/holder view. Missing fields remain unknown.
        view = {'registeredPrefixLegs': report.get('finalizedPrefixLegs')}
        value = _project_report(report, view)
        value['historicalSnapshot'] = True
        result.append(value)
    return {'available': True, 'reports': result}
