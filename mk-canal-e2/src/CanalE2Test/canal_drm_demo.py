#!/usr/bin/env python3
"""Independent Widevine demo probe. Does not authenticate to CANAL+.

Downloads a pinned public tools_cenc source into a temporary directory,
checks each selected source hash, and tests its normal demo license flow.
No Enigma2/E2iPlayer imports; no license/device/key values are printed.
Upstream source: archivczsk/archivczsk-doplnky (GPL-2.0).
"""
import argparse
import contextlib
import hashlib
import importlib
import io
import json
import logging
import pathlib
import platform
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

COMMIT = "0adcaead1cc7b3688ee72627f6810a2453794fd7"
ARCHIVE = "https://codeload.github.com/archivczsk/archivczsk-doplnky/zip/" + COMMIT
LICENSE_URL = "https://cwip-shaka-proxy.appspot.com/no_auth"
# Public Bitmovin Art of Motion demo PSSH, documented by pywidevine.
PSSH = ("AAAAW3Bzc2gAAAAA7e+LqXnWSs6jyCfc1R0h7QAAADsIARIQ62dqu8s0Xpa"
        "7z2FmMPGj2hoNd2lkZXZpbmVfdGVzdCIQZmtqM2xqYVNkZmFsa3IzaioCSEQyAA==")

