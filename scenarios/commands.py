"""The command line's subcommands, declared once.

This exists so that the parser and the check that the guides describe real
commands read the same list. Keeping the list in the command-line module and
importing it from the check would close an import loop, and importing it lazily
loads that module a second time under a different name - which the provenance
snapshot then correctly reports as the loaded source changing mid-run. A list
with no dependencies of its own avoids both.
"""

#: Every subcommand of ``python3 -B -m scenarios.cli``.
COMMANDS = ("run-all", "scenarios", "paths", "matrix", "manifest", "handoff",
            "validate-config", "observations", "evidence-index", "decisions",
            "receipt", "reuse", "events", "stages", "dossier", "storyboard",
            "operations", "usage", "completion", "sections")
