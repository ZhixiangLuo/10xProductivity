"""Playwright-friendly typing with per-keystroke jitter."""

from __future__ import annotations

import random
from typing import Any, Literal, Protocol

from .delays import pause_uniform


class _SupportsType(Protocol):
    def type(self, text: str, *, delay: int = 0, **kwargs: Any) -> None: ...


def human_type(
    locator: _SupportsType,
    text: str,
    *,
    min_delay_ms: int = 50,
    max_delay_ms: int = 200,
) -> None:
    """Type ``text`` with one random inter-key delay for the whole string (Playwright ``delay``)."""
    lo, hi = (min_delay_ms, max_delay_ms) if min_delay_ms <= max_delay_ms else (max_delay_ms, min_delay_ms)
    locator.type(text, delay=random.randint(lo, hi))


def human_type_rich_keyboard(
    page: Any,
    text: str,
    *,
    min_delay_ms: int = 55,
    max_delay_ms: int = 165,
) -> None:
    """Character-level typing on ``page.keyboard`` with micro-pauses (comments, sensitive UIs)."""
    lo, hi = (min_delay_ms, max_delay_ms) if min_delay_ms <= max_delay_ms else (max_delay_ms, min_delay_ms)
    for ch in text:
        if ch == "\n":
            page.keyboard.press("Enter")
        elif ch == "\r":
            continue
        else:
            page.keyboard.type(ch, delay=random.randint(lo, hi))

        if ch in " \n\t":
            pause_uniform(0.04, 0.22)
        elif ch in ".!?,;:":
            pause_uniform(0.12, 0.38)
        elif ch == "/":
            pause_uniform(0.08, 0.2)

        if random.random() < 0.06:
            pause_uniform(0.25, 0.9)
        elif random.random() < 0.015:
            pause_uniform(0.9, 1.8)


def paste_like_keyboard(page: Any, text: str) -> None:
    """Bulk insert (clipboard-style): no per-key cadence; tiny pauses before/after."""
    pause_uniform(0.1, 0.32)
    page.keyboard.insert_text(text)
    pause_uniform(0.05, 0.2)


def paste_like_editor(locator: Any, text: str) -> None:
    """Bulk insert into a focused contenteditable / Quill node (Playwright ``fill``)."""
    pause_uniform(0.12, 0.28)
    locator.fill(text)
    pause_uniform(0.06, 0.18)


def human_type_rich_editor(
    locator: Any,
    text: str,
    *,
    min_delay_ms: int = 45,
    max_delay_ms: int = 130,
) -> None:
    """Typed input bound to ``locator`` (clears selection first) — avoids stray ``page.keyboard`` focus."""
    lo, hi = (min_delay_ms, max_delay_ms) if min_delay_ms <= max_delay_ms else (max_delay_ms, min_delay_ms)
    pause_uniform(0.08, 0.18)
    try:
        locator.press("Control+a")
    except Exception:
        pass
    pause_uniform(0.06, 0.14)
    # Default Playwright ``type`` timeout (30s) is too low for long comments + per-key delay.
    est_ms = len(text) * hi + 15_000
    timeout_ms = max(90_000, min(300_000, int(est_ms * 1.2)))
    locator.type(text, delay=random.randint(lo, hi), timeout=timeout_ms)
    pause_uniform(0.05, 0.12)


def comment_input_mode(text: str) -> Literal["human", "paste"]:
    """Prefer human typing for short comments; paste-like for long ones — still random mix."""
    n = len(text)
    if n <= 72:
        p_human = 0.82
    elif n <= 160:
        p_human = 0.52
    else:
        p_human = 0.28
    return "human" if random.random() < p_human else "paste"
