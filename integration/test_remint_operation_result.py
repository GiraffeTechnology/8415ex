"""Synthetic definitions only; no RPC, product runtime or chain writes."""
import unittest

from exchange.remint_operation_result import (
    RemintResultRefused, decode_remint_operation_result,
)


DIGEST = "0x" + "12" * 32
OTHER = "0x" + "34" * 32


def result(digest=DIGEST, token=7):
    return bytes.fromhex(digest[2:]) + token.to_bytes(32, "big")


class RemintOperationResultTest(unittest.TestCase):
    def test_matching_original_digest_and_token(self):
        observed = decode_remint_operation_result(result(), expected_digest=DIGEST)
        self.assertEqual(observed["status"], "RECORDED")
        self.assertEqual(observed["digest"], DIGEST)
        self.assertEqual(observed["newTokenId"], "7")
        self.assertFalse(observed["replayAllowed"])
        self.assertFalse(observed["releaseAllowed"])
        self.assertEqual(observed["receiptFinality"], "NOT_ESTABLISHED")
        self.assertEqual(observed["businessAcceptance"], "NOT_ESTABLISHED")

    def test_zero_result_is_not_authenticated_native_absence(self):
        observed = decode_remint_operation_result(bytes(64), expected_digest=DIGEST)
        self.assertEqual(observed["status"], "NOT_RECORDED_AT_READ")
        self.assertIsNone(observed["digest"])
        self.assertIsNone(observed["newTokenId"])
        self.assertEqual(observed["nativePendingAbsence"], "NOT_ESTABLISHED")
        self.assertFalse(observed["replayAllowed"])
        self.assertFalse(observed["releaseAllowed"])

    def test_json_rpc_hex_and_bytes_are_identical(self):
        raw = result()
        self.assertEqual(
            decode_remint_operation_result("0x" + raw.hex().upper(),
                                           expected_digest=DIGEST),
            decode_remint_operation_result(raw, expected_digest=DIGEST))

    def test_uint256_max_remains_exact_decimal_string(self):
        token = 2 ** 256 - 1
        observed = decode_remint_operation_result(result(token=token),
                                                  expected_digest=DIGEST)
        self.assertEqual(observed["newTokenId"], str(token))

    def test_conflicting_original_digest_is_refused(self):
        with self.assertRaises(RemintResultRefused):
            decode_remint_operation_result(result(OTHER), expected_digest=DIGEST)

    def test_partial_or_trailing_abi_and_non_bytes_are_refused(self):
        for raw in (b"", bytes(32), bytes(63), bytes(65), bytes(96),
                    bytearray(64), memoryview(bytes(64)), None, 0,
                    "0x", "0x" + "0" * 127, "0x" + "g" * 128,
                    "0X" + "0" * 128, "0x" + "0" * 128 + "\n"):
            with self.subTest(raw=type(raw).__name__):
                with self.assertRaises(RemintResultRefused):
                    decode_remint_operation_result(raw, expected_digest=DIGEST)

    def test_half_empty_contract_record_is_refused(self):
        for raw in (result("0x" + "0" * 64, 7), result(DIGEST, 0)):
            with self.assertRaises(RemintResultRefused):
                decode_remint_operation_result(raw, expected_digest=DIGEST)

    def test_expected_digest_is_original_nonzero_word_only(self):
        for digest in (None, 1, bytes(32), "native_operation", "12" * 32,
                       "0x" + "0" * 64, DIGEST + "\n", "0x" + "A" * 64):
            with self.subTest(digest=digest):
                with self.assertRaises(RemintResultRefused):
                    decode_remint_operation_result(result(), expected_digest=digest)


if __name__ == "__main__":
    unittest.main()
