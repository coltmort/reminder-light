"""Data models for Reminder Light."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompletionCondition:
    """A Home Assistant state condition that completes a reminder."""

    entity_id: str
    target_state: str


@dataclass(frozen=True)
class ReminderDefinition:
    """User-configured reminder behavior."""

    reminder_id: str
    name: str
    due_time: str
    color: tuple[int, int, int]
    completion: CompletionCondition


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

    reminder: ReminderDefinition
    state: ReminderRuntimeState
