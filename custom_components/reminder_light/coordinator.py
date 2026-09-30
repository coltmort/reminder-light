"""Coordinator and reminder manager for Reminder Light."""

from __future__ import annotations

from datetime import datetime
import logging
from collections.abc import Callable

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_RGB_COLOR, DOMAIN as LIGHT
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BRIGHTNESS,
    CONF_COMPLETION_ENTITY,
    CONF_COMPLETION_STATE,
    CONF_OUTPUT_LIGHT,
    CONF_REMINDER_COLOR,
    CONF_REMINDER_NAME,
    CONF_REMINDER_TIME,
    DEFAULT_BRIGHTNESS,
    DEFAULT_COMPLETION_STATE,
    DEFAULT_REMINDER_COLOR,
    DEFAULT_REMINDER_NAME,
    DEFAULT_REMINDER_TIME,
    DOMAIN,
    STORE_VERSION,
)
from .models import (
    CompletionCondition,
    ReminderDefinition,
    ReminderLightData,
    ReminderRuntimeState,
)

_LOGGER = logging.getLogger(__name__)


class ReminderLightCoordinator(DataUpdateCoordinator[ReminderLightData]):
    """Own reminder state, scheduling, completion triggers, and light output."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""

        self.entry = entry
        self.store: Store[dict] = Store(
            hass,
            STORE_VERSION,
            f"{DOMAIN}_{entry.entry_id}",
        )
        self._unsubscribers: list[Callable[[], None]] = []

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            always_update=False,
        )

    async def async_setup(self) -> None:
        """Load persisted state and begin listening."""

        reminder = self._build_reminder()
        stored = await self.store.async_load()
        runtime_state = ReminderRuntimeState(**(stored or {}))
        self.async_set_updated_data(ReminderLightData(reminder, runtime_state))

        self._register_schedule_listener(reminder)
        self._register_completion_listener(reminder)
        await self._async_apply_light_state()

    def async_unload(self) -> None:
        """Release active Home Assistant listeners."""

        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()

    async def async_mark_due(self) -> None:
        """Mark the configured reminder due."""

        if self.data.state.due and not self.data.state.completed:
            return

        self.data.state.due = True
        self.data.state.completed = False
        self.data.state.last_due = dt_util.utcnow().isoformat()
        await self._async_save_state()
        self.async_update_listeners()
        await self._async_apply_light_state()

    async def async_complete(self) -> None:
        """Complete the configured reminder."""

        if self.data.state.completed and not self.data.state.due:
            return

        self.data.state.due = False
        self.data.state.completed = True
        self.data.state.last_completed = dt_util.utcnow().isoformat()
        await self._async_save_state()
        self.async_update_listeners()
        await self._async_apply_light_state()

    def _build_reminder(self) -> ReminderDefinition:
        """Create the in-memory reminder definition from entry data/options."""

        config = {**self.entry.data, **self.entry.options}

        return ReminderDefinition(
            reminder_id="primary",
            name=config.get(CONF_REMINDER_NAME, DEFAULT_REMINDER_NAME),
            due_time=config.get(CONF_REMINDER_TIME, DEFAULT_REMINDER_TIME),
            color=_hex_to_rgb(config.get(CONF_REMINDER_COLOR, DEFAULT_REMINDER_COLOR)),
            completion=CompletionCondition(
                entity_id=config[CONF_COMPLETION_ENTITY],
                target_state=config.get(CONF_COMPLETION_STATE, DEFAULT_COMPLETION_STATE),
            ),
        )

    def _register_schedule_listener(self, reminder: ReminderDefinition) -> None:
        """Register the daily due-time listener."""

        hour, minute = (int(part) for part in reminder.due_time.split(":", 1))

        @callback
        def _handle_time(now: datetime) -> None:
            self.hass.async_create_task(self.async_mark_due())

        self._unsubscribers.append(
            async_track_time_change(
                self.hass,
                _handle_time,
                hour=hour,
                minute=minute,
                second=0,
            )
        )

    def _register_completion_listener(self, reminder: ReminderDefinition) -> None:
        """Register the first completion trigger implementation."""

        @callback
        def _handle_state_change(event: Event) -> None:
            new_state = event.data.get("new_state")
            if new_state is None:
                return

            if new_state.state != reminder.completion.target_state:
                return

            self.hass.async_create_task(self.async_complete())

        self._unsubscribers.append(
            async_track_state_change_event(
                self.hass,
                [reminder.completion.entity_id],
                _handle_state_change,
            )
        )

    async def _async_save_state(self) -> None:
        """Persist runtime state."""

        await self.store.async_save(
            {
                "due": self.data.state.due,
                "completed": self.data.state.completed,
                "last_completed": self.data.state.last_completed,
                "last_due": self.data.state.last_due,
            }
        )

    async def _async_apply_light_state(self) -> None:
        """Reflect the active reminder state on the selected output light."""

        config = {**self.entry.data, **self.entry.options}
        output_light = config[CONF_OUTPUT_LIGHT]

        if self.data.state.due:
            await self.hass.services.async_call(
                LIGHT,
                SERVICE_TURN_ON,
                {
                    "entity_id": output_light,
                    ATTR_RGB_COLOR: self.data.reminder.color,
                    ATTR_BRIGHTNESS: config.get(CONF_BRIGHTNESS, DEFAULT_BRIGHTNESS),
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


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    """Convert #RRGGBB to a Home Assistant RGB tuple."""

    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
