"""The current decision register, loaded from the verified product contract."""
from .current_prd import load, report

PRODUCT_OWNER = "the product owner"
ENGINEERING = "engineering verifies original interfaces and configuration"
LOCAL_MODEL_PROCEEDS = "independent authorized work proceeds"
LOCAL_MODEL_BLOCKED = "only the affected path waits"


def register():
    return report("decisions")


def reported_locally():
    return {}
