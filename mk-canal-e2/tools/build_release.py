#!/usr/bin/env python3
"""Build a self-contained IPK and update manifest; never include account files."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://raw.githubusercontent.com/bimer535/Aktualizacja-Listy/main/mk-canal-e2/"
PREFIX = "usr/lib/enigma2/python/Plugins/Extensions/CanalE2Test/"
PACKAGE = "enigma2-plugin-extensions-canale2test"


def tar_gz(files, mtime=0):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
        for name, body in files:
            entry = tarfile.TarInfo(name)
            entry.mode = 0o644
            entry.uid = entry.gid = 0
            entry.mtime = mtime
            entry.size = len(body)
            tar.addfile(entry, io.BytesIO(body))
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--notes", required=True)
    parser.add_argument("--source", type=Path, default=ROOT / "src" / "CanalE2Test")
    parser.add_argument("--output", type=Path, default=ROOT)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}", args.version):
        parser.error("Version must use X.Y.Z")
    if not 1 <= len(args.notes) <= 1600:
        parser.error("Release notes must contain 1-1600 characters")
    version_path = args.source / "version.py"
    source = version_path.read_text()
    source, count = re.subn(r'^APP_VERSION = "[0-9.]+"$', 'APP_VERSION = "' + args.version + '"', source, flags=re.M)
    if count != 1:
        raise SystemExit("Could not locate APP_VERSION")
    version_path.write_text(source)
    files = []
    for path in sorted(args.source.iterdir()):
        if not path.is_file() or path.suffix not in (".py", ".png", ".svg", ".txt") and path.name != "LICENSE":
            continue
        body = path.read_bytes()
        if path.suffix == ".py":
            ast.parse(body, filename=str(path))
        files.append(("./" + PREFIX + path.name, body))
    names = {name.rsplit("/", 1)[-1] for name, body in files}
    if not {"plugin.py", "version.py", "update_worker.py", "account_worker.py", "icon.png", "logo.png", "LICENSE"} <= names:
        raise SystemExit("Incomplete plugin source")
    control = ("Package: " + PACKAGE + "\nVersion: " + args.version + "\n"
               "Description: MK Canal+ E2 - live TV, device-code login and online updates\n"
               "Architecture: all\nMaintainer: MK\nSection: extra\nPriority: optional\n"
               "License: GPL-2.0\nDepends: enigma2, python3-core, python3-pycryptodome\n").encode()
    result = bytearray(b"!<arch>\n")
    for name, body in (("debian-binary", b"2.0\n"),
                       ("control.tar.gz", tar_gz([("./control", control)])),
                       # Real source timestamps invalidate timestamp-based .pyc
                       # files when an update changes text without changing size.
                       ("data.tar.gz", tar_gz(files, mtime=int(time.time())))):
        header = ((name + "/").ljust(16) + "0".ljust(12) + "0".ljust(6) + "0".ljust(6)
                  + "100644".ljust(8) + str(len(body)).ljust(10) + "`\n")
        result.extend(header.encode("ascii"))
        result.extend(body)
        if len(body) % 2:
            result.extend(b"\n")
    packages = args.output / "packages"
    packages.mkdir(parents=True, exist_ok=True)
    package_path = packages / ("MK_Canal_E2_" + args.version + ".ipk")
    package_path.write_bytes(result)
    manifest = {"schema": 1, "name": "MK Canal+ E2", "package": PACKAGE,
                "version": args.version, "url": BASE_URL + "packages/" + package_path.name,
                "sha256": hashlib.sha256(result).hexdigest(), "size": len(result), "notes": args.notes}
    (args.output / "update.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"ipk": str(package_path.resolve()), "sha256": manifest["sha256"],
                      "size": len(result), "files": len(files)}, indent=2))


if __name__ == "__main__":
    main()
