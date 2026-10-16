"""How much of the domain's own API this delivery actually exercises.

The acceptance matrix answers coverage per requirement. It does not answer the
other question a reviewer asks: of the methods the domain exposes, which ones
has this delivery ever called? That was unanswered, and measuring it turned up
five public methods that no scenario, route contract or guarantee had ever
reached - batch settlement, a restart's payment enquiry, a late registration
conflict, the deadline boundary and redemption readiness. Four of the five were
recovery and boundary behaviour, which is the part of a system a reviewer most
wants demonstrated.

The measurement is a measurement, not a source scan. The methods are wrapped,
the contract groups are run, and the set of methods that were actually entered
is recorded. A name appearing in a source file proves nothing about it being
called; being called is the claim, so being called is what is observed.

This is a second, instrumented execution of the same groups. Its scenario
results are discarded: the reported run, its digest and its resource
observation all come from the primary execution, and this one exists only to
record which methods it entered.

What this is not: a statement that a method is correct, or that its behaviour is
demonstrated well. It says the delivery enters it. Whether what it then records
is enough is the acceptance matrix's question, and the matrix answers it per
case.
"""
import functools
import inspect

from exchange.ledger import Exchange

#: The class this report speaks for: the domain API the logical operations are
#: resolved onto. The adapters and the module-level helpers are other surfaces'
#: to account for, and claiming them here would be a number rather than an
#: answer.
SUBJECT = "exchange.ledger.Exchange"

#: Public methods this delivery does not exercise, with the reason. An
#: unexercised method is accounted for here or it is a finding; it is never
#: simply absent from the count.
NOT_EXERCISED_LOCALLY = {}


def public_methods():
    """Every public method of the subject, read from the class itself."""
    return tuple(sorted(name for name, value
                        in inspect.getmembers(Exchange, inspect.isfunction)
                        if not name.startswith("_")))


def _instrumented(groups, runner):
    """Run the groups with every public method recording that it was entered.

    The class is restored whatever happens. Leaving it wrapped would make every
    later report in the same process describe an instrumented domain rather than
    the real one.
    """
    names = public_methods()
    entered = set()
    originals = {name: getattr(Exchange, name) for name in names}

    def wrap(name, original):
        @functools.wraps(original)
        def record(self, *arguments, **keywords):
            entered.add(name)
            return original(self, *arguments, **keywords)
        return record

    reports = []
    try:
        for name in names:
            setattr(Exchange, name, wrap(name, originals[name]))
        for group in groups:
            reports.append(runner(list(group)))
    finally:
        for name in names:
            setattr(Exchange, name, originals[name])
    return names, entered, reports


def coverage(groups, runner):
    """Which of the subject's public methods this delivery enters.

    ``groups`` are the scenario groups and ``runner`` is the harness runner,
    both passed in rather than imported, so this module does not import the
    command line's own dependencies back and load them twice.
    """
    names, entered, reports = _instrumented(groups, runner)
    unexercised = sorted(name for name in names if name not in entered)
    unaccounted = sorted(name for name in unexercised
                         if name not in NOT_EXERCISED_LOCALLY)
    stale = sorted(name for name in NOT_EXERCISED_LOCALLY
                   if name not in unexercised)
    unknown = sorted(name for name in NOT_EXERCISED_LOCALLY if name not in names)
    # A measurement taken over a run that did not pass measures the wrong thing:
    # a scenario that stopped early never reaches the methods it would have.
    all_passed = all(report["allPassed"] for report in reports) and bool(reports)
    return {
        "schema": "8415ex-domain-surface-coverage/1",
        "subject": SUBJECT,
        "publicMethods": list(names),
        "publicMethodCount": len(names),
        "exercised": sorted(entered),
        "exercisedCount": len(entered),
        "notExercised": unexercised,
        "notAccountedFor": unaccounted,
        "accountedForWithoutBeingExercised": dict(NOT_EXERCISED_LOCALLY),
        "staleExemptions": stale,
        "exemptionsNamingNoMethod": unknown,
        "instrumentedRunPassed": all_passed,
        "groupsRun": len(reports),
        "everyMethodAccountedFor": (all_passed and not unaccounted and not stale
                                    and not unknown),
        "basis": ("measured: each public method was wrapped and the contract groups "
                  "were run, so this records the methods the delivery entered rather "
                  "than the names its source mentions"),
        "isNot": [
            "not the reported run: this is a second, instrumented execution and its "
            "scenario results are discarded, so the run digest and the resource "
            "observation come from the primary execution",
            "not a correctness claim: entering a method says nothing about what it "
            "then did, which is the acceptance matrix's question, per case",
            "not a claim about other surfaces: only this one class is counted, "
            "because the adapters and the module-level helpers are not this "
            "report's to account for",
        ],
    }
