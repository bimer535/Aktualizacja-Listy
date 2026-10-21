#!/usr/bin/env python3
"""Fetch one selected channel's now/next outside the Enigma2 GUI process."""
import argparse
import json
import signal

from epg_data import EpgError, get_pair


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True)
    args = parser.parse_args()
    def interrupt(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    try:
        pair = get_pair(args.channel)
        event = {"stage": "epg_loaded", "channel_id": args.channel, "source": "CANAL+", **pair}
        result = 0
    except KeyboardInterrupt:
        return 130
    except EpgError as error:
        event = {"stage": "epg_error", "channel_id": args.channel, "reason": error.reason}
        result = 1
    except Exception:
        event = {"stage": "epg_error", "channel_id": args.channel, "reason": "epg_unavailable"}
        result = 1
    print(json.dumps(event, ensure_ascii=False), flush=True)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
