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

Module-level functions were once outside this report, because a caller that
wrote ``from .errors import require`` holds the original function and replacing
the defining module's attribute observes nothing. That is a reason to look in
the right place, not a reason to leave twelve domain functions uncounted: the
call reaches the function through the name the *caller's* module holds, so every
binding of it in the project's own modules is replaced. All of them are, and all
twelve are entered.

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
import sys

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

#: Domain modules whose own public functions are counted. A function is reached
#: through the name its caller holds, so these are the modules the functions are
#: defined in, not the modules that call them.
FUNCTION_MODULES = (
    "exchange.ids",
    "exchange.errors",
    "exchange.settlement",
    "exchange.rollback",
    "exchange.registration",
    "exchange.exit",
)

#: Top-level packages whose modules may hold a binding that matters. A call from
#: outside the project cannot reach the domain in this run, and searching every
#: loaded module would also reach this measurement's own bookkeeping.
BINDING_NAMESPACES = ("exchange", "scenarios", "integration")

#: Imported so the reuse map sees these dependencies rather than having them
#: hidden behind a string. The names resolved below are these same classes.
_IMPORTED = (Exchange, SimulatedPaymentAdapter, SimulatedAssetControl,
             SimulatedRegistrar, DirectRegistrar, ElectronicRegistrar,
             IntermediaryRegistrar, SimulatedVoucherDesk)

#: What this measurement cannot observe, and why. Stated so the absence is a
#: known limit rather than a silently narrower count.
NOT_MEASURED = {
    "inherited methods": "wrapping one sets the wrapper on the subclass and shadows "
                         "the base, so the base would read as unentered whatever the "
                         "delivery did; only methods a class defines itself are "
                         "counted, and an override is counted on the class that "
                         "defines it",
    "a function held somewhere other than a module global": "a reference taken into "
        "a list, a dict, a default argument or a local alias before the run is not "
        "reached by replacing module bindings, so a function called only that way "
        "would read as unentered",
    "anything outside the counted subjects and modules": "the domain's record "
        "classes and the fixtures are not counted, because they are scaffolding or "
        "data rather than behaviour this delivery has to demonstrate",
}

#: Methods this delivery does not enter, with the reason. An unentered method is
#: accounted for here or it is a finding; it is never simply absent from the
#: count.
NOT_EXERCISED_LOCALLY = {
    "exchange.ledger.Exchange.order_book_view":
        "the legacy scenario groups do not request terminal order-book observations; "
        "integration.test_public_order_book.PublicOrderBook exercises this read separately "
        "and scenarios.operations checks its no-movement rule, neither counted as "
        "entered by this instrumented scenario run",
    "exchange.ledger.Exchange.record_prepared_registration_request":
        "the original aggregate host persists prepared task correlation; "
        "this scenario run does not bind that writer and does not count its method as exercised",
    "exchange.ledger.Exchange.confirm_retired_asset_recovery":
        "the legacy scenario groups do not install a remint generation verifier; "
        "retired-generation recovery is exercised separately by domain tests, "
        "not counted as entered by this scenario run",
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


def functions():
    """Every own public function of every counted module, with the object."""
    found = []
    for path in FUNCTION_MODULES:
        module = importlib.import_module(path)
        for name, value in sorted(vars(module).items()):
            if name.startswith("_") or not inspect.isfunction(value):
                continue
            if value.__module__ != path:
                continue
            found.append(("%s.%s" % (path, name), value))
    return tuple(found)


def _binding_holders():
    """Project modules that may hold a reference to a counted function."""
    return [module for name, module in list(sys.modules.items())
            if module is not None
            and name.split(".")[0] in BINDING_NAMESPACES]


def _instrumented(groups, runner):
    """Run the groups with every counted name recording that it was entered.

    Everything is restored whatever happens. Leaving one wrapped would make
    every later report in the same process describe an instrumented domain
    rather than the real one.
    """
    counted_methods = methods()
    counted_functions = functions()
    entered = set()
    restore = [(subject, name, subject.__dict__[name])
               for _, subject, name in counted_methods]

    def wrap(label, original):
        @functools.wraps(original)
        def record(*arguments, **keywords):
            entered.add(label)
            return original(*arguments, **keywords)
        return record

    reports = []
    try:
        for label, subject, name in counted_methods:
            setattr(subject, name, wrap(label, subject.__dict__[name]))
        # A function is reached through the name its caller holds, so every
        # binding of the object in the project's own modules is replaced,
        # including the one in the module that defines it.
        for label, original in counted_functions:
            replacement = wrap(label, original)
            for module in _binding_holders():
                for name, value in list(vars(module).items()):
                    if value is original:
                        restore.append((module, name, original))
                        setattr(module, name, replacement)
        for group in groups:
            reports.append(runner(list(group)))
    finally:
        for holder, name, original in restore:
            setattr(holder, name, original)
    return ([label for label, _, _ in counted_methods],
            [label for label, _ in counted_functions], entered, reports)


def coverage(groups, runner):
    """Which of the subjects' own public methods this delivery enters.

    ``groups`` are the scenario groups and ``runner`` is the harness runner,
    both passed in rather than imported, so this module does not import the
    command line's own dependencies back and load them twice.
    """
    method_names, function_names, entered, reports = _instrumented(groups, runner)
    names = method_names + function_names
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
    for path in SUBJECTS + FUNCTION_MODULES:
        own = [name for name in names if name.startswith(path + ".")
               and name.count(".") == path.count(".") + 1]
        per_subject.append({
            "subject": path,
            "kind": "class" if path in SUBJECTS else "module",
            "methodCount": len(own),
            "exercisedCount": sum(1 for name in own if name in entered),
            "notExercised": [name for name in own if name not in entered],
        })
    return {
        "schema": "8415ex-domain-surface-coverage/3",
        "subjects": list(SUBJECTS),
        "functionModules": list(FUNCTION_MODULES),
        "bindingNamespaces": list(BINDING_NAMESPACES),
        "perSubject": per_subject,
        "counted": names,
        "countedCount": len(names),
        "methods": method_names,
        "methodCount": len(method_names),
        "functions": function_names,
        "functionCount": len(function_names),
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
            "not a count over everything the domain exposes: the record classes, "
            "the fixtures, inherited methods and a function held outside a module "
            "global are not counted, and each limit is named in notMeasured with "
            "the reason rather than quietly left out",
        ],
    }
