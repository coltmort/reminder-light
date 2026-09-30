"""Binary sensors for Reminder Light."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ReminderLightCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Reminder Light binary sensors."""

    coordinator: ReminderLightCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ReminderDueBinarySensor(coordinator)])


class ReminderDueBinarySensor(
    CoordinatorEntity[ReminderLightCoordinator], BinarySensorEntity
):
    """Expose whether the reminder is currently due."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ReminderLightCoordinator) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_primary_due"
        self._attr_translation_key = "reminder_due"

    @property
    def is_on(self) -> bool:
        """Return true if the reminder is due."""

        return self.coordinator.data.state.due

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return useful reminder metadata."""

        reminder = self.coordinator.data.reminder
        state = self.coordinator.data.state
        return {
            "reminder_id": reminder.reminder_id,
            "reminder_name": reminder.name,
            "due_time": reminder.due_time,
            "completion_entity": reminder.completion.entity_id,
            "completion_state": reminder.completion.target_state,
            "last_due": state.last_due,
            "last_completed": state.last_completed,
        }
