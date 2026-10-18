"""Native local workbench over the existing domain views and demo harness.

The host injects its existing wallet-authorized command gateway. This module
creates no authority, signer, journal, provider, deployment or acceptance result.
"""
import argparse
from collections import OrderedDict
from html import escape
import hashlib
import json
import re
import secrets
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import views
from .nft_detail import receipt_detail
from .nft_detail_page import render_detail, LOCALES
from .nft_directory import NftDirectory
from .reference_feed import CommodityReferenceFeed
from .market_page import render_market, ASSETS
from .demo_ui import DemoHandler, DemoServer, MAX_BODY
from .errors import DomainError
from .public_workbench import snapshot as public_snapshot, command_result

ACTIONS = {
    "submit-registration": "Submit registration",
    "reconcile-payment": "Enquire payment outcome",
    "resume-payment": "Resume an eligible payment",
    "advance-rollback": "Continue authorized suffix recovery",
    "advance-exit": "Continue authorized exit",
}
SCHEMA = "8415ex-workbench/1"

def stable_revision(value):
    if isinstance(value, dict):
        return {k:stable_revision(v) for k,v in value.items() if k != "observedAt"}
    if isinstance(value, (list,tuple)):
        return [stable_revision(v) for v in value]
    return value

class RuntimeBinding:
    """One domain object for every native page and command refresh.

    gateway.dispatch(action, payload, context) must enter the original checked
    wallet/task-journal path. gateway.enquire(key, context) must reconcile an
    unknown result before a retry. A configured gateway is not proof of a live
    provider. No credentials or signed payloads belong in snapshots.
    """
    def __init__(self, exchange, receipt_id, authorization_ids=(), run=None, gateway=None,
                 read_details=None, verify_details=None, verify_signature=None):
        self.exchange = exchange
        self.receipt_id = receipt_id
        self.authorization_ids = tuple(authorization_ids)
        self.run = dict(run or {})
        self.gateway = gateway
        self.read_details = read_details
        self.verify_details = verify_details
        self.verify_signature = verify_signature

    def snapshot(self):
        ex, rid = self.exchange, self.receipt_id
        value = {"receipt": ex.receipt_view(rid), "funds": ex.reconciliation(rid),
                 "rollback": ex.rollback_report(rid), "exit": ex.exit_report(rid),
                 "timeline": list(ex.receipt_timeline(rid)),
                 "overdue": list(ex.overdue_requests(rid)),
                 "authorizations": [ex.authorization_state(i) for i in self.authorization_ids]}
        # Observation time is not a concurrency revision. The original checked
        # gateway owns atomic head/nonce/authorization validation.
        revision_input = stable_revision(value)
        revision_input["receipt"] = {k:v for k,v in value["receipt"].items() if k != "observedAt"}
        revision = hashlib.sha256(json.dumps(revision_input, sort_keys=True,
                                              separators=(",", ":"), default=list).encode()).hexdigest()
        return {"schema": SCHEMA, "source": dict(self.run), "revision": revision,
                "state": value, "commandGateway": "configured" if self.gateway else "NOT_CONFIGURED",
                "meaning": "domain observation, not deployment or real-evidence acceptance"}

    def public_detail(self):
        return receipt_detail(self.exchange, self.receipt_id,
                              read_details=self.read_details, verify_details=self.verify_details,
                              verify_signature=self.verify_signature)

    def command(self, action, key, revision, payload):
        if action not in ACTIONS:
            raise ValueError("unsupported workbench action")
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key):
            raise ValueError("bounded journal key required")
        if self.gateway is None:
            raise PermissionError("original wallet/task-journal gateway NOT_CONFIGURED")
        current = self.snapshot()
        if not secrets.compare_digest(revision, current["revision"]):
            raise ValueError("state changed; refresh before submitting")
        context = {"receiptId": self.receipt_id, "source": dict(self.run),
                   "journalKey": key, "observedRevision": revision, "action": action,
                   "payloadDigest": hashlib.sha256(json.dumps(payload, sort_keys=True,
                       separators=(",", ":")).encode()).hexdigest()}
        previous = self.gateway.enquire(key, context)
        if previous is not None:
            # Unknown and pending are returned for investigation, never resent.
            return {"journalKey": key, "enquired": True, "result": previous}
        result = self.gateway.dispatch(action, dict(payload), context)
        return {"journalKey": key, "enquired": False, "result": result}


