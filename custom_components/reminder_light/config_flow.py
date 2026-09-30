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

CONF_SCHEDULE_PATTERN = "schedule_pattern"
CONF_TASK_TIME = "time"

SCHEDULE_EVERY_DAY = "every_day"
SCHEDULE_WEEKDAYS = "weekdays"
SCHEDULE_WEEKENDS = "weekends"
SCHEDULE_CUSTOM = "custom"

_WEEKDAY_OPTIONS = [
    selector.SelectOptionDict(value="mon", label="Monday"),
    selector.SelectOptionDict(value="tue", label="Tuesday"),
    selector.SelectOptionDict(value="wed", label="Wednesday"),
    selector.SelectOptionDict(value="thu", label="Thursday"),
    selector.SelectOptionDict(value="fri", label="Friday"),
    selector.SelectOptionDict(value="sat", label="Saturday"),
    selector.SelectOptionDict(value="sun", label="Sunday"),
]
_SCHEDULE_OPTIONS = [
    selector.SelectOptionDict(value=SCHEDULE_EVERY_DAY, label="Every day"),
    selector.SelectOptionDict(value=SCHEDULE_WEEKDAYS, label="Weekdays"),
    selector.SelectOptionDict(value=SCHEDULE_WEEKENDS, label="Weekends"),
    selector.SelectOptionDict(value=SCHEDULE_CUSTOM, label="Custom days"),
]


class ReminderLightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Reminder Light."""

    VERSION = 3

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
    """Add and edit individual reminders in one responsive form."""

    _initialized = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a reminder."""

        self._initialize({}, reconfigure=False)
        return await self._async_reminder_step("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing reminder."""

        self._initialize(dict(self._get_reconfigure_subentry().data), reconfigure=True)
        return await self._async_reminder_step("reconfigure", user_input)

    async def _async_reminder_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        """Collect and validate the complete reminder definition."""

        errors: dict[str, str] = {}
        if user_input is not None:
            name = str(user_input[CONF_REMINDER_NAME]).strip()
            if not name:
                errors[CONF_REMINDER_NAME] = "name_required"
            pattern = user_input[CONF_SCHEDULE_PATTERN]
            weekdays = _days_for_pattern(pattern)
            if weekdays is None:
                weekdays = user_input.get(CONF_WEEKDAYS, [])
                if not weekdays:
                    errors[CONF_WEEKDAYS] = "weekday_required"

            time_rows = user_input.get(CONF_REMINDER_TIMES, [])
            times = [
                _normalize_time(row[CONF_TASK_TIME])
                for row in time_rows
                if row.get(CONF_TASK_TIME)
            ]
            if not times:
                errors[CONF_REMINDER_TIMES] = "time_required"
            elif len(times) > MAX_DAILY_TIMES:
                errors[CONF_REMINDER_TIMES] = "max_times"
            elif len(times) != len(set(times)):
                errors[CONF_REMINDER_TIMES] = "duplicate_time"

            triggers = user_input.get(CONF_COMPLETION_TRIGGERS, [])
            if triggers:
                try:
                    await async_validate_trigger_config(self.hass, triggers)
                except (probatio.Invalid, HomeAssistantError):
                    errors[CONF_COMPLETION_TRIGGERS] = "invalid_trigger"

            if not errors:
                data = dict(user_input)
                data.pop(CONF_SCHEDULE_PATTERN, None)
                data[CONF_REMINDER_ID] = self._reminder_id
                data[CONF_REMINDER_NAME] = name
                data[CONF_REMINDER_TIMES] = sorted(times)
                data[CONF_WEEKDAYS] = [day for day in WEEKDAYS if day in weekdays]
                return self._finish(data)

        return self.async_show_form(
            step_id=step_id,
            data_schema=_reminder_schema(user_input or self._data),
            errors=errors,
        )

    def _initialize(self, values: dict[str, Any], reconfigure: bool) -> None:
        """Initialize working state once for this flow."""

        if self._initialized:
            return
        self._initialized = True
        self._reconfigure = reconfigure
        self._data = values
        self._reminder_id = values.get(CONF_REMINDER_ID, uuid4().hex)

    def _finish(self, data: dict[str, Any]) -> SubentryFlowResult:
        """Persist the fully assembled reminder."""

        title = f"Reminder: {data[CONF_REMINDER_NAME]}"
        if self._reconfigure:
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                data=data,
                title=title,
            )
        return self.async_create_entry(
            title=title,
            data=data,
            unique_id=self._reminder_id,
        )


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
                    min=0.25,
                    max=300,
                    step=0.25,
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


def _reminder_schema(values: dict[str, Any]) -> probatio.Schema:
    """Build the single-page reminder editor."""

    weekdays = list(values.get(CONF_WEEKDAYS, DEFAULT_WEEKDAYS))
    pattern = values.get(CONF_SCHEDULE_PATTERN, _pattern_for_days(weekdays))
    stored_times = values.get(CONF_REMINDER_TIMES, [DEFAULT_REMINDER_TIME])
    time_rows = (
        stored_times
        if stored_times and isinstance(stored_times[0], dict)
        else [{CONF_TASK_TIME: value} for value in stored_times]
    )

    return probatio.Schema(
        {
            probatio.Required(
                CONF_REMINDER_NAME,
                default=values.get(CONF_REMINDER_NAME, DEFAULT_REMINDER_NAME),
            ): selector.TextSelector(),
            probatio.Required(
                CONF_SCHEDULE_PATTERN,
                default=pattern,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_SCHEDULE_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            probatio.Required(
                CONF_WEEKDAYS,
                default=weekdays,
                description={
                    "visible": {
                        "field": CONF_SCHEDULE_PATTERN,
                        "value": SCHEDULE_CUSTOM,
                    }
                },
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_WEEKDAY_OPTIONS,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            probatio.Required(
                CONF_REMINDER_TIMES,
                default=time_rows,
            ): selector.ObjectSelector(
                selector.ObjectSelectorConfig(
                    fields={
                        CONF_TASK_TIME: {
                            "selector": selector.TimeSelector(),
                            "label": "Task time",
                            "required": True,
                        }
                    },
                    multiple=True,
                    label_field=CONF_TASK_TIME,
                )
            ),
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


def _pattern_for_days(weekdays: list[str]) -> str:
    """Return the friendliest preset matching a stored weekday list."""

    day_set = set(weekdays)
    if day_set == set(WEEKDAYS):
        return SCHEDULE_EVERY_DAY
    if day_set == set(WEEKDAYS[:5]):
        return SCHEDULE_WEEKDAYS
    if day_set == set(WEEKDAYS[5:]):
        return SCHEDULE_WEEKENDS
    return SCHEDULE_CUSTOM


def _days_for_pattern(pattern: str) -> list[str] | None:
    """Expand a schedule preset, or return None for a custom pattern."""

    if pattern == SCHEDULE_EVERY_DAY:
        return list(WEEKDAYS)
    if pattern == SCHEDULE_WEEKDAYS:
        return list(WEEKDAYS[:5])
    if pattern == SCHEDULE_WEEKENDS:
        return list(WEEKDAYS[5:])
    return None


def _normalize_time(value: str | time) -> str:
    """Normalize a selector time value to HH:MM:SS."""

    if isinstance(value, time):
        return value.replace(microsecond=0).isoformat()
    return time.fromisoformat(str(value)).replace(microsecond=0).isoformat()
