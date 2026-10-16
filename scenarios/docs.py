"""The documented commands, checked against the commands that exist.

Usage documentation drifts the same way an outline does, and with worse
consequences: a reader follows a command that no longer exists and concludes the
delivery is broken, or never learns about a report because nothing mentions it.
Neither failure makes a test go red on its own.

So every command in the guides is extracted and compared with the commands the
tools really expose, in both directions. A documented command that does not
exist is a broken instruction. A command that exists and is documented nowhere
is a report nobody will find. Both are findings, and they are reported
separately because they are different mistakes.

The scenario commands are read from the one list the parser itself uses, held in
a module with no dependencies of its own, so the parser and this check cannot
disagree and neither imports the other. The domain commands are read out of the
domain's own source, because that module belongs to another surface and is not
edited from here to make a check easier.

Both the guides and the entry points are discovered rather than listed. An
earlier version of this check read four guides and knew two command lines, and
reported itself consistent while saying nothing about the rest of the delivery:
four of the eight runnable entry points are documented only under ``docs/``,
which it never opened. A check that is green because it is not looking is worse
than no check, so the guide set now includes that folder and the entry points
are read out of the source.
"""
import pathlib
import re

from .commands import COMMANDS as SCENARIO_COMMANDS

#: Guides that must exist. One of these going missing is a finding, never a
#: silent skip.
REQUIRED_GUIDES = ("README.md", "scenarios/README.md", "exchange/README.md",
                   "ci/README.md")

#: Folders whose Markdown is also read. Without this the check cannot see the
#: guides that document most of the runnable entry points.
GUIDE_DIRECTORIES = ("docs",)

#: Kept for callers that named the required set directly.
GUIDES = REQUIRED_GUIDES

#: Where a runnable module may live. Test modules are skipped: a test is run by
#: the suite, not followed by a reader out of a guide.
ENTRY_POINT_DIRECTORIES = ("scenarios", "exchange", "ci", "integration")

#: What makes a module runnable, and whether it takes options.
MAIN_GUARD = re.compile(r"^if __name__ == ['\"]__main__['\"]:", re.M)
ARGUMENT_PARSER = re.compile(r"ArgumentParser\(")

#: Any documented ``-m`` invocation, whatever the module.
ANY_INVOCATION = re.compile(r"python3(?: -B)? -m ([A-Za-z_][A-Za-z0-9_.]*)")

#: Modules a guide may invoke that this project does not own, so their absence
#: from the entry-point list is not a finding.
FOREIGN_MODULES = ("unittest", "pip", "venv", "http.server", "json.tool")

#: Where the domain's own command list lives, and how to read it.
DOMAIN_CLI = "exchange/cli.py"
DOMAIN_CHOICES = re.compile(
    r'add_argument\(\s*"command"\s*,\s*choices=\(([^)]*)\)', re.S)

#: A documented invocation of one of the two command lines.
INVOCATION = re.compile(r"python3 -B -m (scenarios|exchange)\.cli ([a-z][a-z-]*)")

#: Commands that exist for a reason other than being followed by a reader, and
#: so are not required to appear in a guide. Each says why.
NOT_REQUIRED_IN_GUIDES = {}


def guides(root="."):
    """Every guide this check reads, and any required one that is absent.

    The required set must exist. The guide folders are read on top of it, so a
    command documented only there is visible to this check instead of being
    invisible and silently counted as undocumented.
    """
    base = pathlib.Path(root)
    read = [name for name in REQUIRED_GUIDES if (base / name).is_file()]
    missing = [name for name in REQUIRED_GUIDES if not (base / name).is_file()]
    for directory in GUIDE_DIRECTORIES:
        folder = base / directory
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.md")):
            name = path.relative_to(base).as_posix()
            if name not in read:
                read.append(name)
    return {"read": read, "missing": sorted(missing)}


def entry_points(root="."):
    """Every module that can be run with ``-m``, read from the source.

    A module counts when it carries a main guard. ``takesOptions`` records
    whether it also builds an argument parser, because a module that runs with
    no options still has to be documented but has no subcommands to check.
    """
    base = pathlib.Path(root)
    found = []
    for directory in ENTRY_POINT_DIRECTORIES:
        folder = base / directory
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*.py")):
            parts = path.relative_to(base).parts
            # A test module carries a main guard so it can be run alone, but it
            # is run by the suite rather than followed out of a guide, so it is
            # not a user-facing entry point. Both layouts are skipped: a tests
            # folder, and a test_ file sitting beside the code it exercises.
            if "tests" in parts or parts[-1].startswith("test_"):
                continue
            text = path.read_text(encoding="utf-8")
            if MAIN_GUARD.search(text) is None:
                continue
            found.append({
                "module": ".".join(parts)[:-len(".py")],
                "path": path.relative_to(base).as_posix(),
                "takesOptions": ARGUMENT_PARSER.search(text) is not None,
            })
    return found


def invoked_modules(root="."):
    """Every ``-m`` module the guides invoke, with the guides that show it."""
    base = pathlib.Path(root)
    found = {}
    for name in guides(root)["read"]:
        text = (base / name).read_text(encoding="utf-8")
        for module in ANY_INVOCATION.findall(text):
            found.setdefault(module, []).append(name)
    return {module: sorted(set(names)) for module, names in sorted(found.items())}


