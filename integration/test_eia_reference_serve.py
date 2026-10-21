"""Synthetic CLI/config definitions; execution belongs to CI/review."""
import hashlib
import json
from unittest.mock import mock_open, patch
import unittest

from exchange.eia_reference_serve import load_eia_reference_config, main
from exchange.eia_wti_spot_table import SCOPE, SOURCE_URL


class EIAReferenceServeTests(unittest.TestCase):
    def config(self):
        return {
            "version": 1,
            # UTC is test data only, not a production source-calendar choice.
            "policy": dict(SCOPE, sourceURL=SOURCE_URL, sourceTimezone="UTC",
                           pollSeconds=60, maxSourceAgeSeconds=86400,
                           maxClockSkewSeconds=0),
            "reader": dict(timeout_seconds=20, user_agent="Synthetic host config",
                           minimum_fetch_seconds=60, failure_backoff_seconds=120),
        }

    def raw(self, config):
        return json.dumps(config).encode()

    def args(self, raw=None):
        raw = self.raw(self.config()) if raw is None else raw
        return ["--empty-catalogue", "--reference-config", "synthetic.json",
                "--reference-config-sha256", hashlib.sha256(raw).hexdigest(),
                "--port", "0", "--commit", "a" * 40, "--tree", "b" * 40,
                "--collateral-selection", "--scenario-selection"]

    def test_config_retains_explicit_values_and_independent_copy(self):
        config = self.config()
        parsed = load_eia_reference_config(self.raw(config))
        self.assertEqual(parsed, config)
        parsed["policy"]["currency"] = "EUR"
        self.assertEqual(config["policy"]["currency"], "USD")

    def test_missing_calendar_cadence_and_reader_settings_are_not_defaulted(self):
        for group, key in (("policy", "sourceTimezone"), ("policy", "pollSeconds"),
                           ("reader", "timeout_seconds"), ("reader", "user_agent")):
            config = self.config()
            del config[group][key]
            with self.assertRaises(ValueError):
                load_eia_reference_config(self.raw(config))

    def test_credentials_and_transport_callbacks_are_not_configuration_fields(self):
        for key in ("api_key", "authorization", "open_response"):
            config = self.config()
            config["reader"][key] = "synthetic"
            with self.assertRaises(ValueError):
                load_eia_reference_config(self.raw(config))

    def test_changed_scope_version_and_noninteger_cadence(self):
        for group, key, value in (("policy", "currency", "EUR"),
                                   ("policy", "pollSeconds", True)):
            config = self.config()
            config[group][key] = value
            with self.assertRaises(ValueError):
                load_eia_reference_config(self.raw(config))
        for version in (True, 0, 2, "1"):
            config = self.config()
            config["version"] = version
            with self.assertRaises(ValueError):
                load_eia_reference_config(self.raw(config))

    def test_duplicate_fields_multiple_documents_and_size_bound(self):
        raw = self.raw(self.config())
        for bad in (raw[:-1] + b',"version":1}', raw + raw,
                    b"x" * (64 * 1024 + 1), b"", "not bytes"):
            with self.assertRaises(ValueError):
                load_eia_reference_config(bad)

    def test_polling_never_runs_inside_reader_spacing(self):
        for poll, spacing in ((30, 60), (60, 60.5), (60, True), (60, "60"),
                              (60, 0), (60, -1)):
            config = self.config()
            config["policy"]["pollSeconds"] = poll
            config["reader"]["minimum_fetch_seconds"] = spacing
            with self.subTest(poll=poll, spacing=spacing):
                with self.assertRaises(ValueError):
                    load_eia_reference_config(self.raw(config))
        for poll, spacing in ((60, 60), (120, 60), (60, 59.5)):
            config = self.config()
            config["policy"]["pollSeconds"] = poll
            config["reader"]["minimum_fetch_seconds"] = spacing
            self.assertEqual(load_eia_reference_config(self.raw(config)), config)

    def test_nonfinite_configuration_is_refused_before_composition(self):
        raw = self.raw(self.config())
        for token in (b"NaN", b"Infinity", b"-Infinity"):
            malformed = raw.replace(b'"timeout_seconds": 20',
                                    b'"timeout_seconds": ' + token)
            with self.assertRaises(ValueError):
                load_eia_reference_config(malformed)
            with patch("builtins.open", mock_open(read_data=malformed)), \
                 patch("exchange.eia_reference_serve.compose_eia_reference_catalogue") as compose:
                with self.assertRaises(SystemExit):
                    main(self.args(malformed))
                compose.assert_not_called()

    def test_host_config_digest_is_external_exact_and_checked_before_binding(self):
        raw = self.raw(self.config())
        changed = raw.replace(b"Synthetic host config", b"Changed host config")
        with patch("builtins.open", mock_open(read_data=changed)), \
             patch("exchange.eia_reference_serve.compose_eia_reference_catalogue") as compose:
            with self.assertRaises(SystemExit):
                main(self.args(raw))
            compose.assert_not_called()
        for digest in ("not-a-digest", "A" * 64, "0" * 63):
            args = self.args(raw)
            args[args.index("--reference-config-sha256") + 1] = digest
            with patch("builtins.open") as opened:
                with self.assertRaises(SystemExit):
                    main(args)
                opened.assert_not_called()

    def test_main_uses_original_factory_and_lifecycle_with_explicit_flags(self):
        config = self.config()
        server = object()
        with patch("builtins.open", mock_open(read_data=self.raw(config))) as opened, \
             patch("exchange.eia_reference_serve.compose_eia_reference_catalogue",
                   return_value=server) as compose, \
             patch("exchange.eia_reference_serve.serve_reference_catalogue") as serve:
            self.assertEqual(main(self.args()), 0)
            opened.assert_called_once_with("synthetic.json", "rb")
            serve.assert_called_once_with(server)
            values = compose.call_args.kwargs
            self.assertEqual(values["port"], 0)
            self.assertEqual(values["commit"], "a" * 40)
            self.assertEqual(values["tree"], "b" * 40)
            self.assertTrue(values["collateral_selection"])
            self.assertTrue(values["scenario_selection"])
            self.assertEqual(values["reader_options"], config["reader"])
            self.assertTrue(values["verify_policy"](config["policy"]))
            self.assertFalse(values["verify_policy"](dict(config["policy"], currency="EUR")))

    def test_invalid_file_never_composes_or_serves(self):
        with patch("builtins.open", mock_open(read_data=b"invalid")), \
             patch("exchange.eia_reference_serve.compose_eia_reference_catalogue") as compose, \
             patch("exchange.eia_reference_serve.serve_reference_catalogue") as serve:
            with self.assertRaises(SystemExit) as raised:
                main(self.args())
            self.assertEqual(raised.exception.code, 2)
            compose.assert_not_called()
            serve.assert_not_called()

    def test_explicit_empty_mode_and_all_server_identities_required(self):
        for flag in ("--empty-catalogue", "--reference-config-sha256", "--port", "--commit", "--tree"):
            args = self.args()
            index = args.index(flag)
            del args[index:index + (1 if flag == "--empty-catalogue" else 2)]
            with patch("builtins.open") as opened:
                with self.assertRaises(SystemExit):
                    main(args)
                opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
