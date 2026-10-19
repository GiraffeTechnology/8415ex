"""Synthetic existing-route contract cases. No real Oracle or chain."""
from copy import deepcopy
from dataclasses import replace
import unittest

from exchange.errors import DomainError
from exchange.model import Asset
from exchange.settlement import EscrowPosition
from exchange.principal_journal_contract import PrincipalBinding
from exchange.oracle_projection_join import OracleProjectionJoin, PREFIX

A = "0x" + "1" * 40
B = "0x" + "2" * 40
TOKEN = "0x" + "3" * 40
NFT = "0x" + "4" * 40
SOURCE = {"chainId": "11155111", "contract": "0x" + "5" * 40, "registerId": "0x" + "6" * 64}
COMMITMENT = "0x" + "7" * 64


def binding():
    return PrincipalBinding(EscrowPosition("escrow-3", "receipt-1", 3, A, B, TOKEN, 10),
                            Asset(11155111, NFT, 19), "transfer-3", TOKEN, 6,
                            "native-op-3", "journal-3")


class Transport:
    def __init__(self, counts=None):
        self.calls = []
        self.counts = list(counts or ["3", "3"])
        self.entry = dict(version="2", holder=A, effectiveAt="100", supersededAt="0",
                          recordCommitment=COMMITMENT, previousCommitment="0x" + "8" * 64,
                          registryReference="0x" + "9" * 64)
        self.final = False
        self.mutate = lambda path, body: body
        self.status = 200

    def __call__(self, method, path):
        self.calls.append((method, path))
        body = {"tokenId": "19", "source": deepcopy(SOURCE)}
        if path == PREFIX + "/19":
            body.update(registerId=SOURCE["registerId"], entryCount=self.counts.pop(0))
        elif path == PREFIX + "/19/entry/version/2":
            body["entry"] = deepcopy(self.entry)
        elif "/holder/as-of/" in path:
            body.update(instant=path.rsplit("/", 1)[-1], holder=self.entry["holder"])
        elif "/finality/as-of/" in path:
            body.update(instant=path.rsplit("/", 1)[-1], final=self.final)
        else:
            raise AssertionError("unexpected route")
        return self.status, self.mutate(path, body)


