"""Isolated player bootstrap and DASH rendition selection. No account data here."""
import hashlib
import base64
import io
import json
import os
import platform
import re
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

from canal_stream_test_v2 import StreamError, WV_UUID, checked_url

PLAYER_COMMIT = "00aaa894db78a5c71c325d7cab1ea9ba5855024d"
PLAYER_URL = ("https://raw.githubusercontent.com/skyjet18/exteplayer3/" + PLAYER_COMMIT
              + "/ipk/exteplayer3_183_armv7ahf.ipk")
PLAYER_SHA256 = "c920ddc6fe6f8d1a77916ef9f842f4072483e8fec189a059563c784dc7ee22ce"
MAX_PACKAGE = 16 * 1024 * 1024
MAX_EXTRACTED = 100 * 1024 * 1024


def tag(node):
    return node.tag.rsplit("}", 1)[-1]


def own_pssh(node):
    values = []
    for child in node:
        if tag(child) == "ContentProtection" and WV_UUID in child.get("schemeIdUri", "").lower():
            for element in child.iter():
                if tag(element) == "pssh" and element.text:
                    value = "".join(element.text.split())
                    if value not in values:
                        values.append(value)
    return values


def own_kids(node):
    values = set()
    for child in node:
        if tag(child) != "ContentProtection":
            continue
        for name, value in child.attrib.items():
            if name.rsplit("}", 1)[-1] == "default_KID":
                for item in value.split():
                    normalized = item.replace("-", "").lower()
                    if re.fullmatch("[0-9a-f]{32}", normalized):
                        values.add(normalized)
    return values


def number(value):
    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        return 0


def track_groups(root):
    """Keep every advertised rendition; representation IDs stay in the worker."""
    root_pssh, root_kids = own_pssh(root), own_kids(root)
    for pi, period in enumerate(node for node in root if tag(node) == "Period"):
        videos, audios = [], []
        pp, pk = own_pssh(period) or root_pssh, own_kids(period) or root_kids
        for ai, adaptation in enumerate(node for node in period if tag(node) == "AdaptationSet"):
            ap, ak = own_pssh(adaptation) or pp, own_kids(adaptation) or pk
            for ri, rep in enumerate(node for node in adaptation if tag(node) == "Representation"):
                attrs = {**adaptation.attrib, **rep.attrib}
                kind = attrs.get("contentType", "").lower()
                mime, codec = attrs.get("mimeType", "").lower(), attrs.get("codecs", "").lower()
                if mime.startswith("video/") or number(attrs.get("height")):
                    kind = "video"
                elif mime.startswith("audio/") or codec.startswith(("mp4a", "ac-3", "ec-3")):
                    kind = "audio"
                item = {"root": root, "period": period, "adaptation": adaptation, "rep": rep,
                        "period_index": pi, "adaptation_index": ai, "rep_index": ri,
                        "id": rep.get("id"), "height": number(attrs.get("height")),
                        "width": number(attrs.get("width")), "frame_rate": attrs.get("frameRate", ""),
                        "bandwidth": number(attrs.get("bandwidth")), "codec": codec,
                        "lang": attrs.get("lang", "").lower(),
                        "pssh": own_pssh(rep) or ap, "kids": own_kids(rep) or ak}
                if kind == "video":
                    videos.append(item)
                elif kind == "audio":
                    audios.append(item)
        if not videos:
            continue
        yield videos, audios


def select_tracks(root, height, video_predicate=None, audio_predicate=None):
    for videos, audios in track_groups(root):
        options = [x for x in videos if 0 < x["height"] <= height]
        if video_predicate is not None:
            options = [x for x in options if video_predicate(x)]
        if not options:
            raise StreamError("requested_resolution_unavailable")
        video = max(options, key=lambda x: (x["height"], x["codec"].startswith("avc"), x["bandwidth"]))
        if audio_predicate is not None:
            audios = [x for x in audios if audio_predicate(x)]
        if not audios:
            raise StreamError("audio_track_missing")
        audio = max(audios, key=lambda x: (x["lang"] in ("pl", "pol", "pl-pl"),
                                          x["codec"].startswith("mp4a"), x["bandwidth"]))
        return video, audio
    raise StreamError("video_track_missing")


