"""How much of the domain's own API this delivery enters.

The acceptance matrix answers coverage per requirement. It does not answer the
other question a reviewer asks: of the methods the domain exposes, which ones
has this delivery ever called? That was unanswered, and measuring it found five
public methods of the ledger that nothing had ever reached - batch settlement, a
restart's payment enquiry, a late registration conflict, the deadline boundary
and redemption readiness - all of them with passing cases, because the domain's
own suite covered them.

Widening the measurement to the simulated adapters found four more, and they
were the same kind of thing: the enquiry surface. Every adapter role here stands
in for an interface whose defining property is that it can be asked what
happened, and no history was ever read, nor an unknown asset return or voucher
outcome ever resolved. An enquiry surface nothing exercises is the part of a
simulation most likely to be wrong when a real adapter replaces it.

The measurement is a measurement, not a source scan. The methods are wrapped,
the contract groups are run, and the set of methods actually entered is
recorded. A name appearing in a source file proves nothing about it being
called; being called is the claim, so being called is what is observed.

Only methods a class defines itself are counted. Wrapping an inherited method
would set the wrapper on the subclass, shadowing the base and making the base
look unentered while the subclass's own entry looked covered - a measurement
artifact rather than a fact about the delivery.

Module-level functions are deliberately not measured this way, and the reason is
worth stating rather than leaving as an unexplained absence: a caller that wrote
``from .errors import require`` holds the original function, so replacing the
module attribute observes nothing and every such function would read as
unentered. A measurement that cannot be made is reported as not attempted, never
as a result.

This is a second, instrumented execution of the same groups. Its scenario
results are discarded: the reported run, its digest and its resource observation
all come from the primary execution, and this one exists only to record which
methods it entered.

What this is not: a statement that a method is correct, or that its behaviour is
demonstrated well. It says the delivery enters it. Whether what it then records
is enough is the acceptance matrix's question, and the matrix answers it per
case.
"""
import functools
import importlib
import inspect

from exchange.exit import SimulatedVoucherDesk
from exchange.ledger import Exchange
from exchange.registration import (DirectRegistrar, ElectronicRegistrar,
                                   IntermediaryRegistrar, SimulatedRegistrar)
from exchange.rollback import SimulatedAssetControl
from exchange.settlement import SimulatedPaymentAdapter

#: The classes this report speaks for: the domain API the logical operations are
#: resolved onto, and every simulated adapter standing in for a real interface.
#: They are named as import paths and resolved, so the report says exactly what
#: it counted.
SUBJECTS = (
    "exchange.ledger.Exchange",
    "exchange.settlement.SimulatedPaymentAdapter",
    "exchange.rollback.SimulatedAssetControl",
    "exchange.registration.SimulatedRegistrar",
    "exchange.registration.DirectRegistrar",
    "exchange.registration.ElectronicRegistrar",
    "exchange.registration.IntermediaryRegistrar",
    "exchange.exit.SimulatedVoucherDesk",
)

#: Imported so the reuse map sees these dependencies rather than having them
#: hidden behind a string. The names resolved below are these same classes.
_IMPORTED = (Exchange, SimulatedPaymentAdapter, SimulatedAssetControl,
             SimulatedRegistrar, DirectRegistrar, ElectronicRegistrar,
             IntermediaryRegistrar, SimulatedVoucherDesk)

#: What this measurement cannot observe, and why. Stated so the absence is a
#: known limit rather than a silently narrower count.
NOT_MEASURED = {
    "module-level functions": "a caller that imported the function by name holds "
                              "the original, so replacing the module attribute "
                              "observes nothing and every such function would read "
                              "as unentered",
    "inherited methods": "wrapping one sets the wrapper on the subclass and shadows "
                         "the base, so the base would read as unentered whatever the "
                         "delivery did",
}

#: Methods this delivery does not enter, with the reason. An unentered method is
#: accounted for here or it is a finding; it is never simply absent from the
#: count.
NOT_EXERCISED_LOCALLY = {
    "exchange.registration.SimulatedRegistrar.handover_record":
        "every concrete registrar defines its own hand-over record, so the base "
        "class's default is on no path this delivery can take; the three "
        "overriding versions are each entered",
}


