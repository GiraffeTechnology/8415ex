"""Explicit read-only empty market entry; no fixture or receipt runtime."""
import argparse
from http.server import HTTPServer
import json
from urllib.parse import parse_qs, urlencode, urlsplit

from .demo_ui import identity
from .health_observation import health_observation
from .market_page import render_market
from .nft_detail_page import LOCALES
from .nft_directory import NftDirectory
from .reference_feed import CommodityReferenceFeed
from .workbench import WorkbenchHandler


class EmptyCatalogueServer(HTTPServer):
    """Loopback origin for an operator's existing proxy, without trading inputs."""

    def __init__(self, *, port, commit, tree, reference_feed=None,
                 collateral_selection=False, scenario_selection=False):
        if type(scenario_selection) is not bool:
            raise ValueError("explicit scenario selection option required")
        if type(collateral_selection) is not bool:
            raise ValueError("explicit collateral selection option required")
        if commit is None or tree is None:
            raise ValueError("explicit declared source identities required")
        source = {"commit": identity(commit), "tree": identity(tree),
                  "meaning": "declared source; independent served-artifact evidence required"}
        if reference_feed is not None and not isinstance(reference_feed, CommodityReferenceFeed):
            raise ValueError("original reference feed required")
        self.source = source
        self.reference_feed = reference_feed
        self.nft_directory = NftDirectory((), allow_empty=True)
        super().__init__(("127.0.0.1", port), EmptyCatalogueHandler)
        if collateral_selection:
            # Import after selecting the original empty server. The shared
            # selector accepts this explicit empty-directory composition, so
            # module CLI execution needs no second server or class-name alias.
            try:
                from .collateral_workbench import mount_collateral_selection
                mount_collateral_selection(self, allow_empty_catalogue=True)
            except Exception:
                self.server_close()
                raise

        if scenario_selection:
            try:
                from .market_scenario_workbench import mount_market_scenarios
                mount_market_scenarios(self, allow_empty_catalogue=True)
            except Exception:
                self.server_close()
                raise

    @property
    def origin(self):
        host, port = self.server_address[:2]
        return f"http://{host}:{port}"


class EmptyCatalogueHandler(WorkbenchHandler):
    server_version = "8415ex-empty-catalogue"

    @staticmethod
    def native_navigation(locale):
        # Receipt-dependent navigation is absent until an original binding exists.
        return ""

    def do_GET(self):
        if not self.host_ok():
            self.send_body(421, "host refused")
            return
        request = urlsplit(self.path)
        if request.fragment or len(request.query) > 4096:
            self.send_body(400, "request refused")
            return
        if request.path in ("/", "/receipt"):
            try:
                query = parse_qs(request.query, strict_parsing=True,
                                 keep_blank_values=True, max_num_fields=1)
                if set(query) - {"lang"} or any(len(values) != 1 for values in query.values()):
                    raise ValueError("one locale only")
                locale = query.get("lang", ["en"])[0]
                if locale not in LOCALES:
                    raise ValueError("supported locale required")
            except ValueError:
                self.send_body(400, "request refused")
                return
            self.send_body(302, "", Location="/market?" + urlencode({"lang": locale}))
            return
        if request.path == "/healthz":
            if request.query:
                self.send_body(400, "request refused")
                return
            value = health_observation(self.server.source,
                gateway_configured=False,
                reference_feed_configured=self.server.reference_feed is not None,
                gas_page_configured=False, registration_sources_configured=False)
            self.send_body(200, json.dumps(value, sort_keys=True),
                           "application/json; charset=utf-8")
            return
        if request.path == "/api/nfts" and not request.query:
            self.send_body(200, '{"nfts": []}', "application/json; charset=utf-8")
            return
        if request.path in ("/market", "/api/catalogue"):
            try:
                query = parse_qs(request.query, strict_parsing=True,
                                 keep_blank_values=True, max_num_fields=2)
                if set(query) - {"lang", "q"} or any(len(values) != 1 for values in query.values()):
                    raise ValueError("one locale and search only")
                locale = query.get("lang", ["en"])[0]
                search = query.get("q", [""])[0]
                if locale not in LOCALES or len(search) > 64 or any(ord(c) < 32 for c in search):
                    raise ValueError("bounded supported search required")
                feed = self.server.reference_feed
                reference = feed.snapshot() if feed is not None else {"status": "not-connected", "price": None}
                if request.path == "/market":
                    body = render_market([], reference, locale, search, empty_catalogue=True)
                    body = body.replace("<main>", "<main>" + self.native_navigation(locale), 1)
                    self.send_body(200, body)
                else:
                    self.send_body(200, json.dumps({"nfts": [], "reference": reference}, sort_keys=True),
                                   "application/json; charset=utf-8")
            except ValueError:
                self.send_body(400, "request refused")
            return
        if ((request.path == "/api/reference" and not request.query)
                or request.path.startswith("/assets/")):
            return super().do_GET()
        # Do not delegate missing receipts, demo, run, snapshot or operation routes.
        self.send_body(404, "entry unavailable")

    def do_POST(self):
        # Close unread request bodies. No form parser, fixture or command dispatch.
        self.close_connection = True
        if not self.host_ok():
            self.send_body(421, "host refused", Connection="close")
            return
        self.send_body(405, "read-only catalogue", Allow="GET", Connection="close")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Serve an explicitly empty read-only market")
    parser.add_argument("--empty-catalogue", action="store_true", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--collateral-selection", action="store_true",
                        help="mount the read-only scenario selector on this empty catalogue")
    parser.add_argument("--scenario-selection", action="store_true",
                        help="mount the read-only market scenario context selector")
    args = parser.parse_args(argv)
    server = EmptyCatalogueServer(port=args.port, commit=args.commit, tree=args.tree,
                                  collateral_selection=args.collateral_selection,
                                  scenario_selection=args.scenario_selection)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
