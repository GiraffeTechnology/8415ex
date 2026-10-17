"""Confirmed quote revisions preserve the original operation's actual spend."""
from dataclasses import dataclass
from .gas_budget import (GasBudgetBook, GasBudgetRefused, GasQuote,
                         BuyerConfirmation, GasFreeze, _integer, _text)


@dataclass(frozen=True)
class GasAdjustment:
    adjustment_id: str
    budget_id: str
    previous_quote_digest: str
    new_quote_digest: str
    buyer: str
    chain_id: int
    actual_consumed_wei: int
    effective_frozen_wei: int
    previous_freeze_reference: str
    new_freeze_reference: str
    status: str
    account_kind: str = 'GAS_PREPAYMENT'


class RevisableGasBudgetBook(GasBudgetBook):
    """Serialized in-memory projection extension, pinned to its parent contract.

    The verifier must authenticate actual wallet adjustment and cumulative debit
    facts. This method never tops up, debits, releases or sends itself.
    """
    def revise(self, budget_id, quote, confirmation, adjustment, now):
        if not (isinstance(quote, GasQuote) and isinstance(confirmation, BuyerConfirmation)
                and isinstance(adjustment, GasAdjustment)):
            raise GasBudgetRefused('typed revised quote, confirmation and adjustment required')
        row = self._budgets[budget_id]
        _integer(now)
        for value in (adjustment.adjustment_id, adjustment.previous_freeze_reference,
                      adjustment.new_freeze_reference, confirmation.proof_reference):
            _text(value)
        _integer(adjustment.actual_consumed_wei)
        _integer(adjustment.effective_frozen_wei)
        old = row['quote']
        prior = row['confirmation']
        revision_identity = (quote.digest, confirmation, adjustment)
        if row.get('lastRevisionIdentity') == revision_identity:
            return self.snapshot(budget_id)
        if row['closed'] or row['attempts']:
            raise GasBudgetRefused('closed or unresolved attempts prohibit budget revision')
        if (quote.budget_id != budget_id or quote.scope != old.scope
                or quote.actions != old.actions or quote.chain_id != old.chain_id
                or quote.version <= old.version or quote.quoted_at < old.quoted_at):
            raise GasBudgetRefused('revision must preserve operation, coverage and increasing version')
        if (confirmation.buyer != prior.buyer or confirmation.action_digest != prior.action_digest
                or confirmation.wallet_grant != prior.wallet_grant
                or confirmation.quote_digest != quote.digest
                or type(confirmation.confirmed_at) is not int
                or not quote.quoted_at <= confirmation.confirmed_at <= now < quote.valid_until):
            raise GasBudgetRefused('fresh buyer confirmation under original grant required')
        if (adjustment.budget_id != budget_id or adjustment.buyer != prior.buyer
                or adjustment.chain_id != quote.chain_id
                or adjustment.previous_quote_digest != old.digest
                or adjustment.new_quote_digest != quote.digest
                or adjustment.previous_freeze_reference != row['freeze'].wallet_reference
                or adjustment.status != 'APPLIED' or adjustment.account_kind != 'GAS_PREPAYMENT'
                or adjustment.actual_consumed_wei != row['spent']
                or quote.cap_wei < row['spent']
                or adjustment.effective_frozen_wei != quote.cap_wei - row['spent']):
            raise GasBudgetRefused('effective adjusted gas freeze and preserved spend required')
        self._verified('buyer-confirmation', confirmation)
        self._verified('gas-budget-adjustment', adjustment)
        frozen = GasFreeze(budget_id, prior.buyer, quote.chain_id,
            adjustment.effective_frozen_wei, quote.digest,
            adjustment.new_freeze_reference, 'FROZEN')
        row.setdefault('revisions', []).append({'previous': old.digest, 'next': quote.digest,
            'consumedWei': row['spent'], 'adjustmentId': adjustment.adjustment_id})
        row['quote'] = quote
        row['confirmation'] = confirmation
        row['freeze'] = frozen
        row['identity'] = (quote.digest, confirmation, frozen)
        row['lastRevisionIdentity'] = revision_identity
        return self.snapshot(budget_id)
