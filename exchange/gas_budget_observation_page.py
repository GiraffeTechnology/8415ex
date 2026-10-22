"""Optional six-language observation of an original gas-budget snapshot.

No financial, journal, reservation, confirmation or transaction writes.
"""
from html import escape
from .gas_disclosure_locales import WORDS as DISCLOSURE_WORDS

KEYS = ("heading","cap","spent","pending","unused","proposal","closed","yes","no","unknown","unavailable","policy")
WORDS = {locale: {key: values["budget_" + key] for key in KEYS}
         for locale, values in DISCLOSURE_WORDS.items()}



def render_budget_observation(read_original_budget, quote, locale):
    """Read one installed snapshot port for the current original quote.

    The port returns GasBudgetBook.snapshot's dict, not a recovery-journal
    envelope, and remains responsible for original source/session binding.
    Optional observation failures cannot replace or block quote confirmation.
    Private identities, errors, source/journal details and extra fields are
    never rendered. This is not the standalone UNKNOWN recovery query.
    """
    w = WORDS[locale]
    heading = '<h3>' + escape(w["heading"]) + '</h3>'
    policy = '<p>' + escape(w["policy"]) + '</p>'
    def unavailable():
        return ('<section data-gas-budget-observation="unavailable">'
                + heading + '<p>' + escape(w["unavailable"]) + '</p>' + policy + '</section>')
    try:
        value = read_original_budget(quote.budget_id)
        if (type(value) is not dict or "unfreezeProposalWei" not in value
                or value.get("budgetId") != quote.budget_id
                or value.get("quoteDigest") != quote.digest
                or type(value.get("closed")) is not bool):
            return unavailable()
        names = ("capWei", "actualConsumedWei", "pendingBoundWei", "unusedWei")
        if any(type(value.get(key)) is not int or not 0 <= value[key] < 2**256
               for key in names):
            return unavailable()
        cap, spent, pending, unused = (value[key] for key in names)
        proposal, closed = value.get("unfreezeProposalWei"), value["closed"]
        if (cap != quote.cap_wei or spent + pending > cap or unused != cap - spent
                or (closed and (pending != 0 or type(proposal) is not int or proposal != unused))
                or (not closed and proposal is not None)):
            return unavailable()
    except Exception:
        return unavailable()
    rows = [
        (w["cap"], str(cap) + " ETH wei"), (w["spent"], str(spent) + " ETH wei"),
        (w["pending"], str(pending) + " ETH wei"), (w["unused"], str(unused) + " ETH wei"),
        (w["proposal"], w["unknown"] if proposal is None else str(proposal) + " ETH wei"),
        (w["closed"], w["yes"] if closed else w["no"]),
    ]
    return ('<section data-gas-budget-observation="recorded">' + heading + '<dl>'
            + ''.join('<dt>' + escape(key) + '</dt><dd>' + escape(text) + '</dd>'
                      for key, text in rows) + '</dl>' + policy + '</section>')
