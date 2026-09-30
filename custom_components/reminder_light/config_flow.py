"""Config flow for Reminder Light."""

from __future__ import annotations

from datetime import time
from typing import Any
from uuid import uuid4

import probatio

from homeassistant import config_entries
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigFlowResult,
    ConfigSubentryFlow,
    FlowType,
    SubentryFlowContext,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.trigger import async_validate_trigger_config

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
    DEFAULT_REMINDER_NAME,
    DEFAULT_REMINDER_TIME,
    DEFAULT_ROTATION_SECONDS,
    DEFAULT_WEEKDAYS,
    DOMAIN,
    MAX_DAILY_TIMES,
    SUBENTRY_TYPE_REMINDER,
    WEEKDAYS,
)

_TIME_FIELD_PREFIX = "schedule_time_"
_WEEKDAY_OPTIONS = [
    selector.SelectOptionDict(value="mon", label="Monday"),
    selector.SelectOptionDict(value="tue", label="Tuesday"),
    selector.SelectOptionDict(value="wed", label="Wednesday"),
    selector.SelectOptionDict(value="thu", label="Thursday"),
    selector.SelectOptionDict(value="fri", label="Friday"),
    selector.SelectOptionDict(value="sat", label="Saturday"),
    selector.SelectOptionDict(value="sun", label="Sunday"),
]


class ReminderLightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Reminder Light."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the shared reminder display."""

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Reminder Light", data=user_input)

        return self.async_show_form(step_id="user", data_schema=_display_schema())

    async def async_on_create_entry(
        self, result: ConfigFlowResult
    ) -> ConfigFlowResult:
        """Open the first reminder flow after configuring the display."""

        subentry_result = await self.hass.config_entries.subentries.async_init(
            (result["result"].entry_id, SUBENTRY_TYPE_REMINDER),
            context=SubentryFlowContext(source=SOURCE_USER),
        )
        result["next_flow"] = (
            FlowType.CONFIG_SUBENTRIES_FLOW,
            subentry_result["flow_id"],
        )
        return result

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update shared display settings."""

        entry = self._get_reconfigure_entry()
        if user_input is not None:
            return self.async_update_and_abort(entry, data=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_display_schema(dict(entry.data)),
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the reminder subentry flow."""

        return {SUBENTRY_TYPE_REMINDER: ReminderSubentryFlow}