def initialization_url(track, mpd_url):
    """Resolve DASH BaseURL and inherited initialization addressing."""
    base, template, initialization = mpd_url, {}, None
    for node in (track["root"], track["period"], track["adaptation"], track["rep"]):
        xml_base = node.get("{http://www.w3.org/XML/1998/namespace}base")
        if xml_base:
            base = urljoin(base, xml_base)
        bases = [child for child in node if tag(child) == "BaseURL" and child.text]
        if bases:
            base = urljoin(base, bases[0].text.strip())
        for child in node:
            if tag(child) == "SegmentTemplate":
                template.update(child.attrib)
            elif tag(child) in ("SegmentList", "SegmentBase"):
                for item in child:
                    if tag(item) == "Initialization":
                        initialization = item.get("sourceURL")
    value = template.get("initialization") or initialization
    if not value:
        raise StreamError("initialization_addressing_unsupported")
    value = value.replace("$$", "\0")
    attrs = {**track["adaptation"].attrib, **track["rep"].attrib}
    def replace(match):
        field = "id" if match.group(1) == "RepresentationID" else "bandwidth"
        raw = attrs.get(field)
        if raw is None:
            raise StreamError("initialization_template_missing_value")
        if match.group(2):
            if not raw.isdigit():
                raise StreamError("initialization_template_invalid_number")
            return str(int(raw)).zfill(int(match.group(2)))
        return raw
    value = re.sub(r"\$(RepresentationID|Bandwidth)(?:%0([1-9][0-9]?)d)?\$", replace, value)
    if "$" in value:
        raise StreamError("initialization_template_unsupported")
    return checked_url(value.replace("\0", "$"), base)


def initialization_metadata(data):
    """Read tenc/PSSH boxes only; never read or expose media decryption keys."""
    kids, pssh, protected, schemes = set(), [], [], set()
    encrypted_entries = 0
    boxes = 0
    containers = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"sinf", b"schi"}
    def walk(start, end, depth=0):
        nonlocal boxes, encrypted_entries
        if depth > 16:
            raise StreamError("initialization_nesting_limit")
        position = start
        while position < end:
            if position + 8 > end:
                raise StreamError("invalid_initialization_box")
            size = int.from_bytes(data[position:position + 4], "big")
            kind = data[position + 4:position + 8]
            header = 8
            if size == 1:
                if position + 16 > end:
                    raise StreamError("invalid_initialization_box")
                size, header = int.from_bytes(data[position + 8:position + 16], "big"), 16
            elif size == 0:
                size = end - position
            if size < header or position + size > end:
                raise StreamError("invalid_initialization_box")
            boxes += 1
            if boxes > 10000:
                raise StreamError("initialization_box_limit")
            body = position + header
            finish = position + size
            if kind in containers:
                walk(body, finish, depth + 1)
            elif kind == b"stsd":
                if body + 8 > finish:
                    raise StreamError("invalid_initialization_stsd")
                walk(body + 8, finish, depth + 1)
            elif kind in (b"encv", b"enca"):
                encrypted_entries += 1
                offset = 78 if kind == b"encv" else 28
                if kind == b"enca" and body + 10 <= finish:
                    version = int.from_bytes(data[body + 8:body + 10], "big")
                    if version not in (0, 1, 2):
                        raise StreamError("unsupported_audio_sample_entry")
                    offset += 16 if version == 1 else 36 if version == 2 else 0
                if body + offset > finish:
                    raise StreamError("invalid_initialization_sample_entry")
                walk(body + offset, finish, depth + 1)
            elif kind == b"tenc":
                # ISO full-box version/flags + reserved/pattern/protection/IV + KID.
                if body + 24 > finish or data[body] not in (0, 1):
                    raise StreamError("invalid_initialization_tenc")
                encrypted = data[body + 6] != 0
                protected.append(encrypted)
                if encrypted:
                    kids.add(data[body + 8:body + 24].hex())
            elif kind == b"schm" and body + 8 <= finish:
                scheme = data[body + 4:body + 8].decode("ascii", "replace")
                if scheme in ("cenc", "cbcs", "cens", "cbc1"):
                    schemes.add(scheme)
            elif kind == b"pssh" and header == 8 and size >= 32:
                if data[position + 12:position + 28].hex() == WV_UUID.replace("-", ""):
                    value = base64.b64encode(data[position:finish]).decode("ascii")
                    if value not in pssh:
                        pssh.append(value)
            position = finish
    walk(0, len(data))
    if encrypted_entries and not protected:
        raise StreamError("encrypted_initialization_without_tenc")
    if not boxes:
        raise StreamError("empty_initialization")
    return {"kids": kids, "pssh": pssh, "encrypted": any(protected), "schemes": sorted(schemes)}


