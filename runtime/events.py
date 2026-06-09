from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NormalizedEvent:
    """Common event shape emitted by triggers and consumed by workflows."""

    source: str
    text: str
    user_id: str = ""
    channel_id: str = ""
    thread_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    attachments: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowResult:
    text: str
    metadata: dict[str, str] = field(default_factory=dict)
