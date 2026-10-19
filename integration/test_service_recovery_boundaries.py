"""Local HTTP service boundaries over the existing Stage 1--5 assembly.

Only the status server restarts; the same Exchange object is retained. These
checks do not demonstrate durable process recovery, real providers or signatures.
"""
import copy
from contextlib import contextmanager
import http.client
import threading
import unittest

from exchange import fixtures as F, stage5, webui
from exchange.errors import DomainError

RECEIPT = stage5.RECEIPT


@contextmanager
def console(exchange, authorizations=()):
    server = webui.serve(exchange, RECEIPT, authorization_ids=authorizations)
    worker = threading.Thread(target=server.serve_forever,
                              kwargs={"poll_interval": 0.01}, daemon=True)
    worker.start()
    try:
        yield server.server_address
    finally:
        server.shutdown()
        server.server_close()
        worker.join(2)
        if worker.is_alive():
            raise AssertionError("local status server did not stop")


def request(address, method, path):
    client = http.client.HTTPConnection(*address, timeout=2)
    try:
        client.request(method, path)
        response = client.getresponse()
        return response.status, response.read().decode("utf-8")
    finally:
        client.close()


class ServiceRecoveryBoundaries(unittest.TestCase):
    def test_stale_grant_after_console_restart_cannot_execute_prepared_trade(self):
        for path in stage5.PATHS:
            for invalidation, reason in (("revoke", "EX_AUTH_REVOKED"),
                                         ("disconnect", "EX_AUTH_SESSION_LOST")):
                with self.subTest(path=path, invalidation=invalidation):
                    ex, clock = F.exit_exchange(registration_path=path)
                    match, _ = F.funded_hop(ex, F.A, F.B, 1, "transfer-prepared",
                                           "session-a", "session-b", lock=False)
                    escrow = ex.lock_escrow(match, "escrow-prepared")
                    with console(ex, ("auth-buy-prepared",)) as address:
                        status, page = request(address, "GET", "/authorization")
                        self.assertEqual(status, 200)
                        self.assertNotIn(reason, page)
                        self.assertIn("<tr><th>Applies right now</th><td>yes</td></tr>", page)
                    if invalidation == "revoke":
                        ex.revoke_authorization("auth-buy-prepared")
                    else:
                        ex.disconnect_wallet(F.B)
                    before = copy.deepcopy(stage5.snapshot(ex))
                    movements = ex.payments.movements
                    with console(ex, ("auth-buy-prepared",)) as address:
                        status, page = request(address, "GET", "/authorization")
                        self.assertEqual(status, 200)
                        current = ex.authorization_state("auth-buy-prepared")
                        self.assertIs(current["applies"], False)
                        self.assertIn(reason, current["reasons"])
                        self.assertIn("<tr><th>Applies right now</th><td>no - original "
                                      "authorization checks did not pass</td></tr>", page)
                        self.assertNotIn(reason, page)
                        for _ in range(2):
                            with self.assertRaises(DomainError) as caught:
                                ex.execute_transfer(match, "transfer-prepared",
                                                    escrow_id=escrow.escrow_id)
                            self.assertEqual(caught.exception.code,
                                             "EX_TRANSFER_AUTHORIZATION_REFUSED")
                            self.assertIn(reason, caught.exception.detail)
                        self.assertEqual(request(address, "POST", "/authorization")[0], 405)
                        self.assertEqual(request(address, "GET", "/receipt")[0], 200)
                    self.assertEqual(stage5.snapshot(ex), before)
                    self.assertEqual(ex.payments.movements, movements)
                    self.assertEqual(len(ex.legs(RECEIPT)), 0)
                    self.assertEqual(ex.owner_of(RECEIPT), F.A)
                    self.assertEqual(ex.asset_control.returns, 0)
                    self.assertTrue(ex.voucher_desk is None or ex.voucher_desk._records == {})

    def test_unknown_suffix_refund_after_console_restart_never_releases_twice(self):
        for path in stage5.PATHS:
            with self.subTest(path=path):
                ex, clock = stage5.make_chain(path, outcomes={"refund:escrow-bc": "unknown"})
                requests = F.submit_all(ex)
                F.confirm(ex, requests[0], "prefix-confirmed")
                stage5.release(ex, 0)
                prefix = copy.deepcopy(ex.reconciliation(RECEIPT)["segments"][0])
                refusal, _ = F.refuse(ex, requests[1], "suffix-refused")
                ex.begin_rollback(RECEIPT, 1, F.rollback_authority(ex, 1, "service-rollback"))
                self.assertFalse(ex.advance_rollback(RECEIPT)["complete"])
                with console(ex) as address:
                    status, page = request(address, "GET", "/rollback")
                    self.assertEqual(status, 200)
                    self.assertIn("unknown", page)
                    self.assertIn("not complete until every step", page)
                movements = ex.payments.movements
                with console(ex) as address:
                    ex.resume_payments(RECEIPT)
                    self.assertFalse(ex.advance_rollback(RECEIPT)["complete"])
                    self.assertEqual(ex.payments.movements, movements)
                    self.assertEqual(request(address, "POST", "/rollback")[0], 405)
                    self.assertEqual(request(address, "GET", "/rollback")[0], 200)
                    ex.payments.resolve_unknown("refund:escrow-bc", "settled")
                    ex.resume_payments(RECEIPT)
                    self.assertTrue(ex.advance_rollback(RECEIPT)["complete"])
                    terminal_movements = ex.payments.movements
                    terminal_returns = ex.asset_control.returns
                    for _ in range(2):
                        self.assertEqual(ex.apply_registration_result(refusal)["disposition"],
                                         "idempotent")
                        ex.resume_payments(RECEIPT)
                        self.assertTrue(ex.advance_rollback(RECEIPT)["complete"])
                        with self.assertRaises(DomainError) as caught:
                            ex.release_segment(RECEIPT, 1,
                                F.release_authority(ex, 1, "forbidden-release"))
                        self.assertEqual(caught.exception.code, "EX_SEGMENT_NOT_RELEASABLE")
                    status, page = request(address, "GET", "/rollback")
                    self.assertEqual(status, 200)
                    self.assertIn("not reopened, reversed or re-collected", page)
                    self.assertEqual(request(address, "GET", "/evidence")[0], 200)
                self.assertEqual(ex.payments.movements, terminal_movements)
                self.assertEqual(ex.asset_control.returns, terminal_returns)
                self.assertEqual(ex.reconciliation(RECEIPT)["segments"][0], prefix)
                self.assertEqual(ex.owner_of(RECEIPT), F.B)
                self.assertEqual(ex.escrow_for_leg(RECEIPT, 1).status, "refunded")
                self.assertEqual(ex.escrow_for_leg(RECEIPT, 2).status, "refunded")
                self.assertTrue(ex.voucher_desk is None or ex.voucher_desk._records == {})