def _subject(path):
    """The class one subject names."""
    module, _, name = path.rpartition(".")
    return getattr(importlib.import_module(module), name)


def methods():
    """Every own public method of every subject, read from the classes."""
    found = []
    for path in SUBJECTS:
        subject = _subject(path)
        for name, value in sorted(subject.__dict__.items()):
            if name.startswith("_") or not inspect.isfunction(value):
                continue
            found.append(("%s.%s" % (path, name), subject, name))
    return tuple(found)


def _instrumented(groups, runner):
    """Run the groups with every counted method recording that it was entered.

    The classes are restored whatever happens. Leaving one wrapped would make
    every later report in the same process describe an instrumented domain
    rather than the real one.
    """
    counted = methods()
    entered = set()
    restore = [(subject, name, subject.__dict__[name])
               for _, subject, name in counted]

    def wrap(label, original):
        @functools.wraps(original)
        def record(*arguments, **keywords):
            entered.add(label)
            return original(*arguments, **keywords)
        return record

    reports = []
    try:
        for label, subject, name in counted:
            setattr(subject, name, wrap(label, subject.__dict__[name]))
        for group in groups:
            reports.append(runner(list(group)))
    finally:
        for subject, name, original in restore:
            setattr(subject, name, original)
    return [label for label, _, _ in counted], entered, reports


def coverage(groups, runner):
    """Which of the subjects' own public methods this delivery enters.

    ``groups`` are the scenario groups and ``runner`` is the harness runner,
    both passed in rather than imported, so this module does not import the
    command line's own dependencies back and load them twice.
    """
    names, entered, reports = _instrumented(groups, runner)
    unexercised = [name for name in names if name not in entered]
    unaccounted = [name for name in unexercised
                   if name not in NOT_EXERCISED_LOCALLY]
    stale = sorted(name for name in NOT_EXERCISED_LOCALLY
                   if name not in unexercised)
    unknown = sorted(name for name in NOT_EXERCISED_LOCALLY if name not in names)
    # A measurement taken over a run that did not pass measures the wrong thing:
    # a scenario that stopped early never reaches the methods it would have.
    all_passed = all(report["allPassed"] for report in reports) and bool(reports)
    per_subject = []
    for path in SUBJECTS:
        own = [name for name in names if name.startswith(path + ".")]
        per_subject.append({
            "subject": path,
            "methodCount": len(own),
            "exercisedCount": sum(1 for name in own if name in entered),
            "notExercised": [name for name in own if name not in entered],
        })
    return {
        "schema": "8415ex-domain-surface-coverage/2",
        "subjects": list(SUBJECTS),
        "perSubject": per_subject,
        "methods": names,
        "methodCount": len(names),
        "exercised": sorted(entered),
        "exercisedCount": len(entered),
        "notExercised": unexercised,
        "notAccountedFor": unaccounted,
        "accountedForWithoutBeingExercised": dict(NOT_EXERCISED_LOCALLY),
        "staleExemptions": stale,
        "exemptionsNamingNoMethod": unknown,
        "notMeasured": dict(NOT_MEASURED),
        "instrumentedRunPassed": all_passed,
        "groupsRun": len(reports),
        "everyMethodAccountedFor": (all_passed and not unaccounted and not stale
                                    and not unknown),
        "basis": ("measured: each counted method was wrapped and the contract groups "
                  "were run, so this records the methods the delivery entered rather "
                  "than the names its source mentions"),
        "isNot": [
            "not the reported run: this is a second, instrumented execution and its "
            "scenario results are discarded, so the run digest and the resource "
            "observation come from the primary execution",
            "not a correctness claim: entering a method says nothing about what it "
            "then did, which is the acceptance matrix's question, per case",
            "not a count over everything the domain exposes: module-level functions "
            "and inherited methods cannot be observed this way, and each is named in "
            "notMeasured with the reason rather than quietly left out",
        ],
    }
