"""Mount existing gas and registration views on one native workbench.

Construction requires original application controllers. No fixture, endpoint,
wallet, session or registration authority is selected here.
"""
from html import escape
import re
from urllib.parse import parse_qs, urlsplit

from .workbench import WorkbenchServer, WorkbenchHandler
from .demo_ui import MAX_BODY
from .gas_confirmation_ui import GasConfirmationPage
from .gas_budget import GasBudgetRefused
from .registration_source_workbench import (
    RegistrationSourceWorkbench, RegistrationSourceRefused,
)


class IntegratedWorkbenchServer(WorkbenchServer):
    """Explicit application composition; constructor does not start serving."""

    def __init__(self, binding, *, gas_page, registration_sources, current_time,
                 commit, tree, port=0, detail_bindings=(), reference_feed=None):
        if not isinstance(gas_page, GasConfirmationPage):
            raise ValueError("existing gas confirmation controller required")
        if not isinstance(registration_sources, RegistrationSourceWorkbench):
            raise ValueError("existing registration-source controller required")
        if not callable(current_time):
            raise ValueError("original application clock required")
        if gas_page.post_path != "/gas/confirm":
            raise ValueError("gas controller must bind the mounted POST path")
        if any(type(value) is not str or re.fullmatch(r"[0-9a-f]{40}", value) is None
               for value in (commit, tree)):
            raise ValueError("exact source commit and tree required")
        self.gas_page = gas_page
        self.registration_sources = registration_sources
        self.current_time = current_time
        super().__init__(binding, port=port, commit=commit, tree=tree,
                         detail_bindings=detail_bindings, reference_feed=reference_feed)
        self.RequestHandlerClass = IntegratedWorkbenchHandler


class IntegratedWorkbenchHandler(WorkbenchHandler):
    def _page(self, title, content):
        return ('<!doctype html><html lang="en"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>' + escape(title) + '</title><body><main>'
                '<nav><a href="/receipt">Receipt</a> '
                '<a href="/gas">Gas confirmation</a> '
                '<a href="/registration-source">Registration source</a></nav>'
                + content + '</main></body></html>')

    def native_page(self, name):
        body = super().native_page(name)
        links = ('<nav aria-label="Integrated components">'
                 '<a href="/gas">Gas confirmation</a> '
                 '<a href="/registration-source">Registration source</a></nav>')
        return body.replace("<main>", "<main>" + links, 1)

    def do_GET(self):
        request = urlsplit(self.path)
        if request.path not in ("/gas", "/registration-source"):
            return super().do_GET()
        if not self.host_ok():
            self.send_body(421, "host refused")
            return
        try:
            if request.fragment:
                raise ValueError("fragment refused")
            if request.path == "/gas":
                if request.query:
                    raise ValueError("gas page takes no query fields")
                content = self.server.gas_page.render(
                    self.server.current_time(), self.server.csrf)
                title = "Gas confirmation"
            else:
                rid = self.server.binding.receipt_id
                if not request.query:
                    content = self.server.registration_sources.render_choices(
                        rid, "/registration-source")
                else:
                    if len(request.query) > 1024:
                        raise ValueError("bounded source query required")
                    query = parse_qs(request.query, strict_parsing=True,
                                     keep_blank_values=True, max_num_fields=2)
                    if set(query) != {"receipt", "source"} or any(
                            len(values) != 1 for values in query.values()):
                        raise ValueError("exact scalar source fields required")
                    if query["receipt"][0] != rid:
                        raise ValueError("receipt differs from native workbench")
                    content = self.server.registration_sources.render_source(
                        query["source"][0], rid)
                title = "Registration source"
            self.send_body(200, self._page(title, content))
        except (ValueError, KeyError, GasBudgetRefused,
                RegistrationSourceRefused):
            self.send_body(400, "current component input or binding refused")
        except OSError:
            self.send_body(503, "original component unavailable")

    def do_POST(self):
        if urlsplit(self.path).path != "/gas/confirm":
            return super().do_POST()
        if (self.path != "/gas/confirm" or not self.host_ok()
                or self.headers.get("Origin") != self.server.origin):
            self.send_body(403, "same-origin confirmation required")
            return
        try:
            if self.headers.get("Transfer-Encoding") is not None:
                raise ValueError("encoded body refused")
            if self.headers.get("Content-Type") != "application/x-www-form-urlencoded":
                raise ValueError("form content type required")
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or re.fullmatch(r"[0-9]{1,8}", lengths[0]) is None:
                raise ValueError("single bounded content length required")
            length = int(lengths[0])
            if not 0 < length <= MAX_BODY:
                raise ValueError("bounded form body required")
            raw = self.rfile.read(length)
            if len(raw) != length:
                self.close_connection = True
                raise ValueError("incomplete form body")
            form = parse_qs(raw.decode("utf-8"), strict_parsing=True,
                            keep_blank_values=True, max_num_fields=5)
            if set(form) != {"csrf", "quoteId", "version", "quoteDigest", "accepted"}:
                raise ValueError("exact gas confirmation fields required")
            if any(len(values) != 1 for values in form.values()):
                raise ValueError("scalar gas confirmation fields required")
            fields = {key: values[0] for key, values in form.items()}
            # Controller retains original CSRF, live quote and trusted buyer,
            # action, grant and wallet-confirmation verification. Form fields
            # cannot select those bindings or supply financial outcomes.
            self.server.gas_page.submit(fields, self.server.current_time())
            self.send_body(303, "", Location="/gas")
        except (ValueError, UnicodeError, GasBudgetRefused):
            self.send_body(400, "gas confirmation refused; refresh current quote")
        except TimeoutError:
            self.close_connection = True
            self.send_body(408, "outcome unknown; enquire original wallet before retry")
        except OSError:
            self.send_body(503, "outcome unknown; enquire original wallet before retry")

