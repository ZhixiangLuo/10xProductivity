"""Scheduler-oriented timing (OpenOutreach-inspired).

``delays.pause_uniform`` is used by ``search_posts`` / ``post_comment``; this
module adds backoff / active-hours helpers for future workers.

Provides: jittered backoff picks, daily-boundary waits, optional active-hours
guard, connect-spacing delay for throttled campaigns, and a tiny in-memory
priority queue for single-process workers later.
"""

from __future__ import annotations

import heapq
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .delays import (
    equal_jitter_delay_hours,
    equal_jitter_delay_seconds,
    seconds_until_local_midnight,
)


def connect_spacing_delay_seconds(
    base_delay_s: float,
    elapsed_s: float,
    action_fraction: float,
) -> float:
    """Next delay before another connect-style action (freemium-style pacing).

    When ``action_fraction >= 1``, returns ``base_delay_s``. Otherwise stretches
    the gap so short runs do not fire at full rate (see OpenOutreach
    ``ConnectStrategy.compute_delay``).
    """
    if action_fraction >= 1.0:
        return base_delay_s
    if action_fraction <= 0:
        return max(base_delay_s, elapsed_s)
    return max(base_delay_s, elapsed_s * (1.0 - action_fraction) / action_fraction)


def seconds_until_active_hours(
    *,
    tz_name: str = "UTC",
    start_hour: int = 10,
    end_hour: int = 20,
    rest_weekdays: tuple[int, ...] = (5, 6),
) -> float:
    """Seconds to sleep until the next allowed window, or ``0`` if inside window.

    Weekdays match ``datetime``: Mon=0 … Sun=6. ``rest_weekdays`` are *off* days.
    ``start_hour`` inclusive, ``end_hour`` exclusive (local wall clock in ``tz_name``).
    """
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)

    def _in_window(dt: datetime) -> bool:
        if dt.weekday() in rest_weekdays:
            return False
        return start_hour <= dt.hour < end_hour

    if _in_window(now):
        return 0.0

    candidate = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    while candidate.weekday() in rest_weekdays:
        candidate += timedelta(days=1)
    return max(0.0, (candidate - now).total_seconds())


@dataclass(frozen=True)
class BackoffSchedule:
    """Pure data: how long to wait before the next check (jitter applied on read)."""

    backoff_hours: float

    def next_delay_seconds(self) -> float:
        hours = equal_jitter_delay_hours(self.backoff_hours)
        return hours * 3600.0


def reschedule_after_rate_limit_daily() -> float:
    """Seconds until local midnight — same idea as OpenOutreach ``seconds_until_tomorrow``."""
    return seconds_until_local_midnight()


# --- Minimal in-memory queue (future single-process daemon / CLI worker) ---


class MemoryTaskQueue:
    """Small priority queue keyed by ``time.time()`` run time. Not persistent."""

    def __init__(self, time_fn: Callable[[], float] | None = None) -> None:
        self._time = time_fn or time.time
        self._heap: list[tuple[float, int, dict[str, Any]]] = []
        self._seq = 0

    def schedule_at(self, run_at_epoch: float, payload: dict[str, Any]) -> None:
        self._seq += 1
        heapq.heappush(self._heap, (run_at_epoch, self._seq, payload))

    def schedule_in(self, delay_seconds: float, payload: dict[str, Any]) -> None:
        self.schedule_at(self._time() + max(0.0, delay_seconds), payload)

    def schedule_jittered_backoff_hours(
        self,
        backoff_hours: float,
        payload: dict[str, Any],
    ) -> float:
        """Enqueue after equal-jitter delay; returns chosen delay in seconds."""
        delay_s = equal_jitter_delay_seconds(backoff_hours * 3600.0)
        self.schedule_in(delay_s, payload)
        return delay_s

    def seconds_until_next(self) -> float | None:
        if not self._heap:
            return None
        return max(0.0, self._heap[0][0] - self._time())

    def pop_due(self) -> dict[str, Any] | None:
        now = self._time()
        if self._heap and self._heap[0][0] <= now:
            _, __, payload = heapq.heappop(self._heap)
            return payload
        return None

    def __len__(self) -> int:
        return len(self._heap)