def public_result(value):
    """Known statuses and valid transaction hashes; no opaque party-bearing text."""
    return command_result(value)

class WorkbenchServer(DemoServer):
    def __init__(self, binding, port=0, commit=None, tree=None, detail_bindings=(), reference_feed=None):
        self.binding = binding
        if reference_feed is not None and not isinstance(reference_feed, CommodityReferenceFeed):
            raise ValueError("verified original reference feed required")
        self.reference_feed = reference_feed
        self.nft_directory = NftDirectory((binding,) + tuple(detail_bindings))
        self.default_nft_key = self.nft_directory.key_for(binding)
        self.command_observations = OrderedDict()
        super().__init__(port=port, commit=commit, tree=tree)
        self.binding.run.update(self.source)
        self.RequestHandlerClass = WorkbenchHandler

    def serve_forever(self, *args, **kwargs):
        if self.reference_feed is not None:
            self.reference_feed.start()
        try:
            return super().serve_forever(*args, **kwargs)
        finally:
            if self.reference_feed is not None:
                self.reference_feed.close()

    def server_close(self):
        if self.reference_feed is not None:
            self.reference_feed.close()
        return super().server_close()

class WorkbenchHandler(DemoHandler):
    def native_page(self, name, locale="en"):
        binding = self.server.binding
        if name == "receipt":
            # Full applicable terms come only from the original verified,
            # identity-excluding detail projection, never raw mint documents.
            return render_detail(binding.public_detail(), locale=locale,
                                 nft_key=self.server.default_nft_key,
                                 choices=self.server.nft_directory.choices())
        if locale != "en":
            raise ValueError("this native view has no verified localized renderer")
        body = views.page(binding.exchange, binding.receipt_id, name,
                          authorization_ids=binding.authorization_ids, run=binding.run)
        extra = ('<p><a href="/market">Market</a> <a href="/nft">NFT detail</a> '
                 '<a href="/demo">Six fixed scenario simulations</a> '
                 '<a href="/api/snapshot">Current domain JSON</a> '
                 '<a href="/api/operations">Command observations</a></p>'
                 '<p>Native domain pages and fixed scenario runs are separate observations '
                 'in this one process. A scenario run never changes the native receipt.</p>')
        if name == "queue":
            extra += self.queue_controls()
            snapshot = public_snapshot(binding.snapshot())["state"]
            extra += '<h3>Funds, recovery and exit queue detail</h3><pre>' + escape(json.dumps(
                {k:snapshot[k] for k in ("funds", "rollback", "overdue")},
                sort_keys=True, indent=2)) + '</pre>' 
        if name == "evidence":
            extra += '<h3>Runtime boundary</h3><pre>' + escape(json.dumps({
                "source": public_snapshot(binding.snapshot())["source"], "commandGateway": "configured" if binding.gateway else "NOT_CONFIGURED",
                "providerAcceptance": "NOT_RUN", "chainAcceptance": "NOT_RUN",
                "durableRecovery": "NOT_RUN", "localHistory": "lost on process exit"},
                sort_keys=True, indent=2)) + '</pre>'
        return body.replace('<main>', '<main>'+extra, 1)

    def queue_controls(self):
        binding = self.server.binding
        heading = '<h3>Checked operation requests</h3>'
        if binding.gateway is None:
            return heading + ('<p>Original wallet/task-journal gateway NOT_CONFIGURED. '
                              'No action is enabled. Read-only pages remain available.</p>')
        revision = binding.snapshot()["revision"]
        options = ''.join('<option value="'+escape(k)+'">'+escape(v)+'</option>'
                          for k,v in ACTIONS.items())
        return heading + ('<p>These requests use the original wallet-authorized gateway. '
                          'Connecting is not authorization. Unknown results are enquired '
                          'and are never blindly resent. No success outcome can be supplied.</p>'
                          '<form action="/operation" method="post">'
                          '<input type="hidden" name="csrf" value="'+escape(self.server.csrf,quote=True)+'">'
                          '<input type="hidden" name="revision" value="'+revision+'">'
                          '<label>Action <select name="action">'+options+'</select></label>'
                          '<label>Original task journal key <input required name="key" maxlength="128"></label>'
                          '<label>Leg index (only for segment actions) '
                          '<input name="leg" inputmode="numeric" pattern="[0-9]{1,6}"></label>'
                          '<button type="submit">Submit through checked gateway</button></form>')

    def do_GET(self):
        if not self.host_ok():
            self.send_body(421, "host refused")
            return
        req = urlsplit(self.path)
        try:
            if req.path.startswith("/assets/"):
                name = req.path[len("/assets/"):]
                if req.query or name not in ASSETS:
                    self.send_body(404, "unknown asset")
                    return
                raw = (Path(__file__).resolve().parent / "assets" / name).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ASSETS[name])
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "sandbox; default-src 'none'; style-src 'unsafe-inline'")
                self.end_headers()
                self.wfile.write(raw)
                return
            if req.path in ("/market", "/api/catalogue"):
                query = parse_qs(req.query, strict_parsing=True, keep_blank_values=True)
                if set(query) - {"lang", "q"} or any(len(value) != 1 for value in query.values()):
                    raise ValueError("one market locale and search only")
                locale = query.get("lang", ["en"])[0]
                search = query.get("q", [""])[0]
                if len(search) > 64 or any(ord(char) < 32 for char in search):
                    raise ValueError("bounded market search required")
                rows = self.server.nft_directory.catalogue()
                feed = self.server.reference_feed
                reference = feed.snapshot() if feed is not None else {"status": "not-connected", "price": None}
                if req.path == "/market":
                    self.send_body(200, render_market(rows, reference, locale, search))
                else:
                    self.send_body(200, json.dumps({"nfts": rows, "reference": reference}, sort_keys=True),
                                   "application/json; charset=utf-8")
                return
            if req.path in ("/run",) or (req.path == "/evidence" and req.query):
                return super().do_GET()
            if req.path == "/api/reference" and not req.query:
                feed = self.server.reference_feed
                value = feed.snapshot() if feed is not None else {
                    "kind": "external-spot-reference", "status": "not-connected",
                    "price": None, "lastSuccessful": None, "executableOrder": False,
                    "conversionPerformed": False}
                self.send_body(200, json.dumps(value, sort_keys=True),
                               "application/json; charset=utf-8")
                return
            if req.path in ("/nft", "/api/nft-detail", "/api/nfts"):
                query = parse_qs(req.query, strict_parsing=True, keep_blank_values=True)
                allowed = {"lang", "nft", "q"} if req.path == "/nft" else {"nft"}
                if set(query) - allowed or any(len(value) != 1 for value in query.values()):
                    raise ValueError("one NFT selection and locale only")
                directory = self.server.nft_directory
                key = query.get("nft", [self.server.default_nft_key])[0]
                if not re.fullmatch(r"[0-9a-f]{64}", key):
                    self.send_body(404, "unknown NFT")
                    return
                try:
                    detail = directory.detail(key)
                except KeyError:
                    self.send_body(404, "unknown NFT")
                    return
                if req.path == "/nft":
                    locale = query.get("lang", ["en"])[0]
                    search = query.get("q", [""])[0]
                    if len(search) > 64 or any(ord(char) < 32 for char in search):
                        raise ValueError("bounded market search required")
                    self.send_body(200, render_detail(detail, locale, nft_key=key,
                                                     choices=directory.choices(), market_query=search))
                else:
                    value = {"nfts": directory.choices()} if req.path == "/api/nfts" else detail
                    self.send_body(200, json.dumps(value, sort_keys=True),
                                   "application/json; charset=utf-8")
                return
            if req.path in ("/", "/receipt"):
                if req.fragment or len(req.query) > 64:
                    raise ValueError("bounded receipt locale required")
                query = parse_qs(req.query, strict_parsing=True,
                                 keep_blank_values=True, max_num_fields=1)
                if set(query) - {"lang"} or any(len(values) != 1 for values in query.values()):
                    raise ValueError("one receipt locale only")
                locale = query.get("lang", ["en"])[0]
                if locale not in LOCALES:
                    raise ValueError("supported receipt locale required")
                self.send_body(200, self.native_page("receipt", locale=locale))
                return
            if req.query:
                raise ValueError("this native view takes no query parameters")
            if req.path == "/demo":
                self.send_body(200, super().home())
            elif req.path == "/api/snapshot":
                self.send_body(200, json.dumps(public_snapshot(self.server.binding.snapshot()), sort_keys=True),
                               "application/json; charset=utf-8")
            elif req.path == "/api/operations":
                self.send_body(200, json.dumps({"source": public_snapshot(self.server.binding.snapshot())["source"],
                    "observations": list(self.server.command_observations.values()),
                    "meaning": "bounded RAM status references, not a durable journal"}, sort_keys=True),
                    "application/json; charset=utf-8")
            elif req.path == "/" or req.path.lstrip("/") in views.PAGES:
                self.send_body(200, self.native_page(req.path.lstrip("/") or "receipt"))
            else:
                self.send_body(404, "unknown workbench entry")
        except (ValueError, KeyError, DomainError) as error:
            self.send_body(400, "request refused; inspect the original private journal")

    def do_POST(self):
        if self.path == "/simulate":
            return super().do_POST()
        if not self.host_ok() or self.headers.get("Origin") != self.server.origin:
            self.send_body(403, "same-origin request required")
            return
        if self.path != "/operation":
            self.send_body(404, "unknown workbench command")
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
                raise ValueError("bounded body required")
            raw = self.rfile.read(length)
            if len(raw) != length:
                self.close_connection = True
                raise ValueError("incomplete request body")
            form = parse_qs(raw.decode("utf-8"), strict_parsing=True,
                            keep_blank_values=True, max_num_fields=5)
            if set(form) != {"csrf", "revision", "action", "key", "leg"} or any(len(v)!=1 for v in form.values()):
                raise ValueError("fixed operation fields required; no outcomes accepted")
            fields = {k:v[0] for k,v in form.items()}
            if (not fields["csrf"].isascii() or
                    not secrets.compare_digest(fields["csrf"], self.server.csrf)):
                self.send_body(403, "request token refused")
                return
            if not re.fullmatch(r"[0-9a-f]{64}", fields["revision"]):
                raise ValueError("state revision required")
            payload = {}
            if fields["leg"]:
                if not re.fullmatch(r"[0-9]{1,6}",fields["leg"]):
                    raise ValueError("bounded segment index required")
                payload["legIndex"] = int(fields["leg"])
            segment = fields["action"] in ("submit-registration", "reconcile-payment", "resume-payment")
            if segment != ("legIndex" in payload):
                raise ValueError("segment actions need a leg; receipt actions take no leg")
            observed = self.server.binding.command(fields["action"], fields["key"], fields["revision"], payload)
            item = {"enquired": observed["enquired"],
                    "action": fields["action"], "result": public_result(observed["result"]),
                    "meaning": "gateway observation; verify original journal and evidence"}
            self.server.command_observations[fields["key"]] = item
            while len(self.server.command_observations) > 64:
                self.server.command_observations.popitem(last=False)
            self.send_body(303, "", Location="/queue")
        except PermissionError as error:
            self.send_body(403, "original checked gateway refused this operation")
        except TimeoutError:
            self.close_connection = True
            self.send_body(408, "operation timed out; enquire original journal before retry")
        except (ValueError, UnicodeError, DomainError) as error:
            self.send_body(400, "request refused; inspect the original private journal")
        except OSError:
            self.send_body(503, "operation outcome unknown; enquire original journal before retry")


def main(argv=None):
    # Fixed fixture is an explicit development entry, not a wallet/provider.
    from .cli import scenario
    parser = argparse.ArgumentParser(description="Native read views and checked gateway entry")
    parser.add_argument("--port", type=int, default=8415)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--registration-path", choices=views.REGISTRATION_PATHS, default="REG_DIRECT")
    args = parser.parse_args(argv)
    exchange, _, _, _ = scenario(args.registration_path)
    binding = RuntimeBinding(exchange, "rcpt-8415-0001",
                             ("auth-sell-ab", "auth-buy-ab"),
                             {"runId": "native-local-fixture", "scenario": "read-only fixture"})
    server = WorkbenchServer(binding, port=args.port, commit=args.commit, tree=args.tree)
    print(server.origin + "/receipt - LOCAL_SIMULATION, gateway NOT_CONFIGURED")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())