class ReminderSubentryFlow(ConfigSubentryFlow):
    """Add and edit individual reminders."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a reminder."""

        errors: dict[str, str] = {}
        if user_input is not None:
            reminder_id = uuid4().hex
            data = await self._async_validate_and_normalize(user_input, errors)
            if data is not None:
                data[CONF_REMINDER_ID] = reminder_id
                return self.async_create_entry(
                    title=data[CONF_REMINDER_NAME],
                    data=data,
                    unique_id=reminder_id,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_reminder_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing reminder."""

        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = await self._async_validate_and_normalize(user_input, errors)
            if data is not None:
                data[CONF_REMINDER_ID] = subentry.data[CONF_REMINDER_ID]
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    data=data,
                    title=data[CONF_REMINDER_NAME],
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_reminder_schema(user_input or dict(subentry.data)),
            errors=errors,
        )

    async def _async_validate_and_normalize(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> dict[str, Any] | None:
        """Validate a reminder form and return its persisted representation."""

        name = str(user_input[CONF_REMINDER_NAME]).strip()
        times = _extract_times(user_input)
        weekdays = user_input.get(CONF_WEEKDAYS, [])
        triggers = user_input.get(CONF_COMPLETION_TRIGGERS, [])

        if not name:
            errors[CONF_REMINDER_NAME] = "name_required"
        if not times:
            errors[f"{_TIME_FIELD_PREFIX}1"] = "time_required"
        if not weekdays:
            errors[CONF_WEEKDAYS] = "weekday_required"

        if triggers:
            try:
                await async_validate_trigger_config(self.hass, triggers)
            except (probatio.Invalid, HomeAssistantError):
                errors[CONF_COMPLETION_TRIGGERS] = "invalid_trigger"

        if errors:
            return None

        return {
            CONF_REMINDER_NAME: name,
            CONF_REMINDER_TIMES: times,
            CONF_WEEKDAYS: [day for day in WEEKDAYS if day in weekdays],
            CONF_REMINDER_COLOR: list(user_input[CONF_REMINDER_COLOR]),
            CONF_COMPLETION_TRIGGERS: triggers,
            CONF_ENABLED: user_input.get(CONF_ENABLED, DEFAULT_ENABLED),
        }


def _display_schema(values: dict[str, Any] | None = None) -> probatio.Schema:
    """Build the shared display settings schema."""

    values = values or {}
    output_light = values.get(CONF_OUTPUT_LIGHT)
    output_marker = (
        probatio.Required(CONF_OUTPUT_LIGHT, default=output_light)
        if output_light
        else probatio.Required(CONF_OUTPUT_LIGHT)
    )
    return probatio.Schema(
        {
            output_marker: selector.EntitySelector(
                selector.EntitySelectorConfig(domain="light")
            ),
            probatio.Required(
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
            probatio.Required(
                CONF_BRIGHTNESS,
                default=values.get(CONF_BRIGHTNESS, DEFAULT_BRIGHTNESS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=255,
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
        }
    )


def _reminder_schema(values: dict[str, Any] | None = None) -> probatio.Schema:
    """Build the add/edit reminder schema."""

    values = values or {}
    configured_times = list(values.get(CONF_REMINDER_TIMES, []))
    if not configured_times:
        configured_times = [
            _normalize_time(
                values.get(f"{_TIME_FIELD_PREFIX}1", DEFAULT_REMINDER_TIME)
            )
        ]

    schema: dict[Any, Any] = {
        probatio.Required(
            CONF_REMINDER_NAME,
            default=values.get(CONF_REMINDER_NAME, DEFAULT_REMINDER_NAME),
        ): selector.TextSelector(),
        probatio.Required(
            CONF_WEEKDAYS,
            default=values.get(CONF_WEEKDAYS, DEFAULT_WEEKDAYS),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=_WEEKDAY_OPTIONS,
                multiple=True,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
    }

    for index in range(MAX_DAILY_TIMES):
        key = f"{_TIME_FIELD_PREFIX}{index + 1}"
        default = (
            configured_times[index]
            if index < len(configured_times)
            else values.get(key)
        )
        marker = (
            probatio.Required(key, default=default)
            if index == 0
            else probatio.Optional(key)
        )
        if default is not None and index > 0:
            marker = probatio.Optional(key, default=default)
        schema[marker] = selector.TimeSelector()

    schema.update(
        {
            probatio.Required(
                CONF_REMINDER_COLOR,
                default=values.get(CONF_REMINDER_COLOR, list(DEFAULT_REMINDER_COLOR)),
            ): selector.ColorRGBSelector(),
            probatio.Optional(
                CONF_COMPLETION_TRIGGERS,
                default=values.get(CONF_COMPLETION_TRIGGERS, []),
            ): selector.TriggerSelector(),
            probatio.Required(
                CONF_ENABLED,
                default=values.get(CONF_ENABLED, DEFAULT_ENABLED),
            ): selector.BooleanSelector(),
        }
    )
    return probatio.Schema(schema)


def _extract_times(user_input: dict[str, Any]) -> list[str]:
    """Extract, normalize, sort, and deduplicate schedule times."""

    return sorted(
        {
            _normalize_time(value)
            for index in range(1, MAX_DAILY_TIMES + 1)
            if (value := user_input.get(f"{_TIME_FIELD_PREFIX}{index}")) is not None
        }
    )


def _normalize_time(value: str | time) -> str:
    """Normalize a selector time value to HH:MM:SS."""

    if isinstance(value, time):
        return value.replace(microsecond=0).isoformat()
    return time.fromisoformat(str(value)).replace(microsecond=0).isoformat()
