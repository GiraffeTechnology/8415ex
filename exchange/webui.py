"""A minimal status console for the Stage 1 pages, on the standard library only.

This is a local operable UI, not a trading front end. It serves read-only pages
from one :class:`~exchange.ledger.Exchange`; it has no control that changes a
state, so it cannot be used to mark an outcome by hand.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import views
from .errors import DomainError

DEFAULT_HOST = "127.0.0.1"


def build_handler(exchange, receipt_id, authorization_ids, run):
    class Handler(BaseHTTPRequestHandler):
        server_version = "8415ex-stage1"

        def do_GET(self):  # noqa: N802 - the base class defines this name
            name = (self.path.split("?")[0].strip("/") or "receipt")
            try:
                body = views.page(exchange, receipt_id, name,
                                  authorization_ids=authorization_ids, run=run)
            except KeyError:
                self.send_error(404, "unknown page")
                return
            except DomainError as error:
                self.send_error(400, error.code)
                return
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def do_POST(self):  # noqa: N802
            """There is no write path. A state changes only through a checked
            registrar result, never through this console."""
            self.send_error(405, "this console is read-only")

        def log_message(self, fmt, *args):
            return  # keep the fixture output deterministic

    return Handler


def serve(exchange, receipt_id, authorization_ids=(), run=None, host=DEFAULT_HOST, port=0):
    """Start the console. Returns the server; the caller owns its lifetime.

    The host defaults to loopback. The served origin is scheme, host **and**
    port, so whichever address an environment settles on belongs in that
    environment's deployment document, not here.
    """
    handler = build_handler(exchange, receipt_id, tuple(authorization_ids), run or {})
    return ThreadingHTTPServer((host, port), handler)


def main(argv=None):
    from . import fixtures as F

    parser = argparse.ArgumentParser(description="Serve the local Stage 1 status console.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=8415)
    parser.add_argument("--registration-path", default="REG_DIRECT", choices=views.REGISTRATION_PATHS)
    parser.add_argument("--run-id", default="local-stage1")
    parser.add_argument("--commit", default="not supplied")
    parser.add_argument("--tree", default="not supplied")
    arguments = parser.parse_args(argv)

    exchange, _ = F.chain_to_d(registration_path=arguments.registration_path)
    requests = F.submit_all(exchange)
    F.confirm(exchange, requests[0], "res-ab")
    F.confirm(exchange, requests[2], "res-cd")
    run = {"scenario": "A->B->C->D with the AB hop registered and the CD result deferred",
           "runId": arguments.run_id, "commit": arguments.commit, "tree": arguments.tree}
    server = serve(exchange, "rcpt-8415-0001",
                   authorization_ids=("auth-sell-ab", "auth-buy-ab"), run=run,
                   host=arguments.host, port=arguments.port)
    host, port = server.server_address[0], server.server_address[1]
    print(f"Stage 1 console on http://{host}:{port}/ - pages: {', '.join(views.PAGES)}")
    print("Read-only. Simulated registration. No transaction is sent.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
