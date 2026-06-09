from __future__ import annotations

import datetime
import json
import logging
import os
import random
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from runtime.events import NormalizedEvent

logger = logging.getLogger(__name__)

AGENT_REPLY_PREFIX = "[agent_reply]:"
_BASE = 25.0
_JITTER_LO = 1.0
_JITTER_HI = 10.0
_BF_LO = 1.5
_BF_HI = 2.5
_RESET_HOUR = 8
_RESET_JITTER = 3600
_CHECK_CHUNK = 60.0
_HISTORY_LIMIT = 50


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx


_SSL_CTX = _ssl_context()


def _base_interval() -> float:
    return _BASE + random.uniform(_JITTER_LO, _JITTER_HI)


def _backoff(current: float) -> float:
    return current * random.uniform(_BF_LO, _BF_HI) + random.uniform(_JITTER_LO, _JITTER_HI)


def _next_reset_dt() -> datetime.datetime:
    now = datetime.datetime.now()
    candidate = now.replace(hour=_RESET_HOUR, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += datetime.timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += datetime.timedelta(days=1)
    return candidate + datetime.timedelta(seconds=random.uniform(0, _RESET_JITTER))


def slack_api(
    endpoint: str,
    token: str,
    cookie: str,
    *,
    method: str = "GET",
    params: dict | None = None,
    body: dict | None = None,
) -> dict:
    url = f"https://slack.com/api/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Cookie": f"d={cookie}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
        result = json.loads(resp.read().decode())
    if not result.get("ok"):
        raise RuntimeError(f"Slack {endpoint} error: {result.get('error')}")
    return result


def _find_self_dm(token: str, cookie: str, self_user_id: str) -> str | None:
    result = slack_api(
        "conversations.open",
        token,
        cookie,
        method="POST",
        body={"users": self_user_id},
    )
    return (result.get("channel") or {}).get("id")


def post_self_dm(token: str, cookie: str, channel: str, text: str) -> str:
    result = slack_api(
        "chat.postMessage",
        token,
        cookie,
        method="POST",
        body={"channel": channel, "text": f"{AGENT_REPLY_PREFIX} {text}"},
    )
    return str(result.get("ts") or "")


def _load_state(state_file: Path) -> dict:
    try:
        return json.loads(state_file.read_text()) if state_file.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state_file: Path, state: dict) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state), encoding="utf-8")


def _poll_loop(
    handler: Callable[[NormalizedEvent], None],
    token: str,
    cookie: str,
    state_file: Path,
    *,
    post_ack: bool,
) -> None:
    try:
        auth = slack_api("auth.test", token, cookie)
        self_user_id = auth["user_id"]
        dm_channel = _find_self_dm(token, cookie, self_user_id)
    except Exception as exc:
        logger.error("Slack self-DM poller startup failed: %s", exc)
        return
    if not dm_channel:
        logger.error("Slack self-DM channel not found for user %s", self_user_id)
        return

    state = _load_state(state_file)
    oldest_ts: str | None = state.get("last_ts")
    if oldest_ts is None:
        try:
            latest = slack_api(
                "conversations.history",
                token,
                cookie,
                params={"channel": dm_channel, "limit": 1},
            )
            messages = latest.get("messages", [])
            oldest_ts = messages[0]["ts"] if messages else f"{time.time():.6f}"
        except Exception:
            oldest_ts = f"{time.time():.6f}"
        _save_state(state_file, {"last_ts": oldest_ts})

    interval = _base_interval()
    next_reset = _next_reset_dt()
    next_poll_at = time.monotonic()
    logger.info("Slack self-DM poller started (channel=%s, last_ts=%s)", dm_channel, oldest_ts)

    while True:
        now_dt = datetime.datetime.now()
        now_mono = time.monotonic()
        if now_dt >= next_reset:
            interval = _base_interval()
            next_reset = _next_reset_dt()
            next_poll_at = now_mono
        if now_mono < next_poll_at:
            time.sleep(min(_CHECK_CHUNK, next_poll_at - now_mono))
            continue

        try:
            params = {"channel": dm_channel, "limit": _HISTORY_LIMIT}
            if oldest_ts:
                params["oldest"] = oldest_ts
            data = slack_api("conversations.history", token, cookie, params=params)
            raw_messages = data.get("messages", [])
            watermark_before = oldest_ts
            for item in raw_messages:
                ts = item.get("ts", "")
                if ts and (oldest_ts is None or ts > oldest_ts):
                    oldest_ts = ts

            new_messages = [
                item
                for item in raw_messages
                if item.get("user") == self_user_id
                and item.get("subtype") is None
                and not (item.get("text") or "").startswith(AGENT_REPLY_PREFIX)
            ]
            if new_messages:
                interval = _base_interval()
                for item in reversed(new_messages):
                    text = (item.get("text") or "").strip()
                    if not text:
                        continue
                    event = NormalizedEvent(
                        source="slack_polling",
                        text=text,
                        user_id=self_user_id,
                        channel_id=dm_channel,
                        thread_id=dm_channel,
                        metadata={"slack_ts": str(item.get("ts") or "")},
                    )
                    threading.Thread(target=handler, args=(event,), name="SlackPollHandler", daemon=True).start()
                    if post_ack:
                        ack_ts = post_self_dm(token, cookie, dm_channel, "Message received.")
                        if ack_ts and (oldest_ts is None or ack_ts > oldest_ts):
                            oldest_ts = ack_ts
            else:
                interval = _backoff(interval)
            if oldest_ts != watermark_before:
                _save_state(state_file, {"last_ts": oldest_ts})
        except urllib.error.URLError as exc:
            logger.warning("Slack self-DM poller network error: %s", exc)
        except Exception:
            logger.exception("Slack self-DM poller error")
        next_poll_at = time.monotonic() + interval


def start_slack_poller(
    handler: Callable[[NormalizedEvent], None],
    *,
    state_file: Path,
    post_ack: bool = False,
) -> threading.Thread:
    token = os.environ.get("SLACK_XOXC", "").strip()
    cookie = os.environ.get("SLACK_D_COOKIE", "").strip()
    if not token or not cookie:
        logger.warning("Slack polling disabled: SLACK_XOXC or SLACK_D_COOKIE missing")
        return threading.Thread(target=lambda: None, daemon=True)

    thread = threading.Thread(
        target=_poll_loop,
        args=(handler, token, cookie, state_file),
        kwargs={"post_ack": post_ack},
        name="SlackPollingTrigger",
        daemon=True,
    )
    thread.start()
    return thread