class OracleProjectionJoinTests(unittest.TestCase):
    def setUp(self):
        self.b = binding()
        self.transport = Transport()
        self.proofs = []
        self.reader = OracleProjectionJoin(SOURCE, self.transport, self.verify)

    def verify(self, binding, facts):
        self.proofs.append(deepcopy(facts))
        return True

    def inspect(self, **kwargs):
        terms = dict(version="2", record_commitment=COMMITMENT, as_of="110", cutoff="105")
        terms.update(kwargs)
        return self.reader.inspect(self.b, **terms)

    def test_existing_oracle_routes_only_and_no_atomic_authority(self):
        r = self.inspect()
        self.assertEqual(len(self.transport.calls), 5)
        self.assertTrue(all(m == "GET" and p.startswith(PREFIX + "/19") for m, p in self.transport.calls))
        self.assertFalse(r["atomicSettlementAuthority"])
        self.assertFalse(r["holderWritten"])
        self.assertFalse(r["fundsDispatched"])
        self.assertEqual(r["entry"]["registryReference"], "0x" + "9" * 64)
        self.assertEqual(r["nativeOperationId"], "native-op-3")

    def test_holder_finality_and_cutoff_stay_separate(self):
        r = self.inspect(cutoff="99")
        self.assertTrue(r["registeredHolderIsBuyer"])
        self.assertFalse(r["finalAsOf"])
        self.assertFalse(r["withinCutoff"])
        self.assertEqual(r["entry"]["effectiveAt"], "100")
        self.assertFalse(r["atomicSettlementAuthority"])

    def test_same_token_different_source_refused(self):
        for key, value in (("chainId", "560048"), ("contract", NFT),
                           ("registerId", "0x" + "a" * 64)):
            def mutate(path, body, key=key, value=value):
                body["source"][key] = value
                return body
            self.transport = Transport()
            self.transport.mutate = mutate
            self.reader = OracleProjectionJoin(SOURCE, self.transport, self.verify)
            with self.assertRaises(DomainError):
                self.inspect()
        self.assertEqual(self.proofs, [])

    def test_concurrent_append_retries_complete_read_once(self):
        self.transport = Transport(["3", "4", "4", "4"])
        self.reader = OracleProjectionJoin(SOURCE, self.transport, self.verify)
        r = self.inspect()
        self.assertEqual(r["entryCount"], "4")
        self.assertEqual(len(self.transport.calls), 10)
        self.assertEqual(len(self.proofs), 1)

    def test_continuous_churn_refused_without_authority_callback(self):
        self.transport = Transport(["3", "4", "4", "5"])
        self.reader = OracleProjectionJoin(SOURCE, self.transport, self.verify)
        with self.assertRaises(DomainError):
            self.inspect()
        self.assertEqual(len(self.transport.calls), 10)
        self.assertEqual(self.proofs, [])

    def test_entry_commitment_version_and_interval(self):
        for key, value in (("version", "3"), ("recordCommitment", "0x" + "a" * 64),
                           ("effectiveAt", "111"), ("supersededAt", "110")):
            self.transport = Transport(); self.transport.entry[key] = value
            self.reader = OracleProjectionJoin(SOURCE, self.transport, self.verify)
            with self.assertRaises(DomainError):
                self.inspect()
        self.assertEqual(self.proofs, [])

    def test_exact_decimal_bool_and_leading_zero_refused(self):
        for value in ("02", 2, True, "18446744073709551616"):
            with self.assertRaises(DomainError):
                self.inspect(version=value)
        self.assertEqual(self.transport.calls, [])
        for value in ("00", "18446744073709551616"):
            with self.assertRaises(DomainError):
                self.inspect(as_of=value)

    def test_refused_unavailable_and_missing_mapping(self):
        for status in (404, 503, True):
            self.transport = Transport(); self.transport.status = status
            self.reader = OracleProjectionJoin(SOURCE, self.transport, self.verify)
            with self.assertRaises(DomainError):
                self.inspect()
        self.transport = Transport()
        self.reader = OracleProjectionJoin(SOURCE, self.transport, lambda *args: False)
        with self.assertRaises(DomainError):
            self.inspect()

    def test_source_metadata_token_instant_and_extra_fields(self):
        for mutation in (
            lambda p, b: dict(b, tokenId="20"),
            lambda p, b: dict(b, extra="untrusted"),
            lambda p, b: dict(b, registerId="0x" + "a" * 64) if p == PREFIX + "/19" else b,
            lambda p, b: dict(b, instant="111") if "/holder/as-of/" in p else b,
        ):
            self.transport = Transport(); self.transport.mutate = mutation
            self.reader = OracleProjectionJoin(SOURCE, self.transport, self.verify)
            with self.assertRaises(DomainError):
                self.inspect()

    def test_holder_mismatch_and_non_boolean_finality(self):
        for final, mismatch in ((1, False), (False, True)):
            self.transport = Transport(); self.transport.final = final
            if mismatch:
                self.transport.mutate = lambda p, b: dict(b, holder=B) if "/holder/as-of/" in p else b
            self.reader = OracleProjectionJoin(SOURCE, self.transport, self.verify)
            with self.assertRaises(DomainError):
                self.inspect()

    def test_mapping_covers_native_global_leg_and_detaches(self):
        r = self.inspect()
        self.assertEqual(self.proofs[0]["bindingDigest"], self.b.binding_digest)
        self.assertEqual(self.proofs[0]["journalReference"], "journal-3")
        r["entry"]["holder"] = B
        r["source"]["registerId"] = "0x" + "a" * 64
        self.assertEqual(self.proofs[0]["entry"]["holder"], A)
        self.assertEqual(SOURCE["registerId"], "0x" + "6" * 64)
        self.assertEqual(self.b.position.leg_index, 3)

    def test_body_limit_and_absent_version(self):
        self.transport = Transport(["1"])
        self.reader = OracleProjectionJoin(SOURCE, self.transport, self.verify)
        with self.assertRaises(DomainError):
            self.inspect()
        self.transport = Transport()
        self.transport.mutate = lambda p, b: dict(b, padding="x" * 65536)
        self.reader = OracleProjectionJoin(SOURCE, self.transport, self.verify)
        with self.assertRaises(DomainError):
            self.inspect()
