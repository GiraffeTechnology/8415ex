"""The 21-section current product ledger; requirement descriptions live in PRD.md."""
from .current_prd import report


def build(root="."):
    return report("sections", root)
