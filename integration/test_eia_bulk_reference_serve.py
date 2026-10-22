"""Synthetic fixed-source host contracts; no source requests or real serving."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import io

from exchange import eia_bulk_reference_serve as bulk_host
from exchange.eia_reference_serve import load_eia_reference_config, CONFIG_LIMIT
from exchange.eia_wti_bulk_series import BULK_URL
from exchange.eia_wti_spot_table import SOURCE_URL, SCOPE


class EIABulkHostContracts(unittest.TestCase):
    def setUp(self):
        self.config = {"version": 1, "policy": dict(SCOPE,
            sourceURL=BULK_URL, sourceTimezone="unknown", pollSeconds=3600,
            maxSourceAgeSeconds=864000, maxClockSkewSeconds=0),
            "reader": dict(timeout_seconds=20, user_agent="Synthetic bulk host",
                minimum_fetch_seconds=3600, failure_backoff_seconds=7200)}

    def raw(self, config=None):
        return json.dumps(self.config if config is None else config).encode()

    def arguments(self, path, digest):
        return ["--empty-catalogue", "--reference-config", str(path),
                "--reference-config-sha256", digest, "--port", "0",
                "--commit", "a"*40, "--tree", "b"*40,
                "--collateral-selection", "--scenario-selection"]

    def test_exact_original_fields_and_explicit_unknown_calendar_are_preserved(self):
        raw = self.raw()
        result = bulk_host.load_eia_bulk_reference_config(raw)
        self.assertEqual(result, self.config)
        result["reader"]["minimum_fetch_seconds"] = 1
        self.assertEqual(bulk_host.load_eia_bulk_reference_config(raw), self.config)

    def test_bulk_and_original_html_loaders_cannot_silently_select_each_other(self):
        html = deepcopy(self.config)
        html["policy"]["sourceURL"] = SOURCE_URL
        self.assertEqual(load_eia_reference_config(self.raw(html)), html)
        with self.assertRaises(ValueError):
            load_eia_reference_config(self.raw())
        for url in (SOURCE_URL, BULK_URL+"?fallback=1", "https://example.invalid"):
            changed = deepcopy(self.config)
            changed["policy"]["sourceURL"] = url
            with self.assertRaises(ValueError):
                bulk_host.load_eia_bulk_reference_config(self.raw(changed))

    def test_duplicate_unknown_and_executable_configuration_fields_are_refused(self):
        raw = self.raw()
        duplicated = raw[:-1] + b', "version": 1}'
        with self.assertRaises(ValueError):
            bulk_host.load_eia_bulk_reference_config(duplicated)
        for key in ("callback", "authorization", "fallback"):
            changed = deepcopy(self.config)
            changed["reader"][key] = "browser-value"
            with self.assertRaises(ValueError):
                bulk_host.load_eia_bulk_reference_config(self.raw(changed))

    def test_bounds_cadence_calendar_and_nonfinite_values_fail_before_composition(self):
        for raw in (b"", b" "*(CONFIG_LIMIT+1), b"[]", b"null"):
            with self.assertRaises(ValueError):
                bulk_host.load_eia_bulk_reference_config(raw)
        for section, key, value in (
                ("policy", "pollSeconds", 3599), ("policy", "sourceTimezone", ""),
                ("reader", "minimum_fetch_seconds", True),
                ("reader", "minimum_fetch_seconds", float("nan")),
                ("policy", "maxSourceAgeSeconds", -1)):
            changed = deepcopy(self.config)
            changed[section][key] = value
            with self.assertRaises(ValueError):
                bulk_host.load_eia_bulk_reference_config(self.raw(changed))

    def test_changed_config_bytes_with_old_external_digest_never_bind(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"source.json"
            raw = self.raw()
            path.write_bytes(raw+b"\n")
            with patch.object(bulk_host, "compose_eia_bulk_reference_catalogue") as compose, \
                 contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                bulk_host.main(self.arguments(path, hashlib.sha256(raw).hexdigest()))
            compose.assert_not_called()

    def test_malformed_external_digest_never_opens_configuration_or_binds(self):
        for digest in ("missing", "A"*64, "a"*63):
            with patch("builtins.open") as opened, \
                 patch.object(bulk_host, "compose_eia_bulk_reference_catalogue") as compose, \
                 contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                bulk_host.main(self.arguments("unread-config", digest))
            opened.assert_not_called()
            compose.assert_not_called()

    def test_explicit_cli_forwards_original_inputs_to_only_bulk_composition(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"source.json"
            raw = self.raw()
            path.write_bytes(raw)
            sentinel = object()
            with patch.object(bulk_host, "compose_eia_bulk_reference_catalogue",
                              return_value=sentinel) as compose, \
                 patch.object(bulk_host, "serve_reference_catalogue") as serve:
                self.assertEqual(bulk_host.main(self.arguments(path, hashlib.sha256(raw).hexdigest())), 0)
            kwargs = compose.call_args.kwargs
            self.assertEqual(kwargs["policy"], self.config["policy"])
            self.assertTrue(kwargs["verify_policy"](self.config["policy"]))
            self.assertFalse(kwargs["verify_policy"](dict(self.config["policy"], sourceURL=SOURCE_URL)))
            self.assertEqual(kwargs["reader_options"], self.config["reader"])
            self.assertEqual(kwargs["port"], 0)
            self.assertEqual(kwargs["commit"], "a"*40)
            self.assertEqual(kwargs["tree"], "b"*40)
            self.assertTrue(kwargs["collateral_selection"])
            self.assertTrue(kwargs["scenario_selection"])
            serve.assert_called_once_with(sentinel)

    def test_missing_explicit_host_arguments_do_not_create_a_default_service(self):
        for arguments in ([], ["--empty-catalogue"], ["--reference-config", "file"]):
            with patch.object(bulk_host, "compose_eia_bulk_reference_catalogue") as compose, \
                 contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                bulk_host.main(arguments)
            compose.assert_not_called()
