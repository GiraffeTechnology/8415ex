"""Compose original receipt samples with an explicit existing gas quote."""
from copy import deepcopy

from .gas_budget import GasQuote, GasBudgetRefused
from .receipt_fee_samples import receipt_fee_samples, _label


ORIGINAL_QUOTE_FIELDS = frozenset((
    "quote_id", "version", "budget_id", "scope", "actions", "chain_id", "cap_wei",
    "window_start", "window_end", "quoted_at", "valid_until",
    "usd_micro_per_eth", "rate_observed_at", "rate_source", "rate_sha256",
))


def quote_from_original_receipts(population, *, original_quote_fields,
                                 verify_applicability):
    """Use exact host inputs; never choose cap, sample window, FX or actions.

    These are application-installed original inputs, not a public form schema.
    The original host authenticates cap/FX/action context. The existing receipt
    bridge authenticates the complete original population and its applicability.
    Neither structural consistency nor a fixture callback proves source authority.
    No reader, clock, policy, wallet confirmation or financial operation is made.
    """
    if (type(original_quote_fields) is not dict
            or set(original_quote_fields) != ORIGINAL_QUOTE_FIELDS):
        raise GasBudgetRefused("Complete explicit original quote fields required")
    captured = deepcopy(original_quote_fields)
    if type(captured["chain_id"]) is not int or captured["chain_id"] != 11155111:
        raise GasBudgetRefused("Original EX Sepolia quote required")
    for key in ("quote_id", "budget_id", "scope", "rate_source"):
        _label(captured[key])
    if type(captured["actions"]) is not tuple or not captured["actions"]:
        raise GasBudgetRefused("Original covered action tuple required")
    for action in captured["actions"]:
        _label(action)
    samples = receipt_fee_samples(population, scope=captured["scope"],
        window_start=captured["window_start"], window_end=captured["window_end"],
        verify_applicability=verify_applicability)
    # Existing GasQuote validates exact cap, P50, windows, validity and FX.
    # Never increase a cap or fill a missing field to make construction succeed.
    return GasQuote(samples=samples, **captured)
