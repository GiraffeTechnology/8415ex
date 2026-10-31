"""Synthetic actual client transport contracts; not live custody acceptance."""
import unittest
from exchange.wallet_api_client import WalletAPIRefused
from integration.test_wallet_api_client import original_protocol, ACTOR

class NativeWalletLoginConsumer(unittest.TestCase):
    def test_complete_original_challenge_reaches_native_port_and_real_client_session_path(self):
        with original_protocol() as (client, state):
            seen = []
            def sign(challenge):
                self.assertEqual(set(challenge), {"origin", "tenant", "account", "chainId",
                    "nonce", "issuedAt", "expiresAt", "id", "method", "message"})
                self.assertEqual((challenge["origin"], challenge["tenant"], challenge["account"],
                                  challenge["chainId"], challenge["method"]),
                                 (state["origin"], "synthetic", ACTOR, "11155111", "wallet"))
                self.assertIn("urn:8415wallet:purpose:login", challenge["message"])
                self.assertIn("urn:8415wallet:request:" + challenge["id"], challenge["message"])
                seen.append(challenge)
                return {"signature": "0x" + "1" * 130}
            result = client.login_native(sign)
            self.assertEqual(result, {"authenticated": True, "chainId": "11155111"})
            self.assertEqual(len(seen), 1)
            self.assertEqual([path for _, path, _ in state["calls"]],
                             ["/auth/bootstrap", "/auth/challenge", "/auth/proof", "/auth/session"])
            self.assertNotIn("csrf", result)
            self.assertNotIn("signature", result)

    def test_wrong_scope_or_message_is_refused_before_native_custody_port(self):
        for mode in ("wrong-message", "wrong-account", "wrong-chain", "wrong-tenant", "expired"):
            with self.subTest(mode=mode), original_protocol() as (client, state):
                state["mode"] = mode
                with self.assertRaises(WalletAPIRefused):
                    client.login_native(lambda challenge: self.fail("unbound login reached native signer"))
                self.assertNotIn("proof", state)

    def test_native_cancel_clears_private_auth_state_without_proof_or_retry(self):
        for code in ("NATIVE_LOGIN_CANCELLED", "LOGIN_CANCELLED"):
            with self.subTest(code=code), original_protocol() as (client, state):
                calls = []
                def cancel(challenge):
                    calls.append(challenge["id"])
                    raise RuntimeError(code)
                with self.assertRaisesRegex(WalletAPIRefused, "^EX_WALLET_LOGIN_CANCELLED$"):
                    client.login_native(cancel)
                self.assertEqual(len(calls), 1)
                self.assertNotIn("proof", state)
                self.assertIsNone(client._csrf)
                self.assertIsNone(client._session)
                self.assertEqual(list(client._jar), [])
                self.assertFalse(any("/tasks/" in path for _, path, _ in state["calls"]))

    def test_malformed_native_result_or_extra_private_fields_never_reach_proof(self):
        for proof in (None, "0x" + "1" * 130, {}, {"signature": "bad"},
                      {"signature": "0x" + "1" * 130, "privateKey": "synthetic-not-a-key"}):
            with self.subTest(proof=proof), original_protocol() as (client, state):
                with self.assertRaises(WalletAPIRefused):
                    client.login_native(lambda challenge: proof)
                self.assertNotIn("proof", state)
                self.assertEqual(list(client._jar), [])

    def test_expiration_during_native_signing_prevents_proof(self):
        with original_protocol() as (client, state):
            def delayed(challenge):
                state["now"] += 120000
                return {"signature": "0x" + "1" * 130}
            with self.assertRaises(WalletAPIRefused):
                client.login_native(delayed)
            self.assertNotIn("proof", state)

    def test_native_failure_is_sanitized_without_auto_retry(self):
        with original_protocol() as (client, state):
            called = []
            def unavailable(challenge):
                called.append(challenge["id"])
                raise RuntimeError("private custody location must not leave signer")
            with self.assertRaisesRegex(WalletAPIRefused, "^EX_WALLET_NATIVE_LOGIN_REFUSED$"):
                client.login_native(unavailable)
            self.assertEqual(len(called), 1)
            self.assertNotIn("proof", state)

    def test_missing_native_signer_refused_before_transport(self):
        with original_protocol() as (client, state):
            with self.assertRaisesRegex(WalletAPIRefused, "^EX_WALLET_MESSAGE_SIGNER_REQUIRED$"):
                client.login_native(None)
            self.assertEqual(state["calls"], [])

    def test_unrecognized_challenge_fields_stop_before_native_signer(self):
        with original_protocol() as (client, state):
            original_request = client._request
            def request(path, body=None):
                value = original_request(path, body)
                if path == "challenge":
                    value["unrecognized"] = "must-not-reach-native-signer"
                return value
            client._request = request
            with self.assertRaisesRegex(WalletAPIRefused, "^EX_WALLET_CHALLENGE_REFUSED$"):
                client.login_native(lambda challenge: self.fail("unrecognized challenge reached custody"))
            self.assertNotIn("proof", state)
