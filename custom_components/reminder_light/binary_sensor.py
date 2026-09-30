"""Binary sensors for Reminder Light."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ReminderLightCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one due sensor per reminder."""

    coordinator: ReminderLightCoordinator = entry.runtime_data
    for reminder in coordinator.data.reminders.values():
        async_add_entities(
            [ReminderDueBinarySensor(coordinator, reminder.reminder_id)],
            config_subentry_id=reminder.subentry_id,
        )


class ReminderDueBinarySensor(
    CoordinatorEntity[ReminderLightCoordinator], BinarySensorEntity
):
    """Expose whether one reminder is currently due."""

    _attr_has_entity_name = False

    def __init__(
        self, coordinator: ReminderLightCoordinator, reminder_id: str
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator)
        reminder = coordinator.reminder(reminder_id)
        self._reminder_id = reminder_id
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{reminder_id}_due"
        self._attr_name = f"{reminder.name} due"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.entry.entry_id}_{reminder_id}")},
            name=reminder.name,
            manufacturer="Reminder Light",
            model="Scheduled reminder",
        )

    @property
    def is_on(self) -> bool:
        """Return true if the reminder is due."""

        return self.coordinator.state(self._reminder_id).due

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return useful reminder metadata."""

        reminder = self.coordinator.reminder(self._reminder_id)
        state = self.coordinator.state(self._reminder_id)
        return {
            "reminder_id": reminder.reminder_id,
            "reminder_name": reminder.name,
            "times": list(reminder.times),
            "weekdays": list(reminder.weekdays),
            "completion_trigger_count": len(reminder.completion_triggers),
            "enabled": reminder.enabled,
            "last_due": state.last_due,
            "last_completed": state.last_completed,
        }