def inspect_track_initialization(http, track, mpd_url):
    raw, _ = http.read(initialization_url(track, mpd_url))
    metadata = initialization_metadata(raw)
    track["manifest_kids"] = track["kids"]
    track["kids"] = metadata["kids"]
    track["encrypted"] = metadata["encrypted"]
    track["init_pssh_count"] = len(metadata["pssh"])
    track["pssh"] = list(dict.fromkeys(metadata["pssh"] + track["pssh"]))
    return metadata


def track_reference(track):
    return (track["period_index"], track["adaptation_index"], track["id"], track["rep_index"])


def reference_matches(track, reference):
    current = track_reference(track)
    return (current[:2] == reference[:2]
            and (current[2] == reference[2] if reference[2] is not None else current[3] == reference[3]))


def licensed_video_options(root, maximum_height, key_ids):
    """Find advertised video renditions covered by already granted content keys."""
    heights = {number(node.get("height")) for node in root.iter()}
    choices = {}
    for cap in sorted(height for height in heights if 0 < height <= maximum_height):
        try:
            video, _ = select_tracks(root, cap, video_predicate=lambda item: bool(item["kids"]) and item["kids"] <= key_ids)
        except StreamError as error:
            if error.reason == "requested_resolution_unavailable":
                continue
            raise
        choices[track_reference(video)] = video
    return sorted(choices.values(), key=lambda item: (item["height"], item["codec"].startswith("avc"), item["bandwidth"]), reverse=True)


def filtered_manifest(root, final_url, height, expected=None, video_reference=None, audio_reference=None):
    if root.tag.startswith("{"):
        ET.register_namespace("", root.tag[1:].split("}", 1)[0])
    predicate = None if video_reference is None else lambda item: reference_matches(item, video_reference)
    audio_predicate = None if audio_reference is None else lambda item: reference_matches(item, audio_reference)
    video, audio = select_tracks(root, height, video_predicate=predicate, audio_predicate=audio_predicate)
    identity = tuple((x["id"], x["height"], x["codec"], tuple(sorted(x["kids"]))) for x in (video, audio))
    if expected is not None and identity != expected:
        raise StreamError("stream_tracks_changed_restart_required")
    period = video["period"]
    for child in list(root):
        if tag(child) == "Period" and child is not period:
            root.remove(child)
        elif tag(child) in ("Location", "PatchLocation"):
            root.remove(child)
    for adaptation in list(period):
        if tag(adaptation) != "AdaptationSet":
            continue
        keep = [x["rep"] for x in (video, audio) if x["adaptation"] is adaptation]
        if not keep:
            period.remove(adaptation)
            continue
        for rep in list(adaptation):
            if tag(rep) == "Representation" and rep not in keep:
                adaptation.remove(rep)
    # Media URLs must keep resolving against the remote MPD, not localhost.
    bases = [node for node in root if tag(node) == "BaseURL"]
    if bases:
        for node in bases:
            node.text = urljoin(final_url, (node.text or "").strip())
    else:
        namespace = root.tag[:-3] if root.tag.endswith("MPD") else ""
        base = ET.Element(namespace + "BaseURL")
        base.text = urljoin(final_url, ".")
        root.insert(0, base)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), identity


