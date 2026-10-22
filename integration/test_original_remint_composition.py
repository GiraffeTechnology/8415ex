"""Synthetic composition of original declaration, result and review ports."""
from copy import deepcopy
from html import escape
import unittest

from exchange.remint_evm_mapping import bind_remint_evm_arguments
from exchange.remint_operation_result import (
    decode_remint_operation_result, RemintResultRefused,
)
from exchange.remint_review import WORDS
from integration import test_remint_evm_mapping as mappings
from integration import test_remint_operation_result as results
from integration import test_remint_clause_changes as clauses
from integration import test_recovered_workbench_ui as recovered


class OriginalRemintCompositionContracts(unittest.TestCase):
    def test_prepared_declaration_and_actual_result_keep_independent_token_identities(self):
        scope, history = mappings.prepared()
        original = deepcopy((scope, history))
        plan = bind_remint_evm_arguments(scope, history, mappings.original_mapping)
        recorded = decode_remint_operation_result(results.result(token=9),
            expected_digest=results.DIGEST)
        self.assertEqual(plan["argumentsHex"][2:66], "aa"*32)
        self.assertEqual(int(plan["argumentsHex"][66:130], 16), int(scope["tokenId"]))
        self.assertEqual(recorded["newTokenId"], "9")
        self.assertEqual((scope, history), original)
        self.assertEqual(plan["scope"]["nativeOperationId"], scope["nativeOperationId"])
        self.assertFalse(plan["walletOperationCreated"])
        self.assertFalse(plan["dispatchAuthorized"])
        self.assertFalse(recorded["replayAllowed"])
        self.assertFalse(recorded["releaseAllowed"])
        self.assertEqual(recorded["receiptFinality"], "NOT_ESTABLISHED")

    def test_zero_read_never_authorizes_replay_or_discards_prepared_history(self):
        scope, history = mappings.prepared()
        before = deepcopy(history)
        plan = bind_remint_evm_arguments(scope, history, mappings.original_mapping)
        observation = decode_remint_operation_result(bytes(64),
            expected_digest=results.DIGEST)
        self.assertEqual(observation["status"], "NOT_RECORDED_AT_READ")
        self.assertEqual(observation["nativePendingAbsence"], "NOT_ESTABLISHED")
        self.assertIsNone(observation["newTokenId"])
        self.assertFalse(observation["replayAllowed"])
        self.assertFalse(observation["releaseAllowed"])
        self.assertFalse(plan["dispatchAuthorized"])
        self.assertEqual(history, before)

    def test_history_digest_is_not_substituted_for_original_contract_result_digest(self):
        scope, history = mappings.prepared()
        plan = bind_remint_evm_arguments(scope, history, mappings.original_mapping)
        before = deepcopy(plan)
        with self.assertRaises(RemintResultRefused):
            decode_remint_operation_result(results.result(),
                expected_digest=scope["intentDigest"])
        with self.assertRaises(RemintResultRefused):
            decode_remint_operation_result(results.result(results.OTHER),
                expected_digest=results.DIGEST)
        self.assertEqual(plan, before)
        self.assertFalse(plan["nativeOutcomeVerified"])

    def test_recovered_editor_and_complete_ordered_clause_diff_coexist_in_six_locales(self):
        ui = recovered.RecoveredWorkbenchUITests("runTest")
        ui.setUp()
        self.addCleanup(ui.doCleanups)
        review = ui.host.review
        pairs = []
        def pair(old_id, new_id):
            value = (clauses.detail(old_id, [("Quantity", "One whole receipt"),
                                           ("Condition", "Original complete clause")]),
                     clauses.detail(new_id, [("Quantity", "One whole receipt"),
                                           ("Condition", "Proposed complete clause"),
                                           ("Location", "Original public location")]))
            pairs.append(deepcopy(value))
            return value
        review.read_original_pair = pair
        result = ui.compose(read_draft_specifications=ui.read_specs,
            collateral_selection=True, scenario_selection=True)
        server = ui.start(result)
        changes = ui.db.total_changes
        for locale in WORDS:
            status, body = ui.request(server, "/remint-review?lang=" + locale)
            self.assertEqual(status, 200)
            self.assertIn('data-remint-clause-changes="1"', body)
            self.assertIn(escape(WORDS[locale][1]), body)
            self.assertIn(escape(WORDS[locale][2]), body)
            self.assertIn("Original complete clause", body)
            self.assertIn("Proposed complete clause", body)
            self.assertIn("Original public location", body)
            self.assertEqual(body.count("<pre>One whole receipt</pre>"), 2)
            self.assertEqual(ui.request(server, "/remint-draft?lang=" + locale)[0], 200)
            self.assertEqual(ui.request(server, "/collateral?lang=" + locale)[0], 200)
        self.assertEqual(len(pairs), len(WORDS))
        self.assertEqual(ui.db.total_changes, changes)
        self.assertEqual(ui.host.calls, [])
