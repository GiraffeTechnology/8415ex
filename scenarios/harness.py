"""Scenario definition, execution and recorded assertions.

A scenario records rather than asserts. Every expectation keeps its expected and
observed value side by side with the case identifiers it serves, so a report
shows what was actually checked and a mismatch survives as a genuine failure
instead of raising out of the run. The runner's exit status is derived from the
recorded results, so a failure cannot be silently lost.

Nothing here is real-execution evidence. Each run states its own scope.
"""
import time
from dataclasses import dataclass, field

from exchange.ids import canonical_json, digest

#: Every scenario result carries this, so a reader cannot mistake it for chain
#: or deployment evidence.
LOCAL_ONLY = ("local deterministic model run against the in-process domain API; "
              "simulated registrar, payment and asset-control adapters; "
              "no deployment, no transaction, no value movement")

OUTCOMES = ("passed", "failed", "blocked", "not-run")


@dataclass(frozen=True)
class Expectation:
    """One named check, with what was expected and what was seen."""

    name: str
    cases: tuple
    expected: object
    observed: object
    outcome: str
    detail: str = None

    @property
    def passed(self):
        return self.outcome == "passed"

    def as_record(self):
        return {"name": self.name, "cases": list(self.cases), "expected": _plain(self.expected),
                "observed": _plain(self.observed), "outcome": self.outcome, "detail": self.detail}


@dataclass(frozen=True)
class Step:
    """One executed scenario step and the facts observed right after it."""

    index: int
    name: str
    facts: dict

    def as_record(self):
        return {"index": self.index, "name": self.name, "facts": _plain(self.facts)}


def _plain(value):
    """Render a value for the canonical record, without floats or objects."""
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(item) for item in (sorted(value) if isinstance(value, (set, frozenset))
                                          else value)]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value) if abs(value) > 2 ** 53 else value
    return str(value)


class Recorder:
    """Collects a scenario's setup, steps and expectations while it runs."""

    def __init__(self, scenario_id, title, cases, main_path):
        self.scenario_id = scenario_id
        self.title = title
        self.cases = tuple(cases)
        self.main_path = main_path
        self.setup = {}
        self._steps = []
        self._expectations = []
        self._notes = []

    def describe_setup(self, **facts):
        """Initial receipt, accounts, deterministic prices and gas conditions."""
        self.setup.update(facts)
        return self.setup

    def step(self, name, **facts):
        step = Step(index=len(self._steps), name=name, facts=dict(facts))
        self._steps.append(step)
        return step

    def expect(self, name, cases, expected, observed, detail=None):
        """Record one check. A mismatch is kept, not raised."""
        outcome = "passed" if _plain(expected) == _plain(observed) else "failed"
        expectation = Expectation(name=name, cases=tuple(cases), expected=expected,
                                  observed=observed, outcome=outcome, detail=detail)
        self._expectations.append(expectation)
        return expectation

    def blocked(self, name, cases, reason):
        """Record a check that could not run, with the reason it could not."""
        expectation = Expectation(name=name, cases=tuple(cases), expected="executed",
                                  observed="blocked", outcome="blocked", detail=reason)
        self._expectations.append(expectation)
        return expectation

    def not_run(self, name, cases, reason):
        """Record an obligation this local run cannot discharge at all."""
        expectation = Expectation(name=name, cases=tuple(cases), expected="real execution evidence",
                                  observed="NOT_RUN", outcome="not-run", detail=reason)
        self._expectations.append(expectation)
        return expectation

    def note(self, text):
        self._notes.append(text)

    def result(self, started_at, finished_at, elapsed_ms, error=None):
        return ScenarioResult(scenario_id=self.scenario_id, title=self.title, cases=self.cases,
                              main_path=self.main_path, setup=dict(self.setup),
                              steps=tuple(self._steps), expectations=tuple(self._expectations),
                              notes=tuple(self._notes), started_at=started_at,
                              finished_at=finished_at, elapsed_ms=elapsed_ms, error=error)


