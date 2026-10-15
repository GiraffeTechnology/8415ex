"""Loopback-only interactive simulation; runs the existing scenario harness.
No wallet, provider, chain, persistent state or real transaction is exposed.
"""
import argparse
from collections import OrderedDict
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import json
import re
import secrets
from urllib.parse import parse_qs, urlsplit
import uuid

from scenarios.demos import DEMOS
from scenarios.harness import run_all

MAX_RUNS = 16
MAX_BODY = 2048
SCOPE = ("LOCAL SIMULATION: synthetic registrar, payment, asset control and voucher; "
         "no real wallet signing, deployment or chain transaction. "
         "Step navigation replays recorded observations; it does not execute another action.")

def pretty(value):
    return escape(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2))

def identity(value):
    if value is not None and re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError("full lowercase commit/tree identity required")
    return value or "UNVERIFIED"

class DemoServer(HTTPServer):
    """Single-writer synthetic runs, bounded in memory and lost on shutdown."""
    def __init__(self, host="127.0.0.1", port=0, commit=None, tree=None):
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError("simulation must bind to loopback")
        self.source = {"commit": identity(commit), "tree": identity(tree),
                       "meaning": "declared source; execution receipt must independently bind it"}
        self.runs = OrderedDict()
        self.csrf = secrets.token_urlsafe(32)
        super().__init__((host, port), DemoHandler)

    @property
    def origin(self):
        host, port = self.server_address[:2]
        return f"http://{host}:{port}"

    def simulate(self, scenario_id):
        # The exact fixed producer scenario executes; the request supplies no outcomes.
        scenario = next((item for item in DEMOS if item.scenario_id == scenario_id), None)
        if scenario is None:
            raise ValueError("unknown scenario")
        record = {"schema": "8415ex-demo-ui/1", "runId": "demo-" + uuid.uuid4().hex,
                  "evidenceKind": "LOCAL_SIMULATION", "scope": SCOPE,
                  "source": dict(self.source), "report": run_all((scenario,)),
                  "realEvidence": dict.fromkeys(
                      ("deployment", "provider", "signatures", "chain", "transactions"), "NOT_RUN")}
        self.runs[record["runId"]] = record
        while len(self.runs) > MAX_RUNS:
            self.runs.popitem(last=False)
        return record

