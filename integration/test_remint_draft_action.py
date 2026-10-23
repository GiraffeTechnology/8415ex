"""Synthetic original remint form transport; author execution NOT_RUN."""
from html import escape
from dataclasses import replace
import http.client
import re
import threading
import unittest
from urllib.parse import urlencode

from exchange.remint_draft_action import RemintDraftActionBinding, mount_remint_draft_action, WORDS
from exchange.remint_draft_workbench import RemintDraftEditorBinding
from exchange.remint_terms import prepare_remint_terms
from exchange.remint_workbench import RemintWorkbenchServer
from integration import test_checkpointed_remint as original
from integration import test_serialized_workbench_composition as original_ui


class RemintActionHTTPContracts(unittest.TestCase):
    def setUp(self):
        self.host = original.CheckpointedRemintTests("runTest")
        self.host.setUp()
        self.addCleanup(self.host.doCleanups)
        self.ui = original_ui.SerializedWorkbenchCompositionTests("runTest")
        self.ui.setUp()
        self.addCleanup(self.ui.doCleanups)
        self.reads, self.enquiries = [], []
        self.unavailable, self.lose_reply = False, False
        self.enquiry = None
        def read(receipt_id):
            self.reads.append(receipt_id)
            if self.unavailable:
                raise RuntimeError("PRIVATE_DECLARATION_DIAGNOSTIC")
            return self.host.old, self.host.new
        self.editor = RemintDraftEditorBinding(self.host.fixture.bridge.access,
            self.host.old.receipt.receipt_id, read)
        self.options = {"bill_terms": "Reviewed complete replacement conditions"}
        old, proposed = self.editor.draft_specifications(**self.options)
        digest = prepare_remint_terms(old, proposed, self.host.verify, original.bill)["historyDigest"]
        self.scope = dict(self.host.scope, intentDigest=digest)
        self.action = RemintDraftActionBinding(self.host.fixture.bridge, self.editor,
            self.scope, 0, self.host.verify, original.bill, self.enquire, self.execute,
            history_store=self.host.history, draft_options=self.options)
        binding = self.host.fixture.bridge.access.bind_runtime(self.editor.receipt_id)
        self.server = RemintWorkbenchServer(binding, gas_page=self.ui.gas,
            registration_sources=self.ui.server.registration_sources,
            current_time=lambda: 110, commit="c" * 40, tree="d" * 40, port=0)
        self.addCleanup(self.server.server_close)
        mount_remint_draft_action(self.server, self.action)
        self.reads.clear()

    def enquire(self, scope):
        self.enquiries.append(scope)
        return self.enquiry

    def execute(self, scope, history):
        result = self.host.execute(scope, history)
        if self.lose_reply:
            raise TimeoutError("PRIVATE_NATIVE_DIAGNOSTIC")
        return result

    def request(self, path, method="GET", body=None, **headers):
        response, errors = [], []
        if method == "POST":
            headers = dict({"Origin": self.server.origin,
                "Content-Type": "application/x-www-form-urlencoded"}, **headers)
        def client():
            connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
            try:
                connection.request(method, path, body=body, headers=headers)
                result = connection.getresponse()
                response.append((result.status, result.read().decode()))
            except BaseException as error:
                errors.append(error)
            finally:
                connection.close()
        worker = threading.Thread(target=client, daemon=True)
        worker.start()
        # Handle on the original thread, retaining the original SQLite identity.
        self.server.timeout = 3
        self.server.handle_request()
        worker.join(4)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        return response[0]

    def form(self, **changes):
        status, body = self.request("/remint-action")
        self.assertEqual(status, 200)
        proposal = re.search('name="proposal" value="([0-9a-f]{64})"', body).group(1)
        return dict({"csrf": self.server.csrf, "lang": "en",
                     "proposal": proposal, "revision": "0"}, **changes)

    def test_all_locales_show_exact_readonly_proposal_without_private_identity_or_effect(self):
        before = self.host.fixture.claim_db.total_changes
        for locale in WORDS:
            status, body = self.request("/remint-action?lang=" + locale)
            self.assertEqual(status, 200)
            self.assertIn(escape(WORDS[locale][0]), body)
            self.assertIn("<fieldset disabled>", body)
            self.assertIn(self.options["bill_terms"], body)
            self.assertIn('action="/remint-action"', body)
            for private in (self.host.old.receipt.origin_account,
                            self.host.old.receipt.asset.contract,
                            self.host.old.controlled_access_mapping):
                self.assertNotIn(private, body)
        self.assertEqual(len(self.reads), 6)
        self.assertEqual(self.host.calls, [])
        self.assertEqual(self.enquiries, [])
        self.assertEqual(self.host.fixture.claim_db.total_changes, before)

    def test_exact_form_enters_existing_claim_history_checkpoint_and_one_native_call(self):
        fields = self.form()
        self.reads.clear()
        status, body = self.request("/remint-action", "POST", urlencode(fields))
        self.assertEqual(status, 202)
        self.assertIn(escape(WORDS["en"][6]), body)
        self.assertEqual(self.reads, [self.editor.receipt_id])
        self.assertEqual(len(self.host.calls), 1)
        self.assertEqual(self.host.history.read(self.scope)["history"]["newDeclaration"]["billTerms"],
                         self.options["bill_terms"])
        self.assertEqual(self.host.fixture.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")

    def test_csrf_and_origin_fail_before_original_reads_or_enquiry(self):
        fields = self.form(csrf="wrong")
        self.reads.clear()
        self.assertEqual(self.request("/remint-action", "POST", urlencode(fields))[0], 403)
        fields["csrf"] = self.server.csrf
        self.assertEqual(self.request("/remint-action", "POST", urlencode(fields), Origin="https://other.invalid")[0], 403)
        self.assertEqual(self.reads, [])
        self.assertEqual(self.enquiries, [])
        self.assertEqual(self.host.calls, [])

    def test_stale_full_proposal_or_revision_cannot_enter_the_original_gate(self):
        fields = self.form()
        for changes in ({"proposal": "0" * 64}, {"revision": "1"}):
            changed = dict(fields, **changes)
            self.assertEqual(self.request("/remint-action", "POST", urlencode(changed))[0], 409)
        self.assertEqual(self.enquiries, [])
        self.assertEqual(self.host.calls, [])
        self.assertIsNone(self.host.fixture.journal.lookup(self.scope["nativeOperationId"]))

    def test_lost_reply_then_same_form_uses_original_enquiry_without_resend(self):
        fields = self.form()
        self.lose_reply = True
        status, body = self.request("/remint-action", "POST", urlencode(fields))
        self.assertEqual(status, 503)
        self.assertIn(escape(WORDS["en"][7]), body)
        self.assertNotIn("PRIVATE_NATIVE_DIAGNOSTIC", body)
        self.enquiry = {"status": "unknown"}
        self.assertEqual(self.request("/remint-action", "POST", urlencode(fields))[0], 202)
        self.assertEqual(len(self.host.calls), 1)
        self.assertEqual(self.host.fixture.checkpoint.read(
            self.host.fixture.bridge.pre_effect_scope(self.scope))["generation"], 1)

    def test_missing_source_and_bad_form_remain_local_to_action_route(self):
        fields = self.form()
        self.unavailable = True
        status, body = self.request("/remint-action")
        self.assertEqual(status, 503)
        self.assertNotIn("PRIVATE_DECLARATION_DIAGNOSTIC", body)
        self.assertEqual(self.request("/market")[0], 200)
        self.assertEqual(self.request("/remint-action", "POST", urlencode(fields) + "&lang=fr")[0], 400)
        self.assertEqual(self.host.calls, [])

    def test_original_digest_still_refuses_even_when_local_form_token_matches(self):
        self.action._binding["intentDigest"] = self.host.scope["intentDigest"]
        fields = self.form()
        self.assertEqual(self.request("/remint-action", "POST", urlencode(fields))[0], 409)
        self.assertEqual(self.host.calls, [])
        self.assertIsNone(self.host.fixture.journal.lookup(self.scope["nativeOperationId"]))

    def test_mount_is_idempotent_and_does_not_replace_other_original_routes(self):
        handler = self.server.RequestHandlerClass
        self.assertIs(mount_remint_draft_action(self.server, self.action), self.server)
        self.assertIs(self.server.RequestHandlerClass, handler)
        self.assertEqual(self.request("/market")[0], 200)
        self.assertEqual(self.request("/remint-result")[0], 503)
        self.assertEqual(self.reads, [])
        self.assertEqual(self.host.calls, [])


    def test_complete_original_and_replacement_conditions_precede_the_execute_button(self):
        self.host.new = replace(self.host.new,
            template=replace(self.host.new.template, template_id="replacement-template",
                version="template-version-two", standard_reference="Replacement standard <reviewed>"),
            voucher_format=replace(self.host.new.voucher_format, format_id="replacement-format",
                version="format-version-three", path="REG_ELECTRONIC"),
            receipt=replace(self.host.new.receipt, registration_path="REG_ELECTRONIC"))
        before = self.host.fixture.claim_db.total_changes
        for locale in WORDS:
            status, body = self.request("/remint-action?lang=" + locale)
            self.assertEqual(status, 200)
            for value in (self.host.old.template.standard_reference, "replacement-template",
                    "template-version-two", "Replacement standard <reviewed>",
                    self.host.old.voucher_format.format_id, "replacement-format",
                    "format-version-three", "REG_DIRECT", "REG_ELECTRONIC"):
                self.assertIn(escape(value), body)
                self.assertLess(body.index(escape(value)), body.index('type="submit"'))
            self.assertNotIn("Replacement standard <reviewed>", body)
            self.assertIn('data-bound-business="original"', body)
            self.assertIn('data-bound-business="replacement"', body)
            for private in (self.host.old.receipt.origin_account,
                    self.host.old.receipt.asset.contract, self.host.old.receipt.receipt_id,
                    self.host.old.original_document_mapping, self.host.old.controlled_access_mapping):
                self.assertNotIn(private, body)
        self.assertEqual(self.host.calls, [])
        self.assertEqual(self.enquiries, [])
        self.assertEqual(self.host.fixture.claim_db.total_changes, before)


    def test_private_identity_in_newly_displayed_terms_fails_closed_without_mutating_original_facts(self):
        originals = (self.host.old, self.host.new)
        private = originals[0].receipt.origin_account
        try:
            for side in ("old", "new"):
                for field in ("standard_reference", "commodity_scope"):
                    self.host.old, self.host.new = originals
                    specification = getattr(self.host, side)
                    poisoned = replace(specification, template=replace(specification.template,
                        **{field: "Public-looking condition " + private}))
                    setattr(self.host, side, poisoned)
                    for locale in ("en", "ja"):
                        status, body = self.request("/remint-action?lang=" + locale)
                        self.assertEqual(status, 503)
                        self.assertNotIn(private, body)
                        self.assertIn(escape(WORDS[locale][3]), body)
                    self.assertIs(getattr(self.host, side), poisoned)
                    self.assertEqual(getattr(poisoned.template, field),
                        "Public-looking condition " + private)
                    self.assertEqual(self.request("/market")[0], 200)
        finally:
            self.host.old, self.host.new = originals
        self.assertEqual(self.host.calls, [])
        self.assertEqual(self.enquiries, [])
