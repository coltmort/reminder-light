"""Data models for Reminder Light."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReminderDefinition:
    """User-configured reminder behavior."""

    reminder_id: str
    subentry_id: str
    name: str
    times: tuple[str, ...]
    weekdays: frozenset[str]
    color: tuple[int, int, int]
    completion_triggers: tuple[dict[str, Any], ...]
    enabled: bool


@dataclass
class ReminderRuntimeState:
    """Persisted runtime state for one reminder."""

    due: bool = False
    completed: bool = False
    last_completed: str | None = None
    last_due: str | None = None


@dataclass
class ReminderLightData:
    """Coordinator data exposed to Reminder Light entities."""

    reminders: dict[str, ReminderDefinition] = field(default_factory=dict)
    states: dict[str, ReminderRuntimeState] = field(default_factory=dict)
