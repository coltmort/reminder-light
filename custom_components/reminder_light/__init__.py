"""Reminder Light custom integration."""

from __future__ import annotations

from types import MappingProxyType

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BRIGHTNESS,
    CONF_COMPLETION_ENTITY,
    CONF_COMPLETION_STATE,
    CONF_COMPLETION_TRIGGERS,
    CONF_ENABLED,
    CONF_OUTPUT_LIGHT,
    CONF_REMINDER_COLOR,
    CONF_REMINDER_ID,
    CONF_REMINDER_NAME,
    CONF_REMINDER_TIME,
    CONF_REMINDER_TIMES,
    CONF_ROTATION_SECONDS,
    CONF_WEEKDAYS,
    DEFAULT_BRIGHTNESS,
    DEFAULT_COMPLETION_STATE,
    DEFAULT_ENABLED,
    DEFAULT_REMINDER_COLOR,
    DEFAULT_REMINDER_NAME,
    DEFAULT_REMINDER_TIME,
    DEFAULT_ROTATION_SECONDS,
    DEFAULT_WEEKDAYS,
    PLATFORMS,
    SUBENTRY_TYPE_REMINDER,
)
from .coordinator import ReminderLightCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Reminder Light from a config entry."""

    coordinator = ReminderLightCoordinator(hass, entry)
    await coordinator.async_setup()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Reminder Light config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: ReminderLightCoordinator = entry.runtime_data
        coordinator.async_unload()

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate the original single-reminder entry to reminder subentries."""

    if entry.version >= 2:
        return True

    config = {**entry.data, **entry.options}
    reminder_id = "primary"
    old_time = str(config.get(CONF_REMINDER_TIME, DEFAULT_REMINDER_TIME))
    if len(old_time) == 5:
        old_time = f"{old_time}:00"

    old_color = config.get(CONF_REMINDER_COLOR, "#00AEEF")
    if isinstance(old_color, str):
        value = old_color.lstrip("#")
        color = [
            int(value[0:2], 16),
            int(value[2:4], 16),
            int(value[4:6], 16),
        ]
    else:
        color = list(old_color or DEFAULT_REMINDER_COLOR)

    completion_triggers = []
    if completion_entity := config.get(CONF_COMPLETION_ENTITY):
        completion_triggers.append(
            {
                "trigger": "state",
                "entity_id": completion_entity,
                "to": config.get(CONF_COMPLETION_STATE, DEFAULT_COMPLETION_STATE),
            }
        )

    reminder_name = config.get(CONF_REMINDER_NAME, DEFAULT_REMINDER_NAME)
    if not any(
        subentry.unique_id == reminder_id for subentry in entry.subentries.values()
    ):
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType(
                    {
                        CONF_REMINDER_ID: reminder_id,
                        CONF_REMINDER_NAME: reminder_name,
                        CONF_REMINDER_TIMES: [old_time],
                        CONF_WEEKDAYS: DEFAULT_WEEKDAYS,
                        CONF_REMINDER_COLOR: color,
                        CONF_COMPLETION_TRIGGERS: completion_triggers,
                        CONF_ENABLED: DEFAULT_ENABLED,
                    }
                ),
                subentry_type=SUBENTRY_TYPE_REMINDER,
                title=reminder_name,
                unique_id=reminder_id,
            ),
        )
    hass.config_entries.async_update_entry(
        entry,
        data={
            CONF_OUTPUT_LIGHT: config[CONF_OUTPUT_LIGHT],
            CONF_ROTATION_SECONDS: config.get(
                CONF_ROTATION_SECONDS, DEFAULT_ROTATION_SECONDS
            ),
            CONF_BRIGHTNESS: config.get(CONF_BRIGHTNESS, DEFAULT_BRIGHTNESS),
        },
        options={},
        title="Reminder Light",
        version=2,
    )
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when its shared settings or reminders change."""

    await hass.config_entries.async_reload(entry.entry_id)
