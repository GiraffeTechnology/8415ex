"""Verify and load the current repository product contract, without domain execution."""
import argparse
import hashlib
import json
import pathlib
import sys

VERSION = "1.2"
LEGACY_DEMOS = tuple("DEMO-%02d" % n for n in range(1, 7))


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate product-contract key: " + key)
        result[key] = value
    return result


def _json(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)


def load(root=None):
    root = pathlib.Path(root) if root is not None else pathlib.Path(__file__).resolve().parents[1]
    lock = _json((root / "config/prd-lock.json").read_bytes())
    if lock.get("schema") != "8415ex-prd-lock/1" or lock.get("version") != VERSION:
        raise ValueError("current PRD version pin is missing or stale")
    payloads = {}
    for key, expected_path in (("prd", "PRD.md"), ("executionPlan", "config/execution-plan.json")):
        item = lock[key]
        if item.get("path") != expected_path:
            raise ValueError("unexpected product-contract path")
        raw = (root / expected_path).read_bytes()
        if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("product-contract byte identity mismatch: " + expected_path)
        payloads[key] = raw
    plan = _json(payloads["executionPlan"])
    if plan.get("schema") != "8415ex-execution-plan/1" or plan.get("version") != VERSION:
        raise ValueError("execution plan is from a different PRD version")
    for key, expected in (
        ("cases", {"T-%02d" % n for n in range(1, 52)}),
        ("decisions", {"D-%02d" % n for n in range(1, 14)}),
        ("demonstrations", set(LEGACY_DEMOS)), ("stages", set(range(6))),
    ):
        ids = [entry["id"] for entry in plan[key]]
        if len(ids) != len(set(ids)) or set(ids) != expected:
            raise ValueError("incomplete or duplicated current contract: " + key)
    if plan["sections"] != list(range(1, 22)):
        raise ValueError("the full 21-section contract is required")
    declared = [entry["id"] for entry in plan["requirements"]]
    if len(declared) != 77 or len(declared) != len(set(declared)):
        raise ValueError("incomplete or duplicated requirement ledger")
    if any(not set(case["requirementIds"]) <= set(declared) for case in plan["cases"]):
        raise ValueError("case refers to undeclared requirement")
    if any(item.get("executable") is not False for item in plan["retiredRequirements"]):
        raise ValueError("retired requirement was reactivated")
    if not plan["execution"]["continueAfterStagePR"] or plan["execution"]["waitForCIToDevelopNext"]:
        raise ValueError("stage development must not wait for CI")
    return plan


def report(kind="plan", root=None):
    plan = load(root)
    common = {"schema": "8415ex-current-prd-report/1", "version": plan["version"],
              "productStatus": "OPEN", "evidenceKind": "REQUIREMENTS_ONLY",
              "acceptedCases": [], "historicalPassInherited": False,
              "retiredRequirements": plan["retiredRequirements"]}
    if kind == "matrix":
        common.update(rows=plan["cases"], allCasesSound=False,
                      reason="Revised assertions need exact-source evidence, not inherited PASS.")
    elif kind == "stages":
        common.update(stages=plan["stages"], continueAfterPR=True, waitForCI=False)
    elif kind == "decisions":
        common.update(decisions=plan["decisions"],
                      openProductChoices=["D-04 shared-operation allocation", "D-10", "D-11", "D-12"],
                      globalBlockers=[])
    elif kind == "handoff":
        common.update(scenarios=plan["demonstrations"], evidenceStatus="NOT_VERIFIED",
                      execution=plan["execution"])
    elif kind == "sections":
        common.update(sections=plan["sections"], requirements=plan["requirements"])
    else:
        common["executionPlan"] = plan
    return common


def require_current_scenario(scenario_id, revision=None):
    load()
    if scenario_id in LEGACY_DEMOS and revision != VERSION:
        raise ValueError("PRD_MIGRATION_REQUIRED: " + scenario_id
                         + " still uses pre-1.2 fixtures; use the pinned execution plan. "
                         "No legacy collection/burn/payment/grace step was executed.")


def blocked(command, root=None):
    plan = load(root)
    return {"schema": "8415ex-command-migration/1", "version": VERSION,
            "command": command, "status": "PRD_MIGRATION_REQUIRED", "executed": False,
            "allPassed": False, "productStatus": "OPEN",
            "reason": "This legacy path invokes pre-1.2 model expectations. Migrate it "
                      "against config/execution-plan.json; never inherit old PASS.",
            "retiredRequirements": plan["retiredRequirements"],
            "independentWorkMayContinue": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read the pinned EX contract without product scenario execution.")
    parser.add_argument("command", choices=("plan", "matrix", "stages", "decisions", "handoff", "sections"), nargs="?", default="plan")
    parser.add_argument("--root", default=None)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(report(args.command, args.root), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as problem:
        print(json.dumps({"status": "PRD_PIN_ERROR", "executed": False, "error": str(problem),
                          "scope": "this checklist only; independent authorized work continues"}))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
