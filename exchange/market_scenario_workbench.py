"""Mount existing read-only scene context on an original EX HTTP server."""
from html import escape
from http.server import HTTPServer
from urllib.parse import parse_qs, urlsplit

from .market_scenarios import WORDS, render_scenarios
from .nft_directory import NftDirectory
from .workbench import WorkbenchServer


def mount_market_scenarios(server, *, allow_empty_catalogue=False):
    if type(allow_empty_catalogue) is not bool:
        raise ValueError("explicit empty catalogue option required")
    directory = getattr(server, "nft_directory", None)
    empty = (allow_empty_catalogue and isinstance(server, HTTPServer)
             and type(directory) is NftDirectory and not directory._bindings)
    if not isinstance(server, WorkbenchServer) and not empty:
        raise ValueError("original workbench or explicitly selected empty catalogue required")
    if type(directory) is not NftDirectory:
        raise ValueError("original NFT directory required")
    if getattr(server, "_market_scenarios_mounted", False):
        return server
    parent = server.RequestHandlerClass

    class ScenarioHandler(parent):
        @staticmethod
        def native_navigation(locale):
            if locale not in WORDS:
                raise ValueError("supported locale required")
            return (parent.native_navigation(locale) + '<nav><a href="/scenarios?lang='
                    + locale + '">' + escape(WORDS[locale][0]) + '</a></nav>')

        def do_GET(self):
            request = urlsplit(self.path)
            if request.path != "/scenarios":
                return super().do_GET()
            if not self.host_ok():
                self.send_body(421, "host refused")
                return
            locale = "en"
            try:
                if request.fragment or len(request.query) > 1024:
                    raise ValueError("bounded scene context required")
                query = parse_qs(request.query, strict_parsing=True,
                    keep_blank_values=True, max_num_fields=5)
                if (set(query) - {"lang", "scene", "crypto", "commodity", "target"}
                        or any(len(values) != 1 for values in query.values())):
                    raise ValueError("one scalar per scene field required")
                locale = query.get("lang", ["en"])[0]
                if locale not in WORDS:
                    raise ValueError("supported locale required")
                body = render_scenarios(self.server.nft_directory, locale,
                    **{key: query.get(key, [""])[0]
                       for key in ("scene", "crypto", "commodity", "target")})
            except ValueError:
                self.send_body(400, WORDS.get(locale, WORDS["en"])[20])
                return
            self.send_body(200, body)

        def do_POST(self):
            request = urlsplit(self.path)
            if request.path != "/scenarios":
                return super().do_POST()
            # No body parsing or business dispatch; preserve Host refusal first.
            self.close_connection = True
            if not self.host_ok():
                self.send_body(421, "host refused", Connection="close")
                return
            locale = "en"
            try:
                if len(request.query) > 1024:
                    raise ValueError("bounded query required")
                query = parse_qs(request.query, max_num_fields=5)
                supplied = query.get("lang", ["en"])
                if len(supplied) == 1 and supplied[0] in WORDS:
                    locale = supplied[0]
            except ValueError:
                pass
            self.send_body(405, WORDS[locale][20], Allow="GET", Connection="close")

    server.RequestHandlerClass = ScenarioHandler
    server._market_scenarios_mounted = True
    return server