def ar_member(body, wanted):
    if not body.startswith(b"!<arch>\n"):
        raise StreamError("invalid_player_package")
    offset = 8
    while offset + 60 <= len(body):
        header = body[offset:offset + 60]
        if header[58:60] != b"`\n":
            break
        try:
            size = int(header[48:58])
            name = header[:16].decode("ascii").strip().rstrip("/")
        except (ValueError, UnicodeError):
            break
        offset += 60
        if size < 0 or offset + size > len(body):
            break
        if name == wanted:
            return body[offset:offset + size]
        offset += size + size % 2
    raise StreamError("invalid_player_package")


def patch_private_rpath(body):
    old, new = b"/usr/lib/exteplayer3_deps\0", b"$ORIGIN/../lib\0"
    if old not in body:
        return body
    return body.replace(old, new + b"\0" * (len(old) - len(new)))


def extract_player(body, destination):
    if hashlib.sha256(body).hexdigest() != PLAYER_SHA256:
        raise StreamError("player_package_checksum_mismatch")
    archive = ar_member(body, "data.tar.gz")
    total, files, links = 0, {}, []
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar:
            name = member.name.removeprefix("./")
            if name == "usr/bin/exteplayer3":
                relative = Path("bin/exteplayer3")
            elif name.startswith("usr/lib/exteplayer3_deps/"):
                basename = name.rsplit("/", 1)[-1]
                if not re.fullmatch(r"lib[A-Za-z0-9_.+-]+\.so(?:\.[0-9.]+)?", basename):
                    continue
                relative = Path("lib") / basename
            else:
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.issym():
                if Path(member.linkname).name != member.linkname or member.linkname.startswith("."):
                    raise StreamError("unsafe_player_library_link")
                links.append((target, member.linkname))
            elif member.isfile():
                total += member.size
                if member.size < 0 or total > MAX_EXTRACTED:
                    raise StreamError("player_package_too_large")
                data = tar.extractfile(member).read(member.size + 1)
                if len(data) != member.size:
                    raise StreamError("incomplete_player_package")
                data = patch_private_rpath(data)
                target.write_bytes(data)
                target.chmod(0o755)
                files[str(relative)] = hashlib.sha256(data).hexdigest()
    if "bin/exteplayer3" not in files or len(files) < 8:
        raise StreamError("incomplete_player_package")
    for target, link in links:
        if not (target.parent / link).is_file():
            raise StreamError("missing_player_library_target")
        target.symlink_to(link)
    (destination / "verified-files.json").write_text(json.dumps(files))


def ensure_player(cache, event):
    if platform.machine().lower() not in ("armv7l", "armv7", "armv7ahf"):
        raise StreamError("test_player_requires_armv7_decoder")
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = cache / "player-183-private-v1"
    marker = destination / "verified-files.json"
    if marker.is_file():
        try:
            files = json.loads(marker.read_text())
            if files and all(hashlib.sha256((destination / name).read_bytes()).hexdigest() == digest
                             for name, digest in files.items()):
                return destination / "bin/exteplayer3"
        except (OSError, ValueError, TypeError):
            pass
        raise StreamError("installed_test_player_checksum_mismatch")
    if shutil.disk_usage(cache).free < 120 * 1024 * 1024:
        raise StreamError("need_120mb_free_for_private_player")
    event("prepare_player")
    try:
        with urllib.request.urlopen(PLAYER_URL, timeout=35) as response:
            package = response.read(MAX_PACKAGE + 1)
    except Exception:
        raise StreamError("player_download_failed") from None
    if len(package) > MAX_PACKAGE:
        raise StreamError("player_package_too_large")
    with tempfile.TemporaryDirectory(prefix="player-stage-", dir=cache) as tmp:
        stage = Path(tmp) / "player"
        stage.mkdir()
        extract_player(package, stage)
        os.replace(stage, destination)
    return destination / "bin/exteplayer3"