@dataclass(frozen=True)
class ScenarioResult:
    """What one scenario run actually did."""

    scenario_id: str
    title: str
    cases: tuple
    main_path: str
    setup: dict
    steps: tuple
    expectations: tuple
    notes: tuple
    started_at: str
    finished_at: str
    elapsed_ms: int
    error: str = None

    def counts(self):
        counts = {outcome: 0 for outcome in OUTCOMES}
        for expectation in self.expectations:
            counts[expectation.outcome] += 1
        return counts

    @property
    def failures(self):
        return tuple(e for e in self.expectations if e.outcome == "failed")

    @property
    def passed(self):
        """True only when nothing failed, nothing is blocked, and it completed.

        A ``not-run`` obligation does not fail a local scenario: it is a real
        Stage 5 duty this run is not entitled to discharge, and it is reported
        as such rather than hidden or counted as a pass.
        """
        counts = self.counts()
        return (self.error is None and counts["failed"] == 0 and counts["blocked"] == 0
                and counts["passed"] > 0)

    def as_record(self):
        return {"scenarioId": self.scenario_id, "title": self.title, "cases": list(self.cases),
                "mainPath": self.main_path, "scope": LOCAL_ONLY, "setup": _plain(self.setup),
                "steps": [step.as_record() for step in self.steps],
                "expectations": [e.as_record() for e in self.expectations],
                "notes": list(self.notes), "counts": self.counts(), "passed": self.passed,
                "error": self.error, "startedAt": self.started_at,
                "finishedAt": self.finished_at, "elapsedMs": self.elapsed_ms}


@dataclass(frozen=True)
class Scenario:
    """A named, repeatable local scenario."""

    scenario_id: str
    title: str
    cases: tuple
    main_path: str
    body: object

    def run(self):
        recorder = Recorder(self.scenario_id, self.title, self.cases, self.main_path)
        started = time.time()
        started_at = _utc(started)
        error = None
        try:
            self.body(recorder)
        except Exception as problem:  # a genuine defect is recorded, never swallowed silently
            error = f"{type(problem).__name__}: {problem}"
        finished = time.time()
        return recorder.result(started_at, _utc(finished), int((finished - started) * 1000), error)


def _utc(stamp):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp))


def run_all(scenarios):
    """Run every scenario and return one report with a stable digest."""
    results = [scenario.run() for scenario in scenarios]
    totals = {outcome: 0 for outcome in OUTCOMES}
    for result in results:
        for outcome, count in result.counts().items():
            totals[outcome] += count
    report = {
        "schema": "8415ex-local-scenario-report/1",
        "scope": LOCAL_ONLY,
        "scenarios": [result.as_record() for result in results],
        "totals": totals,
        "scenariosPassed": sum(1 for result in results if result.passed),
        "scenariosTotal": len(results),
        "allPassed": all(result.passed for result in results),
    }
    # The digest covers everything except the wall-clock fields, so two runs of
    # the same source over the same fixtures compare equal.
    report["deterministicDigest"] = digest(_stable(report))
    return report


def _stable(report):
    """The report with wall-clock values removed, for the determinism digest."""
    drop = {"startedAt", "finishedAt", "elapsedMs"}

    def strip(node):
        if isinstance(node, dict):
            return {key: strip(value) for key, value in node.items() if key not in drop}
        if isinstance(node, list):
            return [strip(item) for item in node]
        return node

    return strip({key: value for key, value in report.items() if key != "deterministicDigest"})


def report_text(report):
    """A short human summary. The canonical record stays the JSON."""
    lines = [f"8415ex local scenario report - {report['scenariosPassed']}/"
             f"{report['scenariosTotal']} scenarios passed",
             f"scope: {report['scope']}"]
    for scenario in report["scenarios"]:
        counts = scenario["counts"]
        lines.append(f"  {scenario['scenarioId']} [{scenario['mainPath']}] "
                     f"{'PASS' if scenario['passed'] else 'FAIL'} "
                     f"passed={counts['passed']} failed={counts['failed']} "
                     f"blocked={counts['blocked']} not-run={counts['not-run']}")
        for expectation in scenario["expectations"]:
            if expectation["outcome"] in ("failed", "blocked"):
                lines.append(f"    {expectation['outcome'].upper()} {expectation['name']}: "
                             f"expected {expectation['expected']!r}, "
                             f"observed {expectation['observed']!r}")
        if scenario["error"]:
            lines.append(f"    ERROR {scenario['error']}")
    totals = report["totals"]
    lines.append(f"totals: passed={totals['passed']} failed={totals['failed']} "
                 f"blocked={totals['blocked']} not-run={totals['not-run']}")
    lines.append(f"deterministic digest: {report['deterministicDigest']}")
    return "\n".join(lines)
