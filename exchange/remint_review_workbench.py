"""Mount read-only remint comparison while retaining existing workbench routes."""
from html import escape
from urllib.parse import parse_qs, urlsplit

from .integrated_workbench import IntegratedWorkbenchServer, IntegratedWorkbenchHandler
from .remint_review import RemintReviewBinding, RemintReviewUnavailable, WORDS


class RemintReviewWorkbenchServer(IntegratedWorkbenchServer):
    def __init__(self, binding, *, remint_review=None, **original_options):
        if remint_review is not None and (
                type(remint_review) is not RemintReviewBinding
                or remint_review.receipt_id != binding.receipt_id):
            raise ValueError("original same-receipt review binding required")
        self.remint_review = remint_review
        super().__init__(binding, **original_options)
        self.RequestHandlerClass = RemintReviewWorkbenchHandler


class RemintReviewWorkbenchHandler(IntegratedWorkbenchHandler):
    @staticmethod
    def native_navigation(locale):
        if locale not in WORDS:
            raise ValueError("supported locale required")
        return (IntegratedWorkbenchHandler.native_navigation(locale)
                + '<nav><a href="/remint-review?lang=' + locale + '">'
                + escape(WORDS[locale][8]) + '</a></nav>')

    def do_GET(self):
        request = urlsplit(self.path)
        if request.path != "/remint-review":
            return super().do_GET()
        if not self.host_ok():
            self.send_body(421, "host refused")
            return
        try:
            if request.fragment or len(request.query) > 64:
                raise ValueError("bounded locale required")
            query = parse_qs(request.query, strict_parsing=True, keep_blank_values=True, max_num_fields=1)
            if set(query) - {"lang"} or any(len(values) != 1 for values in query.values()):
                raise ValueError("one locale only")
            locale = query.get("lang", ["en"])[0]
            if locale not in WORDS:
                raise ValueError("supported locale required")
        except ValueError:
            self.send_body(400, "input refused")
            return
        words = WORDS[locale]
        try:
            if self.server.remint_review is None:
                raise RemintReviewUnavailable("not configured")
            content = self.server.remint_review.render(locale)
            status = 200
        except RemintReviewUnavailable:
            content = '<p role="alert">' + escape(words[5]) + '</p>'
            status = 503
        self.send_body(status, self._page(words[0], content, locale, language_path="/remint-review"))

    def do_POST(self):
        if urlsplit(self.path).path != "/remint-review":
            return super().do_POST()
        # No remint body is parsed. Close instead of leaving an unread body on
        # a persistent connection; there is no signing, eligibility or write API.
        self.close_connection = True
        self.send_body(405, "read-only entry", Allow="GET", Connection="close")
