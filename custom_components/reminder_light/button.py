"""Buttons for Reminder Light."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Set up Reminder Light buttons."""

    coordinator: ReminderLightCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ManualCompleteButton(coordinator)])


class ManualCompleteButton(CoordinatorEntity[ReminderLightCoordinator], ButtonEntity):
    """Manually complete the configured reminder."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ReminderLightCoordinator) -> None:
        """Initialize the button."""

        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_primary_complete"
        self._attr_translation_key = "manual_complete"

    async def async_press(self) -> None:
        """Complete the reminder."""

        await self.coordinator.async_complete()
