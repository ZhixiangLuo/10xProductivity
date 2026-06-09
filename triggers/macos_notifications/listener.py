from __future__ import annotations

import datetime
import logging
import os
import plistlib
import sqlite3
import threading
import time
from typing import Callable

from runtime.events import NormalizedEvent

logger = logging.getLogger(__name__)

DB_PATH = os.path.expanduser("~/Library/Group Containers/group.com.apple.usernoted/db2/db")
DEFAULT_WATCH_APPS = {"com.tinyspeck.slackmacgap"}
POLL_INTERVAL = 0.1


def _mac_abs_to_dt(mac_ts: float) -> datetime.datetime:
    epoch = datetime.datetime(2001, 1, 1, tzinfo=datetime.timezone.utc)
    return epoch + datetime.timedelta(seconds=float(mac_ts))


def _parse_record(data: bytes) -> dict:
    payload = plistlib.loads(data)
    req = payload.get("req", {})
    raw_date = payload.get("date", 0)
    return {
        "app": payload.get("app", ""),
        "date": _mac_abs_to_dt(raw_date) if raw_date else None,
        "title": req.get("titl", "") or "",
        "subtitle": req.get("subt", "") or "",
        "body": req.get("body", "") or "",
    }


def _build_message_text(app: str, notification: dict) -> str:
    parts = []
    if notification["title"]:
        parts.append(f"[{notification['title']}]")
    if notification["subtitle"]:
        parts.append(notification["subtitle"])
    if notification["body"]:
        parts.append(notification["body"])
    text = " - ".join(parts) if parts else "(empty notification)"
    return f"macOS notification from {app}: {text}"


def _watch_loop(handler: Callable[[NormalizedEvent], None], watch_apps: set[str] | None) -> None:
    if not os.path.exists(DB_PATH):
        logger.warning("macOS notification DB not found at %s; listener disabled", DB_PATH)
        return
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except Exception as exc:
        logger.warning("macOS notification listener cannot open DB: %s", exc)
        return

    row = conn.execute("SELECT max(rec_id) FROM record").fetchone()
    last_rec_id = row[0] or 0
    logger.info("macOS notification listener started (rec_id>%d, apps=%s)", last_rec_id, watch_apps or "all")

    while True:
        time.sleep(POLL_INTERVAL)
        try:
            if watch_apps:
                placeholders = ",".join("?" * len(watch_apps))
                rows = conn.execute(
                    f"""
                    SELECT app.identifier, record.rec_id, record.data
                    FROM record
                    JOIN app ON record.app_id = app.app_id
                    WHERE record.rec_id > ?
                      AND app.identifier IN ({placeholders})
                    ORDER BY record.rec_id
                    """,
                    (last_rec_id, *watch_apps),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT app.identifier, record.rec_id, record.data
                    FROM record
                    JOIN app ON record.app_id = app.app_id
                    WHERE record.rec_id > ?
                    ORDER BY record.rec_id
                    """,
                    (last_rec_id,),
                ).fetchall()
            for row in rows:
                last_rec_id = max(last_rec_id, row["rec_id"])
                try:
                    app = row["identifier"]
                    notification = _parse_record(bytes(row["data"]))
                    event = NormalizedEvent(
                        source="macos_notifications",
                        text=_build_message_text(app, notification),
                        user_id="local",
                        channel_id="macos-notifications",
                        metadata={
                            "bundle_id": app,
                            "rec_id": str(row["rec_id"]),
                            "title": notification["title"],
                            "subtitle": notification["subtitle"],
                        },
                    )
                    threading.Thread(target=handler, args=(event,), name="MacOSNotificationHandler", daemon=True).start()
                except Exception:
                    logger.exception("Failed to parse macOS notification row %s", row["rec_id"])
        except sqlite3.OperationalError:
            pass
        except Exception:
            logger.exception("macOS notification listener error")


def start_macos_notification_listener(
    handler: Callable[[NormalizedEvent], None],
    *,
    watch_apps: set[str] | None = None,
) -> threading.Thread:
    if watch_apps is None:
        env_apps = os.environ.get("TENX_MACOS_NOTIF_WATCH_APPS", "").strip()
        watch_apps = {app.strip() for app in env_apps.split(",") if app.strip()} if env_apps else DEFAULT_WATCH_APPS

    thread = threading.Thread(
        target=_watch_loop,
        args=(handler, watch_apps),
        name="MacOSNotificationTrigger",
        daemon=True,
    )
    thread.start()
    return thread
