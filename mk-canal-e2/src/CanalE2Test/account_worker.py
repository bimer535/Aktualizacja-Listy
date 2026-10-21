#!/usr/bin/env python3
"""Device-code pairing and channel refresh, with no playback changes."""
import argparse
import json
import signal
import sys
import time
import uuid
from pathlib import Path

import canal_login_test as login_api
import canal_channels_test as channel_api
from session_recover import load_live_session

SESSION = Path("/etc/canal-e2/session.json")


def emit(stage, **fields):
    # Only the one-time pairing code is shown deliberately to the local user.
    # Never persist it or print account/session tokens, responses or URLs.
    print(json.dumps({"stage": stage, **fields}, ensure_ascii=False), flush=True)


def refresh(session_path=SESSION):
    if not session_path.is_file():
        emit("login_required")
        return False
    emit("refresh_channels")
    saved, ids, response, out = load_live_session(session_path, channel_api, emit)
    entries = channel_api.normalize_channels(out)
    if not entries:
        raise channel_api.ChannelError("no_channels_returned")
    channel_api.atomic_private_json(session_path.with_name("live.json"), {
        "schema_version": 1, "session_saved_at_utc": saved.get("saved_at_utc"),
        "client_ids": ids, "init_live_response": response, "channels": entries})
    emit("channels_loaded", channel_count=sum(item.get("authorized") is True for item in entries))
    return True


def login(session_path=SESSION):
    client = login_api.CanalLogin()
    device_id = str(uuid.uuid4())
    emit("generate_code")
    code, expires = client.create_code(device_id)
    emit("pairing_code", activation_code=code, expires_in=expires)
    deadline = time.monotonic() + expires
    while time.monotonic() < deadline:
        authentication = client.check_code(device_id, code)
        if authentication is not None:
            login_api.save_session(session_path, device_id, authentication)
            emit("authenticated")
            return refresh(session_path)
        time.sleep(min(3, max(0, deadline - time.monotonic())))
    raise login_api.LoginError("activation_code_expired")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("login", "refresh"))
    args = parser.parse_args()
    def interrupt(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    try:
        return 0 if (login() if args.mode == "login" else refresh()) else 1
    except KeyboardInterrupt:
        emit("cancelled")
        return 130
    except (login_api.LoginError, channel_api.ChannelError) as error:
        details = {}
        for field in ("status", "error_code"):
            value = getattr(error, field, None)
            if isinstance(value, int):
                details[field] = value
        emit("error", reason=error.reason, **details)
        return 1
    except Exception as error:
        emit("error", reason=type(error).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
