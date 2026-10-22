"""Package integrity and bootstrap boundaries; not installed-provider acceptance."""
import contextlib
import hashlib
import io
import json
import os
import unittest
import zipfile
from unittest.mock import patch
from exchange import demo_package as kit, demo_ui

SOURCE = {"exchange/__init__.py": b"", "exchange/demo_ui.py": b"# synthetic runtime fixture\n",
          "exchange/demo_package.py": b"# synthetic builder fixture\n",
          "scenarios/__init__.py": b"", "scenarios/demos.py": b"# fixture\n"}

class DemoPackage(unittest.TestCase):
    def build(self):
        return kit.build(kit.pack(SOURCE), "a" * 40, kit.git_tree(SOURCE))

    def test_repeat_build_preserves_exact_source_tree_and_hash_inventory(self):
        data = self.build()
        self.assertEqual(data, self.build())
        manifest = kit.verify(data, hashlib.sha256(data).hexdigest())
        self.assertEqual(manifest["tree"], kit.git_tree(SOURCE))
        self.assertEqual(manifest["realAcceptance"], "NOT_RUN")
        self.assertEqual(set(manifest["files"]), set(SOURCE))
        self.assertEqual(kit.read_archive(data)["__main__.py"], kit.BOOTSTRAP)

    def test_untrusted_outer_digest_refuses_before_archive_parser(self):
        data = self.build()
        for digest in (None, "", "0" * 64):
            with self.subTest(digest=digest), patch.object(kit, "read_archive") as parser:
                with self.assertRaises(ValueError):
                    kit.verify(data, digest)
                parser.assert_not_called()

    def test_rehashed_content_or_manifest_tampering_is_still_refused(self):
        data = self.build()
        for mode in ("source", "manifest", "bootstrap", "extra"):
            with self.subTest(mode=mode):
                members = kit.read_archive(data)
                if mode == "source":
                    members["exchange/demo_ui.py"] += b"changed"
                elif mode == "manifest":
                    manifest = json.loads(members[kit.MANIFEST])
                    manifest["realAcceptance"] = "PASS"
                    members[kit.MANIFEST] = kit.canonical(manifest)
                elif mode == "bootstrap":
                    members["__main__.py"] += b"changed"
                else:
                    members["unexpected.py"] = b""
                changed = kit.pack(members)
                with self.assertRaises(ValueError):
                    kit.verify(changed, hashlib.sha256(changed).hexdigest())

    def test_source_identity_and_reserved_or_missing_runtime_refused(self):
        for source, commit, tree in ((SOURCE, "short", kit.git_tree(SOURCE)),
                (SOURCE, "a" * 40, "b" * 40),
                (dict(SOURCE, **{"__main__.py": b""}), "a" * 40, "b" * 40),
                ({"only.txt": b""}, "a" * 40, kit.git_tree({"only.txt": b""}))):
            with self.assertRaises(ValueError):
                kit.build(kit.pack(source), commit, tree)

    def test_unsafe_duplicate_link_and_expansion_limit_refused(self):
        for path in ("../escape.py", "/absolute.py", "a\\b.py", "a/./b.py", "drive:bad.py"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                kit.read_archive(kit.pack({path: b""}))
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            member = zipfile.ZipInfo("link.py")
            member.create_system = 3
            member.external_attr = 0o120777 << 16
            archive.writestr(member, b"elsewhere")
        with self.assertRaises(ValueError):
            kit.read_archive(output.getvalue())
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w") as archive:
                archive.writestr("same", b"one")
                archive.writestr("same", b"two")
        with self.assertRaises(ValueError):
            kit.read_archive(output.getvalue())
        with patch.object(kit, "MAX_CONTENT", 2), self.assertRaises(ValueError):
            kit.read_archive(kit.pack({"large": b"three"}))

    def test_bootstrap_requires_external_digest_and_verify_does_not_start_server(self):
        data = self.build()
        for digest in ("", "0" * 64):
            with patch.dict(os.environ, {"EX_DEMO_SHA256": digest}), \
                    patch("sys.argv", ["approved-demo.pyz", "--verify"]), \
                    patch("builtins.open", return_value=io.BytesIO(data)):
                with self.assertRaises(SystemExit) as stopped:
                    exec(kit.BOOTSTRAP, {"__name__": "__main__"})
                self.assertNotEqual(stopped.exception.code, 0)
        with patch.dict(os.environ, {"EX_DEMO_SHA256": hashlib.sha256(data).hexdigest()}), \
                patch("sys.argv", ["approved-demo.pyz", "--verify"]), \
                patch("builtins.open", return_value=io.BytesIO(data)), \
                contextlib.redirect_stdout(io.StringIO()) as output, \
                patch.object(demo_ui, "main") as launch:
            with self.assertRaises(SystemExit) as stopped:
                exec(kit.BOOTSTRAP, {"__name__": "__main__"})
            self.assertEqual(stopped.exception.code, 0)
            self.assertEqual(json.loads(output.getvalue())["tree"], kit.git_tree(SOURCE))
            launch.assert_not_called()

    def test_launch_identity_cannot_be_overridden_and_stream_cli_roundtrips(self):
        data = self.build()
        sha = hashlib.sha256(data).hexdigest()
        with patch.object(demo_ui, "main", return_value=0) as launch:
            self.assertEqual(kit.run_archive(data, sha, ["--port", "0"]), 0)
            launch.assert_called_once_with(["--port", "0", "--commit", "a" * 40,
                                          "--tree", kit.git_tree(SOURCE)])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            kit.run_archive(data, sha, ["--commit", "b" * 40])
        output = io.BytesIO()
        self.assertEqual(kit.main(["build", "--commit", "a" * 40, "--tree", kit.git_tree(SOURCE)],
                                  io.BytesIO(kit.pack(SOURCE)), output), 0)
        self.assertEqual(output.getvalue(), data)
        with contextlib.redirect_stderr(io.StringIO()):
            rejected = io.BytesIO()
            self.assertEqual(kit.main(["verify", "--sha256", "0" * 64], io.BytesIO(data), rejected), 1)
            self.assertEqual(rejected.getvalue(), b"")

    def test_source_growth_beyond_512_files_roundtrips_complete_kit(self):
        source = dict(SOURCE)
        source.update({"fixtures/member-%04d.txt" % n: b"" for n in range(508)})
        self.assertEqual(len(source), 513)
        data = kit.build(kit.pack(source), "a" * 40, kit.git_tree(source))
        manifest = kit.verify(data, hashlib.sha256(data).hexdigest())
        self.assertEqual(set(manifest["files"]), set(source))
        self.assertEqual(len(kit.read_archive(data)), 515)

    def test_output_reserves_members_for_manifest_and_bootstrap(self):
        source = dict(SOURCE, **{"extra.txt": b""})
        with patch.object(kit, "MAX_MEMBERS", 8):
            data = kit.build(kit.pack(source), "a" * 40, kit.git_tree(source))
            self.assertEqual(len(kit.read_archive(data)), 8)
            source["over.txt"] = b""
            with self.assertRaisesRegex(ValueError, "too many archive members"):
                kit.build(kit.pack(source), "a" * 40, kit.git_tree(source))

    def test_member_and_generated_content_limits_remain_enforced(self):
        with self.assertRaisesRegex(ValueError, "too many archive members"):
            kit.read_archive(kit.pack({"member-%04d" % n: b""
                                       for n in range(kit.MAX_MEMBERS + 1)}))
        source_bytes = sum(map(len, SOURCE.values()))
        with patch.object(kit, "MAX_CONTENT", source_bytes):
            with self.assertRaisesRegex(ValueError, "archive content limit"):
                self.build()
