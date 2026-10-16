"""Whether the record that leaves this run agrees with itself.

Every report in the bundle is built from the same run, so they must say the same
thing about it. Twice now they have not, and both times for the same reason: a
report rebuilt at sealing time with fewer inputs than it was first built with.
The first time the artifact leg was dropped from the index; the second time the
guarantee contracts were, so the published index said ten cases were evidenced
only by the domain's own suite while the matrix in the same bundle said they
passed. A reviewer reads the published record, not the bundle that existed
mid-run, so a contradiction there is the worst kind: it is the copy that counts.

Each time the fix was a parameter, passed more carefully. ``seal`` even carries a
comment recording the first lesson, and the second mistake was made under it.
What was missing is a check that compares the finished record with itself and
refuses a contradiction, whatever caused it.

Nothing here re-runs anything or recomputes a verdict. It reads the bundle and
compares what the bundle already says, which is the only way to catch a report
that silently lost an input: the inputs are gone by then, and the disagreement
is all that is left to see.

Most comparisons here are between two copies of the same fact. One is not: the
verdict against the blocking list. It was written, dropped as a restatement of
how both places derive the verdict from that list, and restored when the very
next run proved the reasoning wrong - the publication stage recomputes the
verdict from its own factors and then appends to the list, so the two really can
disagree, and nothing else was watching. A report that fabricates a verdict to
exercise its own rendering has to clear the list to mean what it says.

What this is not: a check that the reports are right. Two reports can agree and
both be wrong, and that is what the acceptance matrix, the consistency gates and
the suites are for. This one only establishes that the published record does not
contradict itself.
"""
SCENARIO_REPORT_SCHEMA = "8415ex-local-scenario-report/1"


def scenario_reports(bundle):
    """Every scenario report the bundle carries, found by its schema.

    Discovered rather than listed. A list of report keys is exactly what the
    rebuilds got wrong, so this check cannot be allowed to depend on one: a
    report added to the bundle and left out of a rebuild has to be visible here
    without anyone remembering to name it.
    """
    return {key: value for key, value in sorted(bundle.items())
            if isinstance(value, dict)
            and value.get("schema") == SCENARIO_REPORT_SCHEMA}


def _rows(report):
    return {row["case"]: row for row in (report or {}).get("rows", [])}


def _compare(comparison, expected, observed, meaning, detail=None):
    agrees = expected == observed
    return {
        "comparison": comparison,
        "agrees": agrees,
        "expected": expected,
        "observed": observed,
        "meaning": meaning,
        "detail": detail,
    }


def _case_comparisons(bundle):
    """What the matrix and the published index say about each case.

    A comparison is only made where both sides are present. One side missing
    entirely is reported by ``comparability`` instead: comparing a report with
    an absent one would read as a contradiction when the truth is that there
    was nothing to compare.
    """
    matrix_rows = _rows(bundle.get("matrix"))
    index_rows = _rows(bundle.get("evidenceIndex"))
    if not matrix_rows or not index_rows:
        return
    shared = sorted(set(matrix_rows) & set(index_rows))
    yield _compare(
        "the index covers the same cases as the matrix",
        sorted(matrix_rows), sorted(index_rows),
        "a case in one and not the other is a record with two different scopes")
    yield _compare(
        "each case has one local outcome, not two",
        {case: matrix_rows[case]["localOutcome"] for case in shared},
        {case: index_rows[case]["localOutcome"] for case in shared},
        "this is the contradiction a rebuilt index produced twice: the matrix "
        "saying passed while the index said the case had only unit coverage")
    yield _compare(
        "each case names the same runners in both",
        {case: sorted(matrix_rows[case]["scenarios"]) for case in shared},
        {case: sorted(index_rows[case]["scenarios"]) for case in shared},
        "a reviewer finds the evidence through these names, so they cannot "
        "differ between the two places that carry them")
    yield _compare(
        "each case has the same assertion counts in both",
        {case: dict(matrix_rows[case]["scenarioAssertionCounts"])
         for case in shared if matrix_rows[case]["scenarioAssertionCounts"]},
        {case: dict(index_rows[case]["assertionOutcomes"])
         for case in shared if matrix_rows[case]["scenarioAssertionCounts"]},
        "counts that fell to zero in the published copy are how the dropped "
        "report showed itself the second time")


