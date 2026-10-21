"""Strict, public GitHub update metadata and package checks. No account data."""
import hashlib
import gzip
import io
import json
import re
import ssl
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import PurePosixPath

from version import APP_VERSION, PACKAGE_NAME, UPDATE_URL

MAX_MANIFEST = 32768
MAX_PACKAGE = 8 * 1024 * 1024
REPOSITORY_PATH = "/bimer535/Aktualizacja-Listy/main/mk-canal-e2/"
INSTALL_PREFIX = "usr/lib/enigma2/python/Plugins/Extensions/CanalE2Test/"


class UpdateError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}", value):
        raise UpdateError("invalid_update_version")
    return tuple(int(part) for part in value.split("."))


def allowed_url(value):
    if not isinstance(value, str) or len(value) > 1024:
        raise UpdateError("invalid_update_url")
    try:
        parsed = urllib.parse.urlsplit(value)
        path = urllib.parse.unquote(parsed.path)
        if (parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com"
                or parsed.port not in (None, 443) or parsed.username or parsed.password
                or parsed.query or parsed.fragment or not path.startswith(REPOSITORY_PATH)
                or ".." in PurePosixPath(path).parts or "\\" in path):
            raise UpdateError("update_url_outside_project")
    except ValueError:
        raise UpdateError("invalid_update_url") from None
    return value


class ProjectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        allowed_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, maximum):
    allowed_url(url)
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()), ProjectRedirect())
    request = urllib.request.Request(url, headers={
        "User-Agent": "MK-Canal-E2/" + APP_VERSION, "Cache-Control": "no-cache",
        "Accept-Encoding": "identity"})
    try:
        with opener.open(request, timeout=25) as response:
            allowed_url(response.url)
            if response.status != 200:
                raise UpdateError("update_http_error")
            body = response.read(maximum + 1)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise UpdateError("update_file_not_found") from None
        raise UpdateError("update_http_error") from None
    except urllib.error.URLError:
        raise UpdateError("update_connection_or_tls_error") from None
    if len(body) > maximum:
        raise UpdateError("update_download_too_large")
    return body


def validate_manifest(body):
    if len(body) > MAX_MANIFEST:
        raise UpdateError("update_manifest_too_large")
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        raise UpdateError("invalid_update_manifest") from None
    if not isinstance(data, dict) or data.get("schema") != 1 or data.get("package") != PACKAGE_NAME:
        raise UpdateError("wrong_update_package")
    version_tuple(data.get("version"))
    allowed_url(data.get("url"))
    if not isinstance(data.get("sha256"), str) or not re.fullmatch("[a-f0-9]{64}", data["sha256"]):
        raise UpdateError("invalid_update_checksum")
    size = data.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= MAX_PACKAGE:
        raise UpdateError("invalid_update_size")
    notes = data.get("notes", "")
    if not isinstance(notes, str) or len(notes) > 1600:
        raise UpdateError("invalid_update_notes")
    return {key: data[key] for key in ("version", "url", "sha256", "size")} | {"notes": notes}


def latest_manifest():
    return validate_manifest(download(UPDATE_URL, MAX_MANIFEST))


def ar_members(body):
    if not body.startswith(b"!<arch>\n"):
        raise UpdateError("invalid_ipk_archive")
    result, offset = {}, 8
    while offset < len(body):
        if offset + 60 > len(body):
            raise UpdateError("invalid_ipk_archive")
        header = body[offset:offset + 60]
        try:
            size = int(header[48:58])
            name = header[:16].decode("ascii").strip().rstrip("/")
        except (ValueError, UnicodeError):
            raise UpdateError("invalid_ipk_archive") from None
        offset += 60
        if header[58:60] != b"`\n" or size < 0 or offset + size > len(body) or name in result:
            raise UpdateError("invalid_ipk_archive")
        result[name] = body[offset:offset + size]
        offset += size + size % 2
    if set(result) != {"debian-binary", "control.tar.gz", "data.tar.gz"} or result["debian-binary"] != b"2.0\n":
        raise UpdateError("unsupported_ipk_format")
    return result


def validate_package(body, manifest):
    if len(body) != manifest["size"] or hashlib.sha256(body).hexdigest() != manifest["sha256"]:
        raise UpdateError("update_checksum_mismatch")
    members = ar_members(body)
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(members["control.tar.gz"])) as compressed:
            control_tar = compressed.read(256 * 1024 + 1)
        if len(control_tar) > 256 * 1024:
            raise UpdateError("ipk_control_limit")
        with tarfile.open(fileobj=io.BytesIO(control_tar), mode="r:") as archive:
            control = next((item for item in archive if item.name.removeprefix("./") == "control"), None)
            if control is None or not control.isfile() or not 0 < control.size <= 32768:
                raise UpdateError("invalid_ipk_control")
            text = archive.extractfile(control).read(32769).decode("utf-8")
        fields = {}
        for line in text.splitlines():
            if line and not line[0].isspace() and ":" in line:
                key, value = line.split(":", 1)
                if key in fields:
                    raise UpdateError("duplicate_ipk_control_field")
                fields[key] = value.strip()
        if fields.get("Package") != PACKAGE_NAME or fields.get("Version") != manifest["version"]:
            raise UpdateError("ipk_identity_or_version_mismatch")
        if fields.get("Architecture") != "all":
            raise UpdateError("unsupported_update_architecture")
        count, total = 0, 0
        with tarfile.open(fileobj=io.BytesIO(members["data.tar.gz"]), mode="r:gz") as archive:
            for item in archive:
                name = item.name.removeprefix("./")
                path = PurePosixPath(name)
                count += 1
                total += item.size
                if count > 1000 or total > 32 * 1024 * 1024:
                    raise UpdateError("ipk_content_limit")
                if (path.is_absolute() or ".." in path.parts or "\\" in name
                        or not name.startswith(INSTALL_PREFIX) or not (item.isfile() or item.isdir())):
                    raise UpdateError("ipk_writes_outside_plugin")
        if not count:
            raise UpdateError("empty_ipk_update")
    except (tarfile.TarError, OSError, UnicodeError):
        raise UpdateError("invalid_ipk_archive") from None
    return True