class DemoHandler(BaseHTTPRequestHandler):
    server_version = "8415ex-local-demo"

    def setup(self):
        super().setup()
        self.connection.settimeout(2)  # bound a partial local request; no global network change

    def log_message(self, fmt, *args):
        return

    def send_body(self, status, body, mime="text/html; charset=utf-8", **headers):
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
                         "frame-ancestors 'none'; base-uri 'none'")
        for key, value in headers.items():
            self.send_header(key.replace("_", "-"), value)
        self.end_headers()
        self.wfile.write(payload)

    def host_ok(self):
        return self.headers.get("Host") == self.server.origin.removeprefix("http://")

    def shell(self, content):
        return ('<!doctype html><html lang="en"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>8415ex local simulation</title><style>'
                'body{font:16px system-ui;max-width:1100px;margin:auto;padding:24px;'
                'background:#101923;color:#eef3f8}a{color:#83caff}button,select{font:inherit;'
                'padding:10px;margin:6px}pre{white-space:pre-wrap;overflow-wrap:anywhere;'
                'background:#1b2a3a;padding:16px}section{margin:22px 0}'
                'td,th{padding:10px;border:1px solid #567;text-align:left}table{width:100%;'
                'border-collapse:collapse}.warning{border:2px solid #eda;padding:16px}'
                '</style><body><h1>8415ex scenario console</h1>'
                '<p class="warning">' + escape(SCOPE) + '</p>'
                '<p>State exists in this process only. Shutting down discards these runs. '
                'Registrar roles are simulated; no institutional cooperation is implied.</p>'
                '<p>Declared source identity</p><pre>' + pretty(self.server.source) + '</pre>'
                + content + '</body></html>')

    def home(self):
        choices = ''.join('<option value="' + escape(s.scenario_id, quote=True) + '">'
                          + escape(s.scenario_id + ' — ' + s.title + ' [' + s.main_path + ']')
                          + '</option>' for s in DEMOS)
        form = ('<section><h2>Run a fixed simulation</h2><p>The selected scenario runs its '
                'existing checked domain actions. No editable success result is accepted.</p>'
                '<form method="post" action="/simulate"><input type="hidden" name="csrf" value="'
                + escape(self.server.csrf, quote=True) + '"><label>Scenario <select name="scenario">'
                + choices + '</select></label><button type="submit">Run simulation</button></form></section>')
        history = ''.join('<li><a href="/run?id=' + escape(key, quote=True) + '">'
                          + escape(key + ' ' + record["report"]["scenarios"][0]["scenarioId"])
                          + '</a> — ' + ('local checks passed' if record["report"]["allPassed"]
                                        else 'local failure retained') + '</li>'
                          for key, record in reversed(self.server.runs.items()))
        return self.shell(form + '<h2>Recent runs (up to 16)</h2><ul>' + history + '</ul>')

    def run_page(self, record, step):
        result = record["report"]["scenarios"][0]
        steps = result["steps"]
        if not 0 <= step <= len(steps):
            raise ValueError("step outside recorded range")
        key = escape(record["runId"], quote=True)
        nav = ('<p><a href="/">Scenarios</a> · <a href="/evidence?id=' + key
               + '">JSON evidence for this run</a></p>')
        if step:
            nav += '<a href="/run?id=' + key + '&amp;step=' + str(step - 1) + '">Previous observation</a> '
        if step < len(steps):
            nav += '<a href="/run?id=' + key + '&amp;step=' + str(step + 1) + '">Next observation</a>'
        observed = result["setup"] if step == 0 else steps[step - 1]
        rows = ''.join('<tr><td>' + escape(e["name"]) + '</td><td>' + escape(", ".join(e["cases"]))
                       + '</td><td>' + escape(e["outcome"]) + '</td><td><pre>' + pretty(e["expected"])
                       + '</pre></td><td><pre>' + pretty(e["observed"]) + '</pre>'
                       + escape(e.get("detail") or "") + '</td></tr>' for e in result["expectations"])
        return self.shell('<h2>' + escape(result["scenarioId"] + ' — ' + result["title"]) + '</h2>'
                          + '<p>Run ' + key + ' · simulated path ' + escape(result["mainPath"])
                          + ' · ' + ('local checks passed' if result["passed"] else 'LOCAL FAILURE')
                          + '</p>' + nav + '<h3>Recorded observation ' + str(step) + '/' + str(len(steps))
                          + '</h3><pre>' + pretty(observed) + '</pre><h3>Expected and observed assertions</h3>'
                          + '<table><tr><th>Assertion</th><th>Cases</th><th>Outcome</th><th>Expected</th>'
                          '<th>Observed / limitation</th></tr>' + rows + '</table>'
                          + '<h3>Failure and unresolved notes</h3><pre>'
                          + pretty({"error": result["error"], "notes": result["notes"],
                                    "counts": result["counts"], "realEvidence": record["realEvidence"]})
                          + '</pre>')

    def do_GET(self):
        if not self.host_ok():
            self.send_body(421, "host refused")
            return
        request = urlsplit(self.path)
        query = parse_qs(request.query)
        try:
            if request.path == "/":
                self.send_body(200, self.home())
                return
            if request.path not in ("/run", "/evidence"):
                self.send_body(404, "unknown route")
                return
            if set(query) - {"id", "step"} or len(query.get("id", [])) != 1:
                raise ValueError("one run id required")
            record = self.server.runs.get(query["id"][0])
            if record is None:
                self.send_body(404, "run unknown or expired from memory")
                return
            if request.path == "/evidence":
                self.send_body(200, json.dumps(record, sort_keys=True), "application/json; charset=utf-8")
            else:
                values = query.get("step", ["0"])
                if len(values) != 1:
                    raise ValueError("one observation index required")
                self.send_body(200, self.run_page(record, int(values[0])))
        except ValueError as error:
            self.send_body(400, escape(str(error)))

    def do_POST(self):
        if not self.host_ok() or self.headers.get("Origin") != self.server.origin:
            self.send_body(403, "same-origin simulation request required")
            return
        if self.path != "/simulate":
            self.send_body(404, "unknown simulation route")
            return
        try:
            if self.headers.get("Transfer-Encoding") is not None:
                raise ValueError("encoded request refused")
            if self.headers.get("Content-Type") != "application/x-www-form-urlencoded":
                raise ValueError("form content type required")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise ValueError("bounded request body required")
            form = parse_qs(self.rfile.read(length).decode("utf-8"), strict_parsing=True)
            if set(form) != {"csrf", "scenario"} or any(len(v) != 1 for v in form.values()):
                raise ValueError("fixed scenario and token only; no outcomes accepted")
            if (not form["csrf"][0].isascii()
                    or not secrets.compare_digest(form["csrf"][0], self.server.csrf)):
                self.send_body(403, "simulation token refused")
                return
            record = self.server.simulate(form["scenario"][0])
            self.send_body(303, "", Location="/run?id=" + record["runId"])
        except TimeoutError:
            self.close_connection = True
            self.send_body(408, "simulation request body timed out")
        except (ValueError, UnicodeError) as error:
            self.send_body(400, escape(str(error)))

def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the loopback-only synthetic scenario console.")
    parser.add_argument("--port", type=int, default=8415)
    parser.add_argument("--commit")
    parser.add_argument("--tree")
    args = parser.parse_args(argv)
    server = DemoServer(port=args.port, commit=args.commit, tree=args.tree)
    print(server.origin + "/ — LOCAL SIMULATION, no transactions")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
