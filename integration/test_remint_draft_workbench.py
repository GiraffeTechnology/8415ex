"""Synthetic original-host HTTP contracts; no native signing or mint execution."""
from dataclasses import replace
from html import escape
import http.client
import socket
import threading
import unittest
from urllib.parse import urlencode

from exchange.remint_draft_workbench import RemintDraftEditorBinding, mount_remint_draft, WORDS
from integration import test_serialized_workbench_composition as original_host
from integration.test_mint_specification_codec import specification


class RemintDraftWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.host = original_host.SerializedWorkbenchCompositionTests()
        self.host.setUp()
        self.addCleanup(self.host.doCleanups)
        self.old = specification()
        self.seed = replace(self.old, receipt=replace(self.old.receipt,
            asset=replace(self.old.receipt.asset, token_id=8)))
        self.mode = "ok"
        self.read_calls = []
        def read(receipt_id):
            self.read_calls.append(receipt_id)
            if self.mode == "unavailable":
                raise RuntimeError("private source diagnostic must not be served")
            if self.mode == "wrong-receipt":
                return replace(self.old, receipt=replace(self.old.receipt, receipt_id="other")), self.seed
            return self.old, self.seed
        editor = RemintDraftEditorBinding(self.host.access, "receipt-1", read)
        self.server = mount_remint_draft(self.host.server, editor)
        self.worker = threading.Thread(target=self.server.serve_forever,
            kwargs={"poll_interval": 0.02}, daemon=True)
        self.worker.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.worker.join(3)

    def request(self, method, path, body=None, **extra):
        headers = {}
        if method == "POST":
            headers = {"Content-Type": "application/x-www-form-urlencoded", "Origin": self.server.origin}
        headers.update(extra)
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode()
        finally:
            connection.close()

    def form(self, text="Unsigned proposed bill terms", locale="en", **extra):
        fields = {"csrf": self.server.csrf, "lang": locale, "billTerms": text}
        fields.update(extra)
        return urlencode(fields)

    def test_all_six_locales_render_full_bound_terms_and_unsigned_editor(self):
        for locale, words in WORDS.items():
            with self.subTest(locale=locale):
                status, headers, body = self.request("GET", "/remint-draft?lang=" + locale)
                self.assertEqual(status, 200)
                self.assertIn(words[0], body)
                self.assertIn(words[5], body)
                self.assertIn(self.old.bill_terms, body)
                self.assertIn('<textarea name="billTerms"', body)
                self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.host.calls, [])

    def test_preview_adds_deletes_and_changes_full_text_without_mutating_original(self):
        text = "Changed clause.\nAdded clause <keep full wording>."
        status, _, body = self.request("POST", "/remint-draft", self.form(text, "fr"))
        self.assertEqual(status, 200)
        self.assertIn(escape(text), body)
        self.assertIn(self.old.bill_terms, body)
        self.assertIn(WORDS["fr"][4], body)
        self.assertEqual(self.seed.bill_terms, self.old.bill_terms)
        status, _, next_page = self.request("GET", "/remint-draft?lang=fr")
        self.assertEqual(status, 200)
        self.assertNotIn("Added clause", next_page)
        self.assertEqual(self.host.calls, [])

    def test_model_identity_and_private_mapping_are_not_rendered(self):
        status, _, body = self.request("GET", "/remint-draft")
        self.assertEqual(status, 200)
        for forbidden in (self.old.receipt.origin_account, self.old.receipt.asset.contract,
                          self.old.original_document_mapping, self.old.controlled_access_mapping,
                          "proposedFactSHA256", "originalFactSHA256"):
            self.assertNotIn(forbidden, body)

    def test_foreign_origin_and_invalid_csrf_fail_before_source_reader(self):
        before = len(self.read_calls)
        self.assertEqual(self.request("POST", "/remint-draft", self.form(), Origin="https://foreign.invalid")[0], 403)
        status, _, body = self.request("POST", "/remint-draft", self.form(csrf="wrong"))
        self.assertEqual(status, 403)
        self.assertNotIn(self.server.csrf, body)
        self.assertEqual(self.request("POST", "/remint-draft", self.form(csrf="\u975eASCII"))[0], 403)
        self.assertEqual(len(self.read_calls), before)

    def test_extra_identity_authorization_fields_or_address_text_do_not_reach_editor(self):
        before = len(self.read_calls)
        for raw in (self.form(receiptId="other"), self.form(authorization="approved"),
                    self.form("0x" + "a" * 40), self.form() + "&lang=en"):
            with self.subTest(raw=raw):
                self.assertEqual(self.request("POST", "/remint-draft", raw)[0], 400)
        self.assertEqual(len(self.read_calls), before)
        self.assertEqual(self.host.calls, [])

    def test_missing_source_is_localized_without_raw_error_or_partial_terms(self):
        self.mode = "unavailable"
        for method, path, body in (("GET", "/remint-draft?lang=zh-Hans", None),
                                  ("POST", "/remint-draft", self.form(locale="zh-Hans"))):
            status, _, output = self.request(method, path, body)
            self.assertEqual(status, 503)
            self.assertIn(WORDS["zh-Hans"][6], output)
            self.assertNotIn("private source diagnostic", output)
            self.assertNotIn(self.old.bill_terms, output)

    def test_source_receipt_drift_and_request_selected_source_are_refused(self):
        self.mode = "wrong-receipt"
        self.assertEqual(self.request("GET", "/remint-draft")[0], 503)
        before = len(self.read_calls)
        for path in ("/remint-draft?receipt=other", "/remint-draft?lang=en&lang=ja", "/remint-draft?lang=unknown"):
            self.assertEqual(self.request("GET", path)[0], 400)
        self.assertEqual(len(self.read_calls), before)

    def test_original_gas_and_readonly_review_routes_survive_mount(self):
        self.assertEqual(self.request("GET", "/gas")[0], 200)
        status, _, body = self.request("GET", "/remint-review?lang=en")
        self.assertEqual(status, 200)
        self.assertIn("Original terms", body)
        self.assertEqual(self.host.calls, [])

    def test_early_eof_refuses_before_editor_read_or_any_operation(self):
        before = len(self.read_calls)
        raw = self.form().encode()
        connection = socket.create_connection(self.server.server_address, timeout=3)
        try:
            headers = ("POST /remint-draft HTTP/1.1\r\nHost: " + self.server.origin.removeprefix("http://")
                + "\r\nOrigin: " + self.server.origin + "\r\nContent-Type: application/x-www-form-urlencoded"
                + "\r\nContent-Length: " + str(len(raw) + 10) + "\r\n\r\n").encode()
            connection.sendall(headers + raw)
            connection.shutdown(socket.SHUT_WR)
            response = http.client.HTTPResponse(connection)
            response.begin()
            body = response.read().decode()
            self.assertEqual(response.status, 400)
            self.assertNotIn(self.server.csrf, body)
            self.assertEqual(len(self.read_calls), before)
            self.assertEqual(self.host.calls, [])
        finally:
            connection.close()

    def test_unsupported_form_framing_and_query_close_without_source_read(self):
        before = len(self.read_calls)
        for path, headers in (("/remint-draft?lang=en", {}),
                              ("/remint-draft", {"Content-Type": "application/json"}),
                              ("/remint-draft", {"Transfer-Encoding": "chunked"})):
            status, response_headers, _ = self.request("POST", path, self.form(), **headers)
            self.assertEqual(status, 400)
            self.assertEqual(response_headers["Connection"], "close")
        self.assertEqual(len(self.read_calls), before)
