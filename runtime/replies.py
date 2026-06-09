from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .env import load_environment


def append_reply_log(text: str, channel_id: str, thread_id: str | None) -> bool:
    log_path = os.environ.get("TENX_REPLY_LOG_PATH", "").strip()
    if not log_path:
        return False
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channel_id": channel_id,
        "thread_id": thread_id,
        "text": text,
    }
    path = Path(log_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return True


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Record a reply for the active 10x runtime turn")
    parser.add_argument("--text", required=True, help="Reply text")
    parser.add_argument("--channel-id", help="Channel id; defaults to TENX_REPLY_CHANNEL_ID")
    parser.add_argument("--thread-id", help="Thread id; defaults to TENX_REPLY_THREAD_ID")
    args = parser.parse_args(argv)

    load_environment()
    channel_id = (args.channel_id or os.environ.get("TENX_REPLY_CHANNEL_ID") or "").strip()
    if not channel_id:
        raise SystemExit("Missing channel id; set --channel-id or TENX_REPLY_CHANNEL_ID")
    thread_id = (args.thread_id or os.environ.get("TENX_REPLY_THREAD_ID") or "").strip() or None
    text = args.text.strip()
    if not text:
        raise SystemExit("Reply text is empty")
    if not append_reply_log(text, channel_id, thread_id):
        print(text, flush=True)


if __name__ == "__main__":
    main()
