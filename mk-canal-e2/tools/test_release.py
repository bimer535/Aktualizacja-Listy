#!/usr/bin/env python3
"""Offline update validation and installation-flow tests; never run real opkg."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import py_compile
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/CanalE2Test"))
import update_core as core
import update_worker as worker


class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "update.json").read_text())
        cls.package = (ROOT / "packages" / cls.manifest["url"].rsplit("/", 1)[-1]).read_bytes()

    def test_published_package_identity_and_checksum(self):
        manifest = core.validate_manifest(json.dumps(self.manifest).encode())
        self.assertTrue(core.validate_package(self.package, manifest))

    def test_corrupt_package_rejected_before_install(self):
        changed = self.package[:-1] + bytes((self.package[-1] ^ 1,))
        with self.assertRaisesRegex(core.UpdateError, "update_checksum_mismatch"):
            core.validate_package(changed, self.manifest)

    def test_upgrade_reloads_same_size_version_source_with_old_bytecode(self):
        archive = core.ar_members(self.package)
        with tarfile.open(fileobj=io.BytesIO(archive["data.tar.gz"]), mode="r:gz") as tar:
            member = next(m for m in tar if m.name.endswith("/version.py"))
            source = tar.extractfile(member).read()
            timestamp = member.mtime
        current = self.manifest["version"]
        older = "0.0.0"
        self.assertEqual(len(current), len(older))
        old_source = source.replace(('APP_VERSION = "' + current + '"').encode(),
                                    ('APP_VERSION = "' + older + '"').encode())
        self.assertEqual(len(source), len(old_source))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "version.py"
            path.write_bytes(old_source)
            os.utime(path, (0, 0))
            py_compile.compile(str(path), doraise=True)
            path.write_bytes(source)
            os.utime(path, (timestamp, timestamp))
            script = "import sys; sys.path.insert(0, sys.argv[1]); import version; print(version.APP_VERSION)"
            result = subprocess.run([sys.executable, "-I", "-c", script, directory],
                                    check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout.strip(), current)

    def test_other_package_version_and_untrusted_hosts_rejected(self):
        wrong = copy.deepcopy(self.manifest)
        wrong["version"] = "99.0.0"
        with self.assertRaisesRegex(core.UpdateError, "ipk_identity_or_version_mismatch"):
            core.validate_package(self.package, wrong)
        for value in ("http://raw.githubusercontent.com" + core.REPOSITORY_PATH + "file.ipk",
                      "https://evil.example/file.ipk",
                      "https://raw.githubusercontent.com/other/project/main/file.ipk",
                      "https://raw.githubusercontent.com" + core.REPOSITORY_PATH + "../secret.ipk",
                      "https://user:pass@raw.githubusercontent.com" + core.REPOSITORY_PATH + "file.ipk"):
            with self.subTest(value=value), self.assertRaises(core.UpdateError):
                core.allowed_url(value)

    def test_package_cannot_write_account_files(self):
        archive = core.ar_members(self.package)
        output = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(archive["data.tar.gz"]), mode="r:gz") as original:
            with tarfile.open(fileobj=output, mode="w:gz") as new:
                for member in original:
                    new.addfile(member, original.extractfile(member) if member.isfile() else None)
                member = tarfile.TarInfo("./etc/canal-e2/session.json")
                body = b'{}'; member.size = len(body)
                new.addfile(member, io.BytesIO(body))
        archive["data.tar.gz"] = output.getvalue()
        body = bytearray(b"!<arch>\n")
        for name, data in archive.items():
            header = (name + "/").ljust(16) + "0".ljust(12) + "0".ljust(6) + "0".ljust(6)
            header += "100644".ljust(8) + str(len(data)).ljust(10) + "`\n"
            body.extend(header.encode()); body.extend(data)
            if len(data) % 2: body.extend(b"\n")
        manifest = dict(self.manifest, size=len(body), sha256=hashlib.sha256(body).hexdigest())
        with self.assertRaisesRegex(core.UpdateError, "ipk_writes_outside_plugin"):
            core.validate_package(bytes(body), manifest)

    def run_flow(self, mode, *, installed_version=None, install_code=0, expected=None):
        calls, paths = [], []
        def fake_run(arguments, **kwargs):
            calls.append(arguments)
            if arguments[1] == "install":
                path = Path(arguments[2]); paths.append(path)
                self.assertEqual(path.read_bytes(), self.package)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                return SimpleNamespace(returncode=install_code)
            self.assertEqual(arguments[1:], ["status", core.PACKAGE_NAME])
            text = "Package: %s\nVersion: %s\nStatus: install ok installed\n" % (
                core.PACKAGE_NAME, installed_version or self.manifest["version"])
            return SimpleNamespace(returncode=0, stdout=text.encode())
        command = ["update_worker.py", mode]
        if expected: command += ["--expected-version", expected]
        output = io.StringIO()
        saved = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
        try:
            with patch.object(sys, "argv", command), patch.object(worker, "APP_VERSION", "0.0.1"), \
                 patch.object(core, "latest_manifest", return_value=self.manifest), \
                 patch.object(core, "download", return_value=self.package), \
                 patch.object(worker.shutil, "which", return_value="/test/opkg"), \
                 patch.object(worker.subprocess, "run", side_effect=fake_run), \
                 contextlib.redirect_stdout(output):
                result = worker.main()
        finally:
            for signum, handler in saved.items(): signal.signal(signum, handler)
        self.assertTrue(all(not p.exists() for p in paths))
        return result, [json.loads(line) for line in output.getvalue().splitlines()], calls

    def test_check_never_installs(self):
        result, events, calls = self.run_flow("check")
        self.assertEqual(result, 0)
        self.assertEqual(events[-1]["stage"], "update_available")
        self.assertEqual(calls, [])

    def test_explicit_install_checks_native_status(self):
        result, events, calls = self.run_flow("install", expected=self.manifest["version"])
        self.assertEqual(result, 0)
        self.assertEqual(events[-1]["stage"], "installed")
        self.assertEqual([call[1] for call in calls], ["install", "status"])

    def test_failed_install_and_unconfirmed_version_never_report_success(self):
        for kwargs, reason in (({"install_code": 1}, "opkg_install_failed"),
                               ({"installed_version": "0.0.1"}, "installed_version_not_confirmed")):
            with self.subTest(reason=reason):
                result, events, _ = self.run_flow("install", expected=self.manifest["version"], **kwargs)
                self.assertEqual(result, 1)
                self.assertEqual(events[-1], {"stage": "error", "reason": reason})

    def test_changed_release_requires_new_check(self):
        result, events, calls = self.run_flow("install", expected="0.0.2")
        self.assertEqual(result, 1)
        self.assertEqual(events[-1]["reason"], "update_changed_check_again")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
