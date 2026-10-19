"""Stage 1 status pages: the required content, and the wording the PRD forbids.

A rendered page is development evidence that the view layer reports the state
correctly. It is not genuine UI acceptance evidence, which needs a real browser
journey on a deployed build.
"""
import http.client
import threading
import unittest

from exchange import fixtures as F, views, webui
from exchange.ledger import Exchange


def state():
    exchange, _ = F.chain_to_d()
    requests = F.submit_all(exchange)
    F.confirm(exchange, requests[0], "res-ab")
    F.confirm(exchange, requests[2], "res-cd")
    return exchange, requests


class EveryPageRenders(unittest.TestCase):

    def setUp(self):
        self.exchange, _ = state()

    def _page(self, name):
        return views.page(self.exchange, "rcpt-8415-0001", name,
                          authorization_ids=("auth-sell-ab", "auth-buy-ab"),
                          run={"runId": "test-run", "commit": "0" * 40})

    def test_all_six_required_pages_exist(self):
        self.assertEqual(views.PAGES,
                         ("receipt", "authorization", "timeline", "rollback", "queue", "evidence"))
        for name in views.PAGES:
            with self.subTest(page=name):
                html = self._page(name)
                self.assertTrue(html.startswith("<!doctype html>"))
                self.assertIn("NFT transfer details" if name == "receipt" else "8415ex", html)

    def test_the_receipt_page_labels_both_positions_separately(self):
        html = self._page("receipt")
        self.assertIn("On-chain Owner position", html)
        self.assertIn("Registered Holder position", html)
        self.assertIn("Current position", html)
        self.assertIn("Original terms not provided", html)
        for account in (F.A, F.B, F.C, F.D):
            self.assertNotIn(account, html)

    def test_the_receipt_page_never_shows_one_unexplained_holder(self):
        html = self._page("receipt")
        self.assertNotIn("<th>Holder</th>", html)
        self.assertNotIn("<th>Owner</th>", html)

    def test_the_receipt_page_separates_ordinary_transfer_from_holder_remint(self):
        exchange, _ = F.minted()
        html = views.page(exchange, "rcpt-8415-0001", "receipt")
        self.assertIn("openGapOF=YES does not block normal continuous trading", html)
        self.assertIn("Unknown", html)
        self.assertNotIn("redeem", html.lower())
        self.assertNotIn("necessary condition", html)

    def test_the_authorization_page_denies_that_connecting_authorizes(self):
        html = self._page("authorization")
        self.assertIn("Connecting a wallet authorizes nothing by itself", html)
        self.assertIn("Allowed actions", html)
        self.assertIn("Amount bound", html)
        self.assertIn("Gas responsibility", html)
        self.assertIn("test network", html)

    def test_the_timeline_never_reads_submitted_as_delivered(self):
        html = self._page("timeline")
        self.assertIn("submitted, awaiting registrar", html)
        for forbidden in ("delivered", "settled", "complete delivery"):
            self.assertNotIn(forbidden, html.lower())

    def test_the_timeline_marks_registration_simulated_on_every_leg(self):
        html = self._page("timeline")
        self.assertEqual(html.count("(simulated)"), 3)

    def test_the_rollback_page_hides_no_confirmed_prefix(self):
        html = self._page("rollback")
        self.assertIn("Finalized prefix", html)
        self.assertIn("1 legs confirmed and shown", html)
        self.assertIn("no rollback is open for this receipt", html)
        self.assertIn("Nothing on this page is zeroed out", html)

    def test_the_queue_page_offers_no_manual_outcome_control(self):
        html = self._page("queue")
        self.assertIn("no control on this page that marks an outcome by hand", html)
        self.assertNotIn("<button", html.lower())
        self.assertNotIn("<form", html.lower())
        self.assertNotIn("mark success", html.lower())

    def test_the_queue_page_separates_deferred_from_refused(self):
        html = self._page("queue")
        self.assertIn("deferred", html)
        self.assertIn("a later result is held until the earlier hop is recorded", html)

    def test_an_overdue_window_is_reported_without_a_conclusion(self):
        exchange, requests = state()
        later = requests[1].commitment_deadline_at + 1
        html = views.page(exchange, "rcpt-8415-0001", "queue", now=later)
        self.assertIn("window passed", html)
        self.assertIn("This is a report, not a conclusion and not advice", html)

    def test_the_evidence_page_binds_this_run_and_claims_nothing_more(self):
        html = self._page("evidence")
        self.assertIn("private run reference", html)
        self.assertNotIn("test-run", html)
        self.assertIn("no verified transaction hash supplied", html)
        self.assertIn("no earlier run&#x27;s output is reused here", html)

    def test_every_page_carries_the_scope_banner(self):
        for name in views.PAGES:
            with self.subTest(page=name):
                html = self._page(name)
                if name == "receipt":
                    self.assertIn("Original terms not provided; completeness cannot be verified", html)
                    self.assertIn("Not provided", html)
                else:
                    self.assertIn("Not a deployment or an acceptance record", html)
                    self.assertIn("Registration is simulated", html)

    def test_an_unfunded_stage_says_no_payment_is_modelled(self):
        html = self._page("timeline")
        self.assertIn("No payment is modelled at this stage", html)
        self.assertIn("Original terms not provided", self._page("receipt"))

    def test_an_unknown_page_is_refused(self):
        with self.assertRaises(KeyError):
            self._page("wire-me-money")

    def test_rendering_a_receipt_with_no_trade_yet_is_explicit(self):
        exchange, _ = F.minted()
        html = views.page(exchange, "rcpt-8415-0001", "timeline")
        self.assertIn("no trade yet", html)


class ConsoleIsReadOnly(unittest.TestCase):
    """The served console answers reads and refuses writes."""

    def setUp(self):
        exchange, _ = state()
        self.server = webui.serve(exchange, "rcpt-8415-0001",
                                  authorization_ids=("auth-sell-ab",),
                                  run={"runId": "served"}, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address[0], self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def _request(self, method, path):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        try:
            connection.request(method, path)
            response = connection.getresponse()
            return response.status, response.read().decode("utf-8", "replace")
        finally:
            connection.close()

    def test_each_page_is_served(self):
        for name in views.PAGES:
            with self.subTest(page=name):
                status, body = self._request("GET", f"/{name}")
                self.assertEqual(status, 200)
                self.assertIn("NFT transfer details" if name == "receipt" else "8415ex", body)

    def test_the_root_serves_the_receipt_page(self):
        status, body = self._request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("NFT transfer details", body)

    def test_an_unknown_path_is_404(self):
        status, _ = self._request("GET", "/nope")
        self.assertEqual(status, 404)

    def test_a_write_is_refused(self):
        status, _ = self._request("POST", "/receipt")
        self.assertEqual(status, 405)

    def test_the_console_binds_to_loopback_by_default(self):
        self.assertEqual(webui.DEFAULT_HOST, "127.0.0.1")


if __name__ == "__main__":
    unittest.main()

