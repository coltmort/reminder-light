"""Buttons for Reminder Light."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Set up one manual completion button per reminder."""

    coordinator: ReminderLightCoordinator = entry.runtime_data
    for reminder in coordinator.data.reminders.values():
        async_add_entities(
            [ManualCompleteButton(coordinator, reminder.reminder_id)],
            config_subentry_id=reminder.subentry_id,
        )


class ManualCompleteButton(CoordinatorEntity[ReminderLightCoordinator], ButtonEntity):
    """Manually complete one configured reminder."""

    _attr_entity_registry_visible_default = False
    _attr_has_entity_name = True
    _attr_name = "Mark complete"

    def __init__(
        self, coordinator: ReminderLightCoordinator, reminder_id: str
    ) -> None:
        """Initialize the button."""

        super().__init__(coordinator)
        reminder = coordinator.reminder(reminder_id)
        self._reminder_id = reminder_id
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{reminder_id}_complete"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.entry.entry_id}_{reminder_id}")},
            name=f"{reminder.name} reminder controls",
            manufacturer="Reminder Light",
            model="Reminder status and controls",
        )

    async def async_press(self) -> None:
        """Complete the reminder."""

        await self.coordinator.async_complete(self._reminder_id)
