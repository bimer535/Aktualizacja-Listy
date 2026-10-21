#!/usr/bin/env python3
"""Public update check and explicit native package installation."""
import argparse
import json
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

import update_core as updates
from version import APP_VERSION, PACKAGE_NAME


def emit(stage, **fields):
    print(json.dumps({"stage": stage, **fields}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check", "install"))
    parser.add_argument("--expected-version")
    args = parser.parse_args()
    def interrupt(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    try:
        emit("checking", current_version=APP_VERSION)
        manifest = updates.latest_manifest()
        if updates.version_tuple(manifest["version"]) <= updates.version_tuple(APP_VERSION):
            emit("up_to_date", version=APP_VERSION)
            return 0
        if args.mode == "check":
            emit("update_available", version=manifest["version"], notes=manifest["notes"])
            return 0
        if args.expected_version != manifest["version"]:
            raise updates.UpdateError("update_changed_check_again")
        opkg = shutil.which("opkg")
        if not opkg:
            raise updates.UpdateError("opkg_not_found")
        emit("downloading", version=manifest["version"])
        body = updates.download(manifest["url"], manifest["size"])
        updates.validate_package(body, manifest)
        with tempfile.TemporaryDirectory(prefix="mk-canal-update-") as tmp:
            path = Path(tmp) / "mk-canal-update.ipk"
            path.write_bytes(body)
            path.chmod(0o600)
            # Once opkg starts, let it complete. The UI disables cancel here.
            emit("installing", version=manifest["version"])
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            with tempfile.TemporaryFile() as log:
                result = subprocess.run([opkg, "install", str(path)], stdin=subprocess.DEVNULL,
                                        stdout=log, stderr=subprocess.STDOUT, check=False)
            if result.returncode != 0:
                raise updates.UpdateError("opkg_install_failed")
            status = subprocess.run([opkg, "status", PACKAGE_NAME], stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
            fields = {}
            for line in status.stdout.decode("utf-8", "replace").splitlines():
                if ":" in line and not line.startswith(" "):
                    key, value = line.split(":", 1)
                    fields[key] = value.strip()
            if (status.returncode != 0 or fields.get("Package") != PACKAGE_NAME
                    or fields.get("Version") != manifest["version"]
                    or fields.get("Status") != "install ok installed"):
                raise updates.UpdateError("installed_version_not_confirmed")
        emit("installed", version=manifest["version"])
        return 0
    except KeyboardInterrupt:
        emit("cancelled")
        return 130
    except updates.UpdateError as error:
        emit("error", reason=error.reason)
        return 1
    except Exception as error:
        emit("error", reason=type(error).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
