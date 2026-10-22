"""Synthetic original ABI result definitions; no RPC or product effects."""
from copy import deepcopy
import unittest
from exchange.remint_read_results import (
    RemintReadResultRefused, decode_remint_declaration, decode_remint_link,
)


def word(value):
    return value.to_bytes(32, "big")


def declaration(currencies=(4, 5)):
    return b"".join(word(n) for n in (32, 1, 2, 3, 128, len(currencies), *currencies))


class RemintReadResultContracts(unittest.TestCase):
    def test_complete_retained_declaration_preserves_all_original_words(self):
        raw = declaration((4, 5, 2**256-1))
        result = decode_remint_declaration(raw)
        self.assertEqual(result, {
            "billKey": "0x"+word(1).hex(), "termsHash": "0x"+word(2).hex(),
            "currencyDeclarationHash": "0x"+word(3).hex(),
            "allowedCurrencies": ["0x"+word(n).hex() for n in (4, 5, 2**256-1)]})
        self.assertNotIn("live", result)
        self.assertNotIn("burned", result)

    def test_hex_and_one_currency_match_bytes_without_reordering(self):
        raw = declaration((9,))
        self.assertEqual(decode_remint_declaration("0x"+raw.hex().upper()),
                         decode_remint_declaration(raw))
        ordered = decode_remint_declaration(declaration((9, 7)))
        self.assertEqual(ordered["allowedCurrencies"],
                         ["0x"+word(9).hex(), "0x"+word(7).hex()])

    def test_noncanonical_overlapping_or_shifted_offsets_are_refused(self):
        for offset in (0, 64, 96, 160, 2**256-1):
            for index in (0, 128):
                raw = bytearray(declaration())
                raw[index:index+32] = word(offset)
                with self.assertRaises(RemintReadResultRefused):
                    decode_remint_declaration(bytes(raw))

    def test_truncated_trailing_empty_and_inconsistent_lengths_are_refused(self):
        original = declaration()
        bad = [b"", original[:-1], original[:-32], original+word(0),
               declaration(()), original[:160]+word(3)+original[192:],
               original[:160]+word(2**256-1)+original[192:]]
        for raw in bad:
            with self.assertRaises(RemintReadResultRefused):
                decode_remint_declaration(raw)

    def test_zero_hashes_and_duplicate_currency_words_are_refused(self):
        for index in (32, 64, 96, 192):
            raw = bytearray(declaration())
            raw[index:index+32] = bytes(32)
            with self.assertRaises(RemintReadResultRefused):
                decode_remint_declaration(bytes(raw))
        with self.assertRaises(RemintReadResultRefused):
            decode_remint_declaration(declaration((4, 4)))

    def test_malformed_types_hex_and_explicit_response_bounds_are_refused(self):
        for raw in (None, True, [], bytearray(declaration()), "0X00",
                    "0x0", "0xGG", "0x 00", "0x00\n"):
            with self.assertRaises(RemintReadResultRefused):
                decode_remint_declaration(raw)
        for bound in (True, 0, 31, "224"):
            with self.assertRaises(RemintReadResultRefused):
                decode_remint_declaration(declaration((4,)), maximum_bytes=bound)
        with self.assertRaises(RemintReadResultRefused):
            decode_remint_declaration(declaration(), maximum_bytes=224)
        self.assertEqual(len(decode_remint_declaration(
            declaration((4,)), maximum_bytes=224)["allowedCurrencies"]), 1)

    def test_each_mapping_getter_preserves_zero_and_full_uint256_precision(self):
        for getter in ("predecessorOf", "successorOf", "activeTokenForBill"):
            zero = decode_remint_link(word(0), getter)
            self.assertEqual(zero["tokenId"], "0")
            self.assertEqual(zero["observation"], "ZERO_AT_READ")
            self.assertFalse(zero["replayAllowed"])
            result = decode_remint_link("0x"+word(2**256-1).hex(), getter)
            self.assertEqual(result["tokenId"], str(2**256-1))
            self.assertEqual(result["observation"], "NONZERO_AT_READ")
        for raw in (b"", word(1)+word(2), word(1)[:-1]):
            with self.assertRaises(RemintReadResultRefused):
                decode_remint_link(raw, "successorOf")
        with self.assertRaises(RemintReadResultRefused):
            decode_remint_link(word(1), "ownerOf")

    def test_results_are_detached_and_no_read_establishes_execution_authority(self):
        raw = declaration()
        before = deepcopy(raw)
        first = decode_remint_declaration(raw)
        first["allowedCurrencies"].clear()
        second = decode_remint_declaration(raw)
        self.assertEqual(len(second["allowedCurrencies"]), 2)
        self.assertEqual(raw, before)
        self.assertEqual(set(second),
                         {"billKey", "termsHash", "currencyDeclarationHash", "allowedCurrencies"})
        self.assertNotIn("businessAcceptance", second)
