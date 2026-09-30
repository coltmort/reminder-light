"""Coordinator and reminder manager for Reminder Light."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta
import logging
from typing import Any

import probatio

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.trigger import (
    async_initialize_triggers,
    async_validate_trigger_config,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BRIGHTNESS,
    CONF_COMPLETION_TRIGGERS,
    CONF_ENABLED,
    CONF_OUTPUT_LIGHT,
    CONF_REMINDER_COLOR,
    CONF_REMINDER_ID,
    CONF_REMINDER_NAME,
    CONF_REMINDER_TIMES,
    CONF_ROTATION_SECONDS,
    CONF_WEEKDAYS,
    DEFAULT_BRIGHTNESS,
    DEFAULT_ENABLED,
    DEFAULT_REMINDER_COLOR,
    DEFAULT_ROTATION_SECONDS,
    DOMAIN,
    STORE_VERSION,
    SUBENTRY_TYPE_REMINDER,
    WEEKDAYS,
)
from .models import ReminderDefinition, ReminderLightData, ReminderRuntimeState

_LOGGER = logging.getLogger(__name__)


class ReminderLightCoordinator(DataUpdateCoordinator[ReminderLightData]):
    """Own reminder state, scheduling, completion triggers, and light output."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""

        self.entry = entry
        self.store: Store[dict[str, Any]] = Store(
            hass,
            STORE_VERSION,
            f"{DOMAIN}_{entry.entry_id}",
        )
        self._unsubscribers: list[Callable[[], None]] = []
        self._rotation_index = 0

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            always_update=False,
        )

    async def async_setup(self) -> None:
        """Load persisted state and begin listening."""

        reminders = self._build_reminders()
        stored = await self.store.async_load() or {}
        stored_states = stored.get("reminders")
        if stored_states is None and reminders:
            # Version 1 stored one reminder directly at the root.
            stored_states = {next(iter(reminders)): stored}

        states = {
            reminder_id: ReminderRuntimeState(
                **(stored_states or {}).get(reminder_id, {})
            )
            for reminder_id in reminders
        }
        self.async_set_updated_data(ReminderLightData(reminders, states))

        state_changed = False
        for reminder_id, reminder in reminders.items():
            if not reminder.enabled and states[reminder_id].due:
                states[reminder_id].due = False
                state_changed = True
        if state_changed:
            await self._async_save_state()

        for reminder in reminders.values():
            self._register_schedule_listeners(reminder)
            await self._async_register_completion_triggers(reminder)

        rotation_seconds = self.entry.data.get(
            CONF_ROTATION_SECONDS, DEFAULT_ROTATION_SECONDS
        )
        self._unsubscribers.append(
            async_track_time_interval(
                self.hass,
                self._handle_rotation,
                timedelta(seconds=rotation_seconds),
            )
        )
        await self._async_apply_light_state()

    def async_unload(self) -> None:
        """Release active Home Assistant listeners."""

        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()

    def reminder(self, reminder_id: str) -> ReminderDefinition:
        """Return a reminder by stable ID."""

        return self.data.reminders[reminder_id]

    def state(self, reminder_id: str) -> ReminderRuntimeState:
        """Return runtime state for a reminder."""

        return self.data.states[reminder_id]

    @property
    def due_reminders(self) -> list[ReminderDefinition]:
        """Return enabled reminders which are currently due."""

        return [
            reminder
            for reminder_id, reminder in self.data.reminders.items()
            if reminder.enabled and self.data.states[reminder_id].due
        ]

    async def async_mark_due(self, reminder_id: str) -> None:
        """Mark one reminder due."""

        reminder = self.reminder(reminder_id)
        state = self.state(reminder_id)
        if not reminder.enabled or (state.due and not state.completed):
            return

        state.due = True
        state.completed = False
        state.last_due = dt_util.utcnow().isoformat()
        self._rotation_index = 0
        await self._async_save_state()
        self.async_update_listeners()
        await self._async_apply_light_state()

    async def async_complete(self, reminder_id: str) -> None:
        """Complete one reminder when it is due."""

        state = self.state(reminder_id)
        if not state.due:
            return

        state.due = False
        state.completed = True
        state.last_completed = dt_util.utcnow().isoformat()
        self._rotation_index = 0
        await self._async_save_state()
        self.async_update_listeners()
        await self._async_apply_light_state()

    def _build_reminders(self) -> dict[str, ReminderDefinition]:
        """Create in-memory reminder definitions from config subentries."""

        reminders: dict[str, ReminderDefinition] = {}
        for subentry in self.entry.subentries.values():
            if subentry.subentry_type != SUBENTRY_TYPE_REMINDER:
                continue

            data = subentry.data
            reminder_id = data[CONF_REMINDER_ID]
            color = data.get(CONF_REMINDER_COLOR, DEFAULT_REMINDER_COLOR)
            reminders[reminder_id] = ReminderDefinition(
                reminder_id=reminder_id,
                subentry_id=subentry.subentry_id,
                name=data[CONF_REMINDER_NAME],
                times=tuple(data[CONF_REMINDER_TIMES]),
                weekdays=frozenset(data[CONF_WEEKDAYS]),
                color=tuple(color),
                completion_triggers=tuple(
                    dict(trigger)
                    for trigger in data.get(CONF_COMPLETION_TRIGGERS, [])
                ),
                enabled=data.get(CONF_ENABLED, DEFAULT_ENABLED),
            )
        return reminders

    def _register_schedule_listeners(self, reminder: ReminderDefinition) -> None:
        """Register every configured due-time listener."""

        for configured_time in reminder.times:
            parsed_time = time.fromisoformat(configured_time)

            @callback
            def _handle_time(
                now: datetime, reminder_id: str = reminder.reminder_id
            ) -> None:
                if WEEKDAYS[now.weekday()] not in self.reminder(reminder_id).weekdays:
                    return
                self.hass.async_create_task(self.async_mark_due(reminder_id))

            self._unsubscribers.append(
                async_track_time_change(
                    self.hass,
                    _handle_time,
                    hour=parsed_time.hour,
                    minute=parsed_time.minute,
                    second=parsed_time.second,
                )
            )

    async def _async_register_completion_triggers(
        self, reminder: ReminderDefinition
    ) -> None:
        """Register Home Assistant completion triggers for one reminder."""

        if not reminder.completion_triggers:
            return

        try:
            validated = await async_validate_trigger_config(
                self.hass, list(reminder.completion_triggers)
            )

            async def _handle_trigger(
                variables: dict[str, Any], context: Context | None = None
            ) -> None:
                await self.async_complete(reminder.reminder_id)

            unsubscribe = await async_initialize_triggers(
                self.hass,
                validated,
                _handle_trigger,
                DOMAIN,
                f"Reminder Light: {reminder.name}",
                _LOGGER.log,
            )
            if unsubscribe is not None:
                self._unsubscribers.append(unsubscribe)
        except (ValueError, probatio.Invalid, HomeAssistantError):
            _LOGGER.exception(
                "Unable to initialize completion triggers for reminder %s",
                reminder.name,
            )

    @callback
    def _handle_rotation(self, now: datetime) -> None:
        """Advance the displayed color while several reminders are due."""

        if len(self.due_reminders) < 2:
            return
        self._rotation_index = (self._rotation_index + 1) % len(self.due_reminders)
        self.hass.async_create_task(self._async_apply_light_state())

    async def _async_save_state(self) -> None:
        """Persist all runtime state."""

        await self.store.async_save(
            {
                "reminders": {
                    reminder_id: {
                        "due": state.due,
                        "completed": state.completed,
                        "last_completed": state.last_completed,
                        "last_due": state.last_due,
                    }
                    for reminder_id, state in self.data.states.items()
                }
            }
        )

    async def _async_apply_light_state(self) -> None:
        """Reflect all due reminders on the selected output light."""

        output_light = self.entry.data[CONF_OUTPUT_LIGHT]
        due_reminders = self.due_reminders

        if due_reminders:
            reminder = due_reminders[self._rotation_index % len(due_reminders)]
            await self.hass.services.async_call(
                LIGHT,
                SERVICE_TURN_ON,
                {
                    "entity_id": output_light,
                    ATTR_RGB_COLOR: reminder.color,
                    ATTR_BRIGHTNESS: self.entry.data.get(
                        CONF_BRIGHTNESS, DEFAULT_BRIGHTNESS
                    ),
                },
                blocking=False,
            )
            return

        await self.hass.services.async_call(
            LIGHT,
            SERVICE_TURN_OFF,
            {"entity_id": output_light},
            blocking=False,
        )
