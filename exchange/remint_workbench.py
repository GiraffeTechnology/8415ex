"""Compose the original remint history and receipt views on one workbench."""
from html import escape
from .remint_history_workbench import (
    RemintHistoryWorkbenchServer, RemintHistoryWorkbenchHandler, RemintChainHistoryBinding,
)
from .remint_receipt_workbench import (
    RemintReceiptWorkbenchServer, RemintReceiptWorkbenchHandler, RemintReceiptViewBinding,
    WORDS as RECEIPT_WORDS,
)


class RemintWorkbenchServer(RemintHistoryWorkbenchServer, RemintReceiptWorkbenchServer):
    """Cooperative original server initialization; each reader remains optional."""
    def __init__(self, binding, *, remint_history=None, remint_receipt=None, **original_options):
        if remint_history is not None and remint_receipt is not None:
            # Original application identity consistency only. No reads or
            # execution eligibility checks occur while mounting these views.
            if (type(remint_history) is not RemintChainHistoryBinding
                    or type(remint_receipt) is not RemintReceiptViewBinding):
                raise ValueError("Original typed read bindings required")
            context = remint_receipt._original_context
            replacement = context.get("replacement")
            if (type(replacement) is not dict
                    or remint_history.contract != context.get("contract")
                    or remint_history.bill_key != replacement.get("billKey")):
                raise ValueError("Original history and receipt must identify one contract and bill")
        super().__init__(binding, remint_history=remint_history,
                         remint_receipt=remint_receipt, **original_options)
        self.RequestHandlerClass = RemintWorkbenchHandler


class RemintWorkbenchHandler(RemintHistoryWorkbenchHandler, RemintReceiptWorkbenchHandler):
    @staticmethod
    def native_navigation(locale):
        if locale not in RECEIPT_WORDS:
            raise ValueError("Supported locale required")
        # The history navigation already retains the original review, gas and
        # registration entries. Add the result entry exactly once.
        return (RemintHistoryWorkbenchHandler.native_navigation(locale)
                + '<nav><a href="/remint-result?lang=' + locale + '">'
                + escape(RECEIPT_WORDS[locale][0]) + '</a></nav>')