SOURCE_HASHES = {
  "LICENSE": "8177f97513213526df2cf6184d8ff986c675afb514d4e68a404010521b880643",
  "tools_cenc/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "tools_cenc/google/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "tools_cenc/google/protobuf/__init__.py": "4128e7f22d14e7a119b39cbaa8e91e16cdbe26227892b5a00b7ee87fc63ef7b9",
  "tools_cenc/google/protobuf/any_pb2.py": "77749a32d9a9e6b9301a9c8a50921478b4c8e44b9b7bc695477ace327755b889",
  "tools_cenc/google/protobuf/api_pb2.py": "d71bf7c5aaa4143458431efc9e29870684a2c334a24c222bcfdb29154798fe88",
  "tools_cenc/google/protobuf/compiler/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "tools_cenc/google/protobuf/compiler/plugin_pb2.py": "b897df67cd5c98efd0210f7e38be781801a4a94d2bf26c6e5f0bac0d400a90a0",
  "tools_cenc/google/protobuf/descriptor.py": "50bc0abbe5e739bd0f6c39a1bb31e993d065fe228742dd13b420cb416f17926a",
  "tools_cenc/google/protobuf/descriptor_database.py": "da105405bcd68d3772ab49cb67d1d829baa1329a2ecd9564f6caeeac44672d5a",
  "tools_cenc/google/protobuf/descriptor_pb2.py": "01e5b252f49d48e9c601072927d7f5eaf9f434f448b8dc6a72e7ddd7500ff3fb",
  "tools_cenc/google/protobuf/descriptor_pool.py": "820e3f4cd923ec8b522c6e8a9ef15014884129ba9a1e7d743839ba1e20fbc748",
  "tools_cenc/google/protobuf/duration_pb2.py": "f44053e0a3638f4c9a823899eb09531ca80f782f1ea6c6ce4a109b772384a991",
  "tools_cenc/google/protobuf/empty_pb2.py": "97e58547036179afa0445670a78e1513ce95930125c0cc6bd78d9e3649732f5f",
  "tools_cenc/google/protobuf/field_mask_pb2.py": "a9e59d0c0674099531a9d0cfd282b9807ffe1133dd385ab83a5f336c3daa0416",
  "tools_cenc/google/protobuf/internal/__init__.py": "ec537e3861afe4126e13ab917580f89363722cf911fc9eba071a67e22761f6fb",
  "tools_cenc/google/protobuf/internal/api_implementation.py": "f2e416a86b73ab45e766297d8403759afb2dfe70ec4ec659765441be0d47ab7e",
  "tools_cenc/google/protobuf/internal/containers.py": "19bf18e29262e33cc72ec2c91d5897218e71f9c328315b2d73bca5109a902584",
  "tools_cenc/google/protobuf/internal/decoder.py": "04931ad52f9bcf3fdc5ff8fec176ff6ac62888c4e5032f0ce3e4145b0363c2e5",
  "tools_cenc/google/protobuf/internal/encoder.py": "012cd616eb097077a6b55f157626e4d00d14d8fd0cac8acb0739e339a5abe8c1",
  "tools_cenc/google/protobuf/internal/enum_type_wrapper.py": "6e0a0d88620812f94e6a0e45741d3614205095f5892c7988ff38ffa244c1d936",
  "tools_cenc/google/protobuf/internal/extension_dict.py": "d2b05dfe8b6cece4b4355a9ccf0fce48dd52d760ec4104324abe6992b9e9b553",
  "tools_cenc/google/protobuf/internal/message_listener.py": "43073982489f02f5b3866ddbd2ffa75c9928ccd4e02fe2fdd9702c9678056a8c",
  "tools_cenc/google/protobuf/internal/python_message.py": "baba79fe5d7688ffa6df81f8575af9a2d57dc955589b450933b6487b0b6f02fe",
  "tools_cenc/google/protobuf/internal/type_checkers.py": "5e67a2a358c7e34dfa6e261fdb24e7df55078480582ec4cf9e5e8f9d5bbf6e46",
  "tools_cenc/google/protobuf/internal/well_known_types.py": "0bfb6d20cc9d883fd79e2aabaf551bc49b2a6a4337e9df215b417290a310192e",
  "tools_cenc/google/protobuf/internal/wire_format.py": "57660f2625c60d3380176bf9a0a72cb896faa349cd6fcd06fbd209097b20dd47",
  "tools_cenc/google/protobuf/json_format.py": "22c3a90c0b4ae00144d2e55823716e032ab75c608aa9ec48cea5fe94a13ecd6e",
  "tools_cenc/google/protobuf/message.py": "d221f125bf313331877cc6a9b376cf9584fc369aea24d7f8d546beeb9d274cb2",
  "tools_cenc/google/protobuf/message_factory.py": "6076b3e41aff966194846e73477ec2eeb3345270efc5d5f3c719875b95578276",
  "tools_cenc/google/protobuf/proto_builder.py": "8f7de232667668447138b58dcd80ddf07ca31ffaa3c070cc5472b9098c35d563",
  "tools_cenc/google/protobuf/pyext/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "tools_cenc/google/protobuf/pyext/cpp_message.py": "f2cdabd4c2aa771507a4a6fc5bf6903da3b0597bb5b01e368172e1f6041ee7b8",
  "tools_cenc/google/protobuf/reflection.py": "94064b1c8c04502f33b577d1287b7ce83579f60a3626f81a94783ed855c6e614",
  "tools_cenc/google/protobuf/service.py": "3065a0a314eb4a59aa5ac817be9d5768fe5283efe9abc4b0d9726e6359ba3153",
  "tools_cenc/google/protobuf/service_reflection.py": "1ab4315656cf8b4305abd4673851377dca991e25e8b0c11497276970ebdcda18",
  "tools_cenc/google/protobuf/source_context_pb2.py": "dccd07e47ba3a02b853f7f8c0f2a8aae8975f34a9edff02834e3ef540122e482",
  "tools_cenc/google/protobuf/struct_pb2.py": "1238852a812d2c0ce1704507310075a18eb10369b70b64a0bd385634f4188b90",
  "tools_cenc/google/protobuf/symbol_database.py": "59cd00ff3d4d3a4842032686c69a5712467766b9c5a5b514a400f13b0cfb75f9",
  "tools_cenc/google/protobuf/text_encoding.py": "58189f51779acf66fc0b91e9afe2a46bf99f1ef4126f7fd17ff4e0e923ab3779",
  "tools_cenc/google/protobuf/text_format.py": "f2dce8744ab79d8c7374d644c580e8ad8f2ca0208eb6f57e4b132904bfe9215f",
  "tools_cenc/google/protobuf/timestamp_pb2.py": "5bdc1b4973e06e79543477b20c43b3c6129d7f4d218cc063ec846f95ee16f866",
  "tools_cenc/google/protobuf/type_pb2.py": "6434ff66dedd6c915b23b9c469dddcebbe4049c15cbfc0f3d59181b0933d351c",
  "tools_cenc/google/protobuf/util/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "tools_cenc/google/protobuf/util/json_format_pb2.py": "eaa21a5888b8f9c3f739ae177c737bf4da6c4503ead9ddbba747daac4b82b200",
  "tools_cenc/google/protobuf/util/json_format_proto3_pb2.py": "b6810983114e08b084f8bf7f3e8ae18225485f0c3b72d08631a7678fa95c9886",
  "tools_cenc/google/protobuf/wrappers_pb2.py": "7334c9c7f1bca4a76e08763a2450ecd4a69b19fef7207b6b4076ef08aa183bf9",
  "tools_cenc/wvl3/cdm/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "tools_cenc/wvl3/cdm/cdm.py": "f8bf5ec69440778e00351d7c3ee6967d01065b8d4af6197f806ee32faf00df85",
  "tools_cenc/wvl3/cdm/compat.py": "79f07217ccc8bf046403c1b1598c3d5b170d234ceb31e5251fc967db82a8ef7c",
  "tools_cenc/wvl3/cdm/deviceconfig.py": "3322b3680bd5847f8f4d3330bd6dc0f0084031fd22ab532f1ef54ea7289943e9",
  "tools_cenc/wvl3/cdm/formats/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "tools_cenc/wvl3/cdm/formats/wv_proto4_pb2.py": "5f47857e0924dc74a2fda5f3bc4fd4793ebfdb2b0be1e6dbfa4e022eec96cd71",
  "tools_cenc/wvl3/cdm/key.py": "07779ad6c670de784925166c9e89e19ae967784043658598f1ddd7e40f697a96",
  "tools_cenc/wvl3/cdm/session.py": "90f8ab7c989595fb2ab37b62a7c777329de9f01ae6afcff76eb0a41fae9a098d",
  "tools_cenc/wvl3/cdm/vmp.py": "c2bd5369b64890ea00afbe8734fab057041399a9cd12ad5129b5f97fcbc601c8"
}