def _run_comparisons(bundle):
    """What the bundle says about the run as a whole."""
    reports = scenario_reports(bundle)
    recorded = sorted(scenario["scenarioId"]
                      for report in reports.values()
                      for scenario in report.get("scenarios", []))
    index = bundle.get("evidenceIndex") or {}
    indexed = sorted(entry["runner"] for entry in index.get("runners", []))
    if reports and index.get("runners") is not None:
        yield _compare(
            "every runner this run recorded is in the published index",
            recorded, indexed,
            "a whole report dropped from the rebuild disappears here first",
            detail="%d scenario reports in the bundle" % len(reports))
    if "runnerCount" in index:
        yield _compare(
            "the index counts the runners it lists",
            len(indexed), index["runnerCount"],
            "a count that disagrees with its own list is not a count")
    if reports and bundle.get("workload") is not None:
        yield _compare(
            "every scenario report has a workload observation",
            len(reports), len(bundle["workload"]),
            "a group that ran without being observed is a group whose cost and "
            "outcome rates are missing from the record",
            detail="reports: %s" % ", ".join(sorted(reports)))
    if bundle.get("scenarioReport") and bundle.get("evidence"):
        yield _compare(
            "the sealed evidence names this run's scenario digest",
            bundle["scenarioReport"].get("deterministicDigest"),
            bundle["evidence"].get("scenarioDigest"),
            "a sealed record pointing at another run's digest is evidence about "
            "something else")
    if (bundle.get("manifest") or {}).get("commands") is not None:
        yield _compare(
            "the manifest carries the same commands as the bundle",
            list(bundle.get("commands") or []),
            list(bundle["manifest"]["commands"]),
            "sealing writes both, so they are one list recorded twice")
    if bundle.get("blocking") is not None and "allLocalPassed" in bundle:
        yield _compare(
            "the verdict matches the blocking items",
            bundle["blocking"] == [], bundle["allLocalPassed"],
            "a pass with a blocking item, or a failure with none, is the record "
            "disagreeing with its own conclusion; the publication stage derives "
            "the verdict from its own factors rather than from this list, so "
            "the two can differ",
            detail="; ".join(bundle["blocking"]) or None)
    if bundle.get("matrix") and index:
        yield _compare(
            "the same cases are unsound in both",
            sorted(bundle["matrix"].get("unsoundCases") or []),
            sorted(index.get("unsoundCases") or []),
            "an unsound case visible in one copy and not the other is a reader "
            "reaching the opposite conclusion from the same run")


def comparability(bundle):
    """What this record carries to be compared, and what is missing.

    Nothing to compare is not agreement, and it is also not a contradiction. A
    recorded bundle from an earlier run may legitimately carry no scenario
    reports at all, while a run that just executed them and carries none is
    wrong in a way this module cannot diagnose. So the two are kept apart: the
    absence is reported here, and whether it is acceptable is decided by the
    caller, which knows whether a run just happened.
    """
    missing = []
    if not scenario_reports(bundle):
        missing.append("no scenario report")
    if not (bundle.get("evidenceIndex") or {}).get("runners"):
        missing.append("no indexed runners")
    if not _rows(bundle.get("matrix")):
        missing.append("no matrix rows")
    return {"comparable": not missing, "missing": missing}


def check(bundle):
    """Compare the finished record with itself.

    Call this on the sealed bundle: before sealing, the published copies of the
    reports do not exist yet, and they are the copies a reviewer reads.
    """
    comparisons = list(_case_comparisons(bundle)) + list(_run_comparisons(bundle))
    disagreements = [entry["comparison"] for entry in comparisons
                     if not entry["agrees"]]
    available = comparability(bundle)
    return {
        "schema": "8415ex-bundle-self-agreement/2",
        "comparisons": comparisons,
        "comparisonCount": len(comparisons),
        "disagreements": disagreements,
        "scenarioReportsFound": sorted(scenario_reports(bundle)),
        "comparable": available["comparable"],
        "nothingToCompare": available["missing"],
        "consistent": not disagreements,
        "why": ("a report rebuilt with fewer inputs than it was built with has "
                "produced a self-contradicting published record twice; the "
                "inputs are gone by then, so the disagreement is what is left "
                "to see"),
        "isNot": [
            "not a check that the reports are right: two reports can agree and "
            "both be wrong, which is what the matrix, the gates and the suites "
            "are for",
            "not a re-run and not a recomputation: it reads what the bundle "
            "already says",
            "not a claim that there was anything to compare: consistent means no "
            "contradiction was found, and comparable says whether a comparison "
            "was possible at all, because a record carrying no reports agrees "
            "with nothing",
        ],
    }
