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

The scenario commands are read from the list the parser itself uses, so the
parser and this check cannot disagree. The domain commands are read out of the
domain's own source, because that module belongs to another surface and is not
edited from here to make a check easier.
"""
import pathlib
import re


def scenario_commands():
    """The scenario command line's own list, imported where it is needed.

    Imported inside the function rather than at module level: the command line
    imports this module to expose the check as a subcommand, and a module-level
    import would close that loop.
    """
    from .cli import COMMANDS

    return tuple(COMMANDS)


#: The guides that carry usage instructions.
GUIDES = ("README.md", "scenarios/README.md", "exchange/README.md", "ci/README.md")

#: Where the domain's own command list lives, and how to read it.
DOMAIN_CLI = "exchange/cli.py"
DOMAIN_CHOICES = re.compile(
    r'add_argument\(\s*"command"\s*,\s*choices=\(([^)]*)\)', re.S)

#: A documented invocation of one of the two command lines.
INVOCATION = re.compile(r"python3 -B -m (scenarios|exchange)\.cli ([a-z][a-z-]*)")

#: Commands that exist for a reason other than being followed by a reader, and
#: so are not required to appear in a guide. Each says why.
NOT_REQUIRED_IN_GUIDES = {}


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
    """Every invocation the guides carry, by tool, with the guides it is in."""
    found = {"scenarios": {}, "exchange": {}}
    missing = []
    for guide in GUIDES:
        path = pathlib.Path(root) / guide
        if not path.is_file():
            missing.append(guide)
            continue
        for tool, command in INVOCATION.findall(path.read_text(encoding="utf-8")):
            found[tool].setdefault(command, []).append(guide)
    return {
        "scenarios": {command: sorted(set(guides))
                      for command, guides in sorted(found["scenarios"].items())},
        "exchange": {command: sorted(set(guides))
                     for command, guides in sorted(found["exchange"].items())},
        "guidesRead": [guide for guide in GUIDES if guide not in missing],
        "guidesMissing": sorted(missing),
    }


def check(root="."):
    """Both directions: broken instructions, and reports nobody will find."""
    guides = documented(root)
    domain = domain_commands(root)
    real = {"scenarios": sorted(scenario_commands()),
            "exchange": sorted(domain["commands"])}
    findings = []
    for guide in guides["guidesMissing"]:
        findings.append({"finding": "a guide named here does not exist",
                         "detail": guide})
    if domain["error"] is not None:
        findings.append({"finding": "the domain command list could not be read",
                         "detail": domain["error"]})
    tools = {}
    for tool in ("scenarios", "exchange"):
        shown = set(guides[tool])
        exists = set(real[tool])
        broken = sorted(shown - exists)
        undocumented = sorted(exists - shown - set(NOT_REQUIRED_IN_GUIDES))
        for command in broken:
            findings.append({
                "finding": "a guide shows a command that does not exist",
                "detail": "%s.cli %s, in %s"
                          % (tool, command, ", ".join(guides[tool][command]))})
        for command in undocumented:
            findings.append({
                "finding": "a command exists and no guide shows it",
                "detail": "%s.cli %s" % (tool, command)})
        tools[tool] = {
            "commandsThatExist": real[tool],
            "commandsDocumented": sorted(shown),
            "documentedButMissing": broken,
            "existsButUndocumented": undocumented,
            "whereEachIsShown": guides[tool],
            "consistent": not broken and not undocumented,
        }
    return {
        "schema": "8415ex-usage-check/1",
        "tools": tools,
        "guidesRead": guides["guidesRead"],
        "guidesMissing": guides["guidesMissing"],
        "domainCommandSource": domain,
        "notRequiredInGuides": dict(NOT_REQUIRED_IN_GUIDES),
        "findings": findings,
        "findingCount": len(findings),
        "consistent": not findings,
        "isNot": [
            "not a check that an instruction works: it checks that the command "
            "exists and is documented, never that following it succeeds",
            "not a review of the explanation around a command",
        ],
    }
