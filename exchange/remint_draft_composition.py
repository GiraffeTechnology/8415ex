"""Mount the unsigned editor alongside the original remint read views."""
from html import escape

from .remint_draft_workbench import (
    RemintDraftEditorBinding, RemintDraftWorkbenchHandler, WORDS,
)
from .remint_review_workbench import (
    RemintReviewWorkbenchServer, RemintReviewWorkbenchHandler,
)


def mount_remint_draft(server, editor):
    """Preserve the actual original handler, access and receipt before serving."""
    if (not isinstance(server, RemintReviewWorkbenchServer)
            or type(editor) is not RemintDraftEditorBinding
            or server.binding.exchange is not editor.access
            or server.binding.receipt_id != editor.receipt_id):
        raise ValueError("Same original server, receipt and serialized access required")
    if getattr(server, "_composed_draft_editor", None) is not None:
        if server._composed_draft_editor is not editor:
            raise ValueError("An original editor is already mounted")
        return server
    parent = server.RequestHandlerClass
    if (not isinstance(parent, type)
            or not issubclass(parent, RemintReviewWorkbenchHandler)
            or issubclass(parent, RemintDraftWorkbenchHandler)):
        raise ValueError("Original read-view handler required before draft composition")

    class DraftHandler(RemintDraftWorkbenchHandler, parent):
        @staticmethod
        def native_navigation(locale):
            if locale not in WORDS:
                raise ValueError("Supported locale required")
            return (parent.native_navigation(locale)
                + '<nav><a href="/remint-draft?lang=' + locale + '">'
                + escape(WORDS[locale][0]) + '</a></nav>')

    server.draft_editor = editor
    server._composed_draft_editor = editor
    server.RequestHandlerClass = DraftHandler
    return server
