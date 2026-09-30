"""Config flow for Reminder Light."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BRIGHTNESS,
    CONF_COMPLETION_ENTITY,
    CONF_COMPLETION_STATE,
    CONF_OUTPUT_LIGHT,
    CONF_REMINDER_COLOR,
    CONF_REMINDER_NAME,
    CONF_REMINDER_TIME,
    CONF_ROTATION_SECONDS,
    DEFAULT_BRIGHTNESS,
    DEFAULT_COMPLETION_STATE,
    DEFAULT_REMINDER_COLOR,
    DEFAULT_REMINDER_NAME,
    DEFAULT_REMINDER_TIME,
    DEFAULT_ROTATION_SECONDS,
    DOMAIN,
)

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class ReminderLightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Reminder Light."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create the first Reminder Light setup."""

        errors: dict[str, str] = {}

        if user_input is not None:
            if not TIME_RE.match(user_input[CONF_REMINDER_TIME]):
                errors[CONF_REMINDER_TIME] = "invalid_time"
            if not HEX_COLOR_RE.match(user_input[CONF_REMINDER_COLOR]):
                errors[CONF_REMINDER_COLOR] = "invalid_color"

            if not errors:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""

        return ReminderLightOptionsFlow(config_entry)


class ReminderLightOptionsFlow(config_entries.OptionsFlow):
    """Handle Reminder Light options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""

        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage Reminder Light options."""

        errors: dict[str, str] = {}

        if user_input is not None:
            if not TIME_RE.match(user_input[CONF_REMINDER_TIME]):
                errors[CONF_REMINDER_TIME] = "invalid_time"
            if not HEX_COLOR_RE.match(user_input[CONF_REMINDER_COLOR]):
                errors[CONF_REMINDER_COLOR] = "invalid_color"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        merged = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(merged),
            errors=errors,
        )


def _schema(values: dict[str, Any] | None = None) -> vol.Schema:
    """Build the setup/options schema."""

    values = values or {}

    return vol.Schema(
        {
            vol.Required(
                CONF_NAME,
                default=values.get(CONF_NAME, "Reminder Light"),
            ): str,
            vol.Required(
                CONF_OUTPUT_LIGHT,
                default=values.get(CONF_OUTPUT_LIGHT),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="light")
            ),
            vol.Required(
                CONF_ROTATION_SECONDS,
                default=values.get(CONF_ROTATION_SECONDS, DEFAULT_ROTATION_SECONDS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=5,
                    max=300,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="seconds",
                )
            ),
            vol.Required(
                CONF_BRIGHTNESS,
                default=values.get(CONF_BRIGHTNESS, DEFAULT_BRIGHTNESS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=255,
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                CONF_REMINDER_NAME,
                default=values.get(CONF_REMINDER_NAME, DEFAULT_REMINDER_NAME),
            ): str,
            vol.Required(
                CONF_REMINDER_TIME,
                default=values.get(CONF_REMINDER_TIME, DEFAULT_REMINDER_TIME),
            ): str,
            vol.Required(
                CONF_REMINDER_COLOR,
                default=values.get(CONF_REMINDER_COLOR, DEFAULT_REMINDER_COLOR),
            ): str,
            vol.Required(
                CONF_COMPLETION_ENTITY,
                default=values.get(CONF_COMPLETION_ENTITY),
            ): selector.EntitySelector(selector.EntitySelectorConfig()),
            vol.Required(
                CONF_COMPLETION_STATE,
                default=values.get(CONF_COMPLETION_STATE, DEFAULT_COMPLETION_STATE),
            ): str,
        }
    )
