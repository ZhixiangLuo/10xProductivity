"""Uniform and jittered wall-clock pauses (no queue)."""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def pause_uniform(min_s: float, max_s: float) -> None:
    """Sleep for a duration uniform in ``[min_s, max_s]``."""
    lo, hi = (min_s, max_s) if min_s <= max_s else (max_s, min_s)
    delay = random.uniform(lo, hi)
    logger.debug("pause_uniform: %.2fs", delay)
    time.sleep(delay)


def equal_jitter_delay_seconds(total_seconds: float) -> float:
    """Equal-jitter: return delay uniform in ``[total/2, total]`` (seconds).

    Same shape as OpenOutreach ``enqueue_check_pending`` backoff pick.
    """
    if total_seconds <= 0:
        return 0.0
    half = total_seconds / 2.0
    return half + random.uniform(0.0, half)


def equal_jitter_delay_hours(backoff_hours: float) -> float:
    """Equal-jitter delay in hours, uniform in ``[backoff_hours/2, backoff_hours]``."""
    return equal_jitter_delay_seconds(backoff_hours * 3600.0) / 3600.0


def seconds_until_local_midnight() -> float:
    """Seconds from now until next 00:00:00 in the process local timezone."""
    now = datetime.now()
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    return max(0.0, (tomorrow - now).total_seconds())