class ProbeError(Exception):
    pass


def prepare_engine(destination):
    req = urllib.request.Request(ARCHIVE, headers={"User-Agent": "IndependentDRMDemo/1.0"})
    with urllib.request.urlopen(req, timeout=25) as response:
        raw = response.read(50 * 1024 * 1024 + 1)
    if len(raw) > 50 * 1024 * 1024:
        raise ProbeError("source_archive_too_large")
    found = set()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for member in archive.infolist():
            parts = pathlib.PurePosixPath(member.filename).parts[1:]
            relative = "/".join(parts)
            if relative not in SOURCE_HASHES or member.is_dir():
                continue
            if relative in found or member.file_size > 2 * 1024 * 1024:
                raise ProbeError("invalid_source_archive")
            data = archive.read(member)
            if hashlib.sha256(data).hexdigest() != SOURCE_HASHES[relative]:
                raise ProbeError("source_checksum_mismatch")
            target = destination.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            found.add(relative)
    if found != set(SOURCE_HASHES):
        raise ProbeError("source_archive_incomplete")


def check_crypto():
    for namespace in ("Crypto", "Cryptodome"):
        try:
            importlib.import_module(namespace + ".Cipher.AES")
            return
        except ImportError:
            pass
    # These are public dependency directories used by the author's installers.
    # No private application modules or loader are imported.
    candidate = pathlib.Path("/iptvplayer_rootfs/usr/lib") / (
        "python%d.%d" % sys.version_info[:2]) / "site-packages"
    if candidate.is_dir():
        sys.path.append(str(candidate))
        for namespace in ("Crypto", "Cryptodome"):
            try:
                importlib.import_module(namespace + ".Cipher.AES")
                return
            except ImportError:
                pass
    raise ProbeError("missing_pycryptodome_dependency")


def run_probe(engine_dir, online):
    # Verify supplied source too; never use an unverified local engine.
    for relative, expected in SOURCE_HASHES.items():
        path = engine_dir / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ProbeError("source_checksum_mismatch")
    check_crypto()
    sys.path.insert(0, str(engine_dir))
    logging.disable(logging.CRITICAL)
    from tools_cenc.wvl3.cdm.cdm import Cdm
    from tools_cenc.wvl3.cdm.deviceconfig import DeviceConfig
    cdm = Cdm(logging.getLogger("disabled"))
    session_id = None
    result = {"stage": "import", "python": platform.python_version(),
              "source_commit": COMMIT, "test": "public_demo_only",
              "canalplus_tested": False, "video_playback_tested": False}
    try:
        session_id = cdm.open_session(PSSH, DeviceConfig())
        if not isinstance(session_id, bytes):
            raise ProbeError("session_creation_failed")
        challenge = cdm.get_license_request(session_id)
        if not isinstance(challenge, bytes):
            raise ProbeError("license_request_creation_failed")
        result["stage"] = "challenge_ready"
        if online:
            req = urllib.request.Request(LICENSE_URL, data=challenge,
                headers={"Content-Type": "application/octet-stream"}, method="POST")
            with urllib.request.urlopen(req, timeout=25) as response:
                license_data = response.read(1024 * 1024 + 1)
                result["http_status"] = response.status
            if len(license_data) > 1024 * 1024:
                raise ProbeError("license_response_too_large")
            status = cdm.provide_license(session_id, license_data)
            keys = cdm.get_keys(session_id) if status == 0 else []
            count = sum(1 for key in keys if key.type == "CONTENT")
            if status != 0 or count == 0:
                raise ProbeError("demo_license_processing_failed")
            result["stage"] = "demo_license_processed"
            result["content_key_count"] = count
        private_imports = [name for name in sys.modules if name == "e2iimport"
            or name.startswith(("Plugins.Extensions.IPTVPlayer", "Plugins.Extensions.archivCZSK"))]
        if private_imports:
            raise ProbeError("unexpected_application_dependency")
        result["private_application_imported"] = False
        result["status"] = "OK"
        return result
    finally:
        if session_id is not None:
            cdm.close_session(session_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true",
        help="request a license from the public demonstration server; no CANAL+ login")
    parser.add_argument("--engine-dir", type=pathlib.Path,
        help="use an already downloaded, pinned source directory")
    args = parser.parse_args()
    result = None
    try:
        # Suppress upstream diagnostics, which may contain DRM session data.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            if args.engine_dir:
                result = run_probe(args.engine_dir.resolve(), args.demo)
            else:
                with tempfile.TemporaryDirectory(prefix="independent-drm-demo-") as tmp:
                    directory = pathlib.Path(tmp)
                    prepare_engine(directory)
                    result = run_probe(directory, args.demo)
    except ProbeError as error:
        result = {"status": "ERROR", "reason": str(error), "canalplus_tested": False}
    except urllib.error.HTTPError as error:
        result = {"status": "ERROR", "reason": "http_error", "http_status": error.code}
    except Exception as error:
        result = {"status": "ERROR", "reason": type(error).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
