"""Mount the two-category scenario selector without a financing command."""
from html import escape
from http.server import HTTPServer
from urllib.parse import parse_qs, urlsplit

from .collateral_scenario import WORDS, render_collateral
from .nft_directory import NftDirectory
from .remint_review_workbench import RemintReviewWorkbenchServer


def mount_collateral_selection(server, *, allow_empty_catalogue=False):
    if type(allow_empty_catalogue) is not bool:
        raise ValueError("explicit empty catalogue composition option required")
    directory = getattr(server, "nft_directory", None)
    empty_directory_server = (allow_empty_catalogue
        and isinstance(server, HTTPServer)
        and type(directory) is NftDirectory and not directory._bindings)
    if not isinstance(server, RemintReviewWorkbenchServer) and not empty_directory_server:
        raise ValueError("original workbench or explicitly selected empty catalogue required")
    if getattr(server, "_collateral_selection_mounted", False):
        return server
    parent = server.RequestHandlerClass

    class CollateralHandler(parent):
        @staticmethod
        def native_navigation(locale):
            if locale not in WORDS:
                raise ValueError("supported locale required")
            return (parent.native_navigation(locale) + '<nav><a href="/collateral?lang='
                    + locale + '">' + escape(WORDS[locale][0]) + '</a></nav>')

        def do_GET(self):
            request = urlsplit(self.path)
            if request.path != "/collateral":
                return super().do_GET()
            if not self.host_ok():
                self.send_body(421, "host refused")
                return
            locale = "en"
            try:
                if request.fragment or len(request.query) > 1024:
                    raise ValueError("bounded selection required")
                query = parse_qs(request.query, strict_parsing=True,
                    keep_blank_values=True, max_num_fields=4)
                if (set(query) - {"lang", "kind", "asset", "target"}
                        or any(len(values) != 1 for values in query.values())):
                    raise ValueError("one value per selection field required")
                locale = query.get("lang", ["en"])[0]
                if locale not in WORDS:
                    raise ValueError("supported locale required")
                body = render_collateral(self.server.nft_directory, locale,
                    **{key: query.get(key, [""])[0] for key in ("kind", "asset", "target")})
            except ValueError:
                self.send_body(400, WORDS.get(locale, WORDS["en"])[13])
                return
            payload = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
                "form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            request = urlsplit(self.path)
            if request.path != "/collateral":
                return super().do_POST()
            self.close_connection = True
            if not self.host_ok():
                self.send_body(421, "host refused", Connection="close")
                return
            try:
                query = parse_qs(request.query, max_num_fields=4)
                locale = query.get("lang", ["en"])[0]
            except ValueError:
                locale = "en"
            self.send_body(405, WORDS.get(locale, WORDS["en"])[13], Allow="GET", Connection="close")

    server.RequestHandlerClass = CollateralHandler
    server._collateral_selection_mounted = True
    return server