def domain_commands(root="."):
    """The domain command line's subcommands, read from its own source."""
    path = pathlib.Path(root) / DOMAIN_CLI
    if not path.is_file():
        return {"source": DOMAIN_CLI, "readable": False,
                "error": "EX_DOMAIN_CLI_UNREADABLE", "commands": []}
    match = DOMAIN_CHOICES.search(path.read_text(encoding="utf-8"))
    if match is None:
        return {"source": DOMAIN_CLI, "readable": True,
                "error": "EX_DOMAIN_CLI_CHOICES_NOT_FOUND", "commands": []}
    found = sorted(set(re.findall(r'"([a-z][a-z-]*)"', match.group(1))))
    return {"source": DOMAIN_CLI, "readable": True, "error": None,
            "commands": found}


def documented(root="."):
    """Every subcommand the guides carry, by tool, with the guides it is in.

    Reads every discovered guide, not only the required four. A subcommand
    documented under the guide folder used to be counted as undocumented purely
    because this function never opened that file.
    """
    located = guides(root)
    found = {"scenarios": {}, "exchange": {}}
    for guide in located["read"]:
        text = (pathlib.Path(root) / guide).read_text(encoding="utf-8")
        for tool, command in INVOCATION.findall(text):
            found[tool].setdefault(command, []).append(guide)
    return {
        "scenarios": {command: sorted(set(names))
                      for command, names in sorted(found["scenarios"].items())},
        "exchange": {command: sorted(set(names))
                     for command, names in sorted(found["exchange"].items())},
        "guidesRead": list(located["read"]),
        "guidesMissing": list(located["missing"]),
    }


def check(root="."):
    """Both directions: broken instructions, and reports nobody will find."""
    shown = documented(root)
    domain = domain_commands(root)
    real = {"scenarios": sorted(SCENARIO_COMMANDS),
            "exchange": sorted(domain["commands"])}
    findings = []
    for guide in shown["guidesMissing"]:
        findings.append({"finding": "a guide named here does not exist",
                         "detail": guide})
    if domain["error"] is not None:
        findings.append({"finding": "the domain command list could not be read",
                         "detail": domain["error"]})
    tools = {}
    for tool in ("scenarios", "exchange"):
        documented_here = set(shown[tool])
        exists = set(real[tool])
        broken = sorted(documented_here - exists)
        undocumented = sorted(exists - documented_here
                              - set(NOT_REQUIRED_IN_GUIDES))
        for command in broken:
            findings.append({
                "finding": "a guide shows a command that does not exist",
                "detail": "%s.cli %s, in %s"
                          % (tool, command, ", ".join(shown[tool][command]))})
        for command in undocumented:
            findings.append({
                "finding": "a command exists and no guide shows it",
                "detail": "%s.cli %s" % (tool, command)})
        tools[tool] = {
            "commandsThatExist": real[tool],
            "commandsDocumented": sorted(documented_here),
            "documentedButMissing": broken,
            "existsButUndocumented": undocumented,
            "whereEachIsShown": shown[tool],
            "consistent": not broken and not undocumented,
        }
    # Every runnable module, not only the two with subcommands. A reader can
    # follow any of these out of a guide, so one documented nowhere is a report
    # nobody will find - the same finding as an undocumented subcommand, one
    # level up.
    runnable = entry_points(root)
    invoked = invoked_modules(root)
    owned = {entry["module"] for entry in runnable}
    entries = []
    for entry in runnable:
        where = invoked.get(entry["module"], [])
        entries.append(dict(entry, documentedIn=where, documented=bool(where)))
        if not where:
            findings.append({
                "finding": "a runnable entry point is documented nowhere",
                "detail": "%s (%s)" % (entry["module"], entry["path"])})
    stale = sorted(module for module, names in invoked.items()
                   if module not in owned
                   and not module.startswith(FOREIGN_MODULES)
                   and module.split(".")[0] in ENTRY_POINT_DIRECTORIES)
    for module in stale:
        findings.append({
            "finding": "a guide invokes a module that is not runnable",
            "detail": "%s, in %s" % (module, ", ".join(invoked[module]))})

    return {
        "schema": "8415ex-usage-check/2",
        "tools": tools,
        "entryPoints": entries,
        "entryPointCount": len(entries),
        "entryPointsUndocumented": sorted(entry["module"] for entry in entries
                                          if not entry["documented"]),
        "guideInvocationsNotRunnable": stale,
        "modulesInvokedByGuides": invoked,
        "foreignModulesAllowed": list(FOREIGN_MODULES),
        "guidesRead": shown["guidesRead"],
        "guidesMissing": shown["guidesMissing"],
        "domainCommandSource": domain,
        "notRequiredInGuides": dict(NOT_REQUIRED_IN_GUIDES),
        "findings": findings,
        "findingCount": len(findings),
        "consistent": not findings,
        "isNot": [
            "not a check that an instruction works: it checks that the command "
            "exists and is documented, never that following it succeeds",
            "not a review of the explanation around a command",
            "not a check of every shell line in a guide: it covers the module "
            "invocations and the two subcommand lists, not arbitrary prose",
        ],
    }
