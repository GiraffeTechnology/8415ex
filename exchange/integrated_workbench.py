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
from .gas_disclosure_locales import WORDS as GAS_WORDS, TRANSPORT
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
    @staticmethod
    def _gas_locale(request):
        if request.fragment or len(request.query) > 64:
            raise ValueError("bounded disclosure locale required")
        if not request.query:
            return "en"
        query = parse_qs(request.query, strict_parsing=True,
                         keep_blank_values=True, max_num_fields=1)
        if (set(query) != {"lang"} or len(query["lang"]) != 1
                or query["lang"][0] not in GAS_WORDS):
            raise ValueError("one supported disclosure locale required")
        return query["lang"][0]

    def _page(self, title, content, locale="en", language_path="/gas"):
        if locale not in GAS_WORDS:
            raise ValueError("supported disclosure locale required")
        words = TRANSPORT[locale]
        suffix = "" if locale == "en" else "?lang=" + locale
        links = ('<nav><a href="/receipt">' + escape(words["receipt"]) + '</a> '
                 '<a href="/gas' + suffix + '">' + escape(words["gas"]) + '</a> '
                 '<a href="/registration-source' + suffix + '">' + escape(words["registration"])
                 + '</a></nav>')
        languages = '<nav aria-label="' + escape(words["language"]) + '">' + ' '.join(
            '<a lang="' + key + '" href="' + language_path + '?lang=' + key + '">' + label + '</a>'
            for key, label in (("en", "English"), ("zh-Hans", "简体中文"),
                               ("zh-Hant", "繁體中文"), ("fr", "Français"),
                               ("es", "Español"), ("ja", "日本語"))) + '</nav>'
        return ('<!doctype html><html lang="' + locale + '"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>' + escape(title) + '</title><body><main>'
                + links + languages + content + '</main></body></html>')

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
        locale = "en"
        source_query = {}
        if request.path == "/gas":
            try:
                locale = self._gas_locale(request)
            except ValueError:
                self.send_body(400, TRANSPORT["en"]["inputRefused"])
                return
        elif request.query:
            try:
                if len(request.query) > 1024:
                    raise ValueError("bounded source query required")
                source_query = parse_qs(request.query, strict_parsing=True,
                                        keep_blank_values=True, max_num_fields=3)
                if (set(source_query) - {"lang", "receipt", "source"}
                        or any(len(values) != 1 for values in source_query.values())):
                    raise ValueError("exact scalar source fields required")
                locale = source_query.pop("lang", ["en"])[0]
                if locale not in GAS_WORDS:
                    raise ValueError("supported registration locale required")
                if source_query and set(source_query) != {"receipt", "source"}:
                    raise ValueError("receipt and source must be paired")
            except ValueError:
                self.send_body(400, TRANSPORT["en"]["inputRefused"])
                return
        if not self.host_ok():
            self.send_body(421, TRANSPORT[locale]["hostRefused"])
            return
        try:
            if request.fragment:
                raise ValueError("fragment refused")
            if request.path == "/gas":
                locale = self._gas_locale(request)
                content = self.server.gas_page.render(
                    self.server.current_time(), self.server.csrf, locale=locale)
                title = GAS_WORDS[locale]["heading"]
            else:
                rid = self.server.binding.receipt_id
                if not source_query:
                    content = self.server.registration_sources.render_choices(
                        rid, "/registration-source", locale=locale)
                else:
                    if source_query["receipt"][0] != rid:
                        raise ValueError("receipt differs from native workbench")
                    content = self.server.registration_sources.render_source(
                        source_query["source"][0], rid, locale=locale)
                title = TRANSPORT[locale]["registration"]
            self.send_body(200, self._page(title, content, locale, request.path))
        except (ValueError, KeyError, GasBudgetRefused,
                RegistrationSourceRefused):
            self.send_body(400, TRANSPORT[locale]["inputRefused"])
        except OSError:
            self.send_body(503, TRANSPORT[locale]["unavailable"])

    def do_POST(self):
        request = urlsplit(self.path)
        if request.path != "/gas/confirm":
            return super().do_POST()
        try:
            locale = self._gas_locale(request)
        except ValueError:
            self.send_body(403, TRANSPORT["en"]["originRefused"])
            return
        if (not self.host_ok()
                or self.headers.get("Origin") != self.server.origin):
            self.send_body(403, TRANSPORT[locale]["originRefused"])
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
            self.send_body(303, "", Location="/gas" + (
                "" if locale == "en" else "?lang=" + locale))
        except (ValueError, UnicodeError, GasBudgetRefused):
            self.send_body(400, TRANSPORT[locale]["confirmationRefused"])
        except TimeoutError:
            self.close_connection = True
            self.send_body(408, TRANSPORT[locale]["unknown"])
        except OSError:
            self.send_body(503, TRANSPORT[locale]["unknown"])




