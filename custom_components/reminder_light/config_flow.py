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

CONF_ADDITIONAL_TIME = "additional_time"
CONF_FIRST_TIME = "first_time"
CONF_REMOVE_TIME = "remove_time"
CONF_SCHEDULE_PATTERN = "schedule_pattern"

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
    """Add and edit individual reminders in short, focused steps."""

    _initialized = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Start adding a reminder."""

        self._initialize({}, reconfigure=False)
        return await self._async_details_step("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Start editing an existing reminder."""

        self._initialize(dict(self._get_reconfigure_subentry().data), reconfigure=True)
        return await self._async_details_step("reconfigure", user_input)

    async def _async_details_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        """Collect the task's identity and display settings."""

        errors: dict[str, str] = {}
        if user_input is not None:
            name = str(user_input[CONF_REMINDER_NAME]).strip()
            if not name:
                errors[CONF_REMINDER_NAME] = "name_required"
            else:
                self._data.update(user_input)
                self._data[CONF_REMINDER_NAME] = name
                return await self.async_step_schedule()

        return self.async_show_form(
            step_id=step_id,
            data_schema=_details_schema(user_input or self._data),
            errors=errors,
        )

    async def async_step_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose a weekly pattern and primary reminder time."""

        if user_input is not None:
            self._schedule_pattern = user_input[CONF_SCHEDULE_PATTERN]
            first_time = _normalize_time(user_input[CONF_FIRST_TIME])
            self._times = sorted({first_time, *self._times[1:]})

            preset_days = _days_for_pattern(self._schedule_pattern)
            if preset_days is not None:
                self._weekdays = preset_days
                return await self.async_step_times()
            return await self.async_step_custom_days()

        return self.async_show_form(
            step_id="schedule",
            data_schema=_schedule_schema(
                self._schedule_pattern,
                self._times[0],
            ),
        )

    async def async_step_custom_days(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose weekdays for a custom weekly pattern."""

        errors: dict[str, str] = {}
        if user_input is not None:
            weekdays = user_input.get(CONF_WEEKDAYS, [])
            if not weekdays:
                errors[CONF_WEEKDAYS] = "weekday_required"
            else:
                self._weekdays = [day for day in WEEKDAYS if day in weekdays]
                return await self.async_step_times()

        return self.async_show_form(
            step_id="custom_days",
            data_schema=_custom_days_schema(
                (user_input or {}).get(CONF_WEEKDAYS, self._weekdays)
            ),
            errors=errors,
        )

    async def async_step_times(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Show current times and actions to add, remove, or continue."""

        menu_options = []
        if len(self._times) < MAX_DAILY_TIMES:
            menu_options.append("add_time")
        if len(self._times) > 1:
            menu_options.append("remove_time")
        menu_options.append("completion")
        return self.async_show_menu(
            step_id="times",
            menu_options=menu_options,
            description_placeholders={"times": _format_times(self._times)},
        )

    async def async_step_add_time(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add one more daily task time."""

        errors: dict[str, str] = {}
        if user_input is not None:
            additional_time = _normalize_time(user_input[CONF_ADDITIONAL_TIME])
            if additional_time in self._times:
                errors[CONF_ADDITIONAL_TIME] = "duplicate_time"
            elif len(self._times) >= MAX_DAILY_TIMES:
                errors[CONF_ADDITIONAL_TIME] = "max_times"
            else:
                self._times = sorted([*self._times, additional_time])
                return await self.async_step_times()

        return self.async_show_form(
            step_id="add_time",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_ADDITIONAL_TIME): selector.TimeSelector()}
            ),
            errors=errors,
        )

    async def async_step_remove_time(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Remove one of several configured task times."""

        if user_input is not None:
            self._times.remove(user_input[CONF_REMOVE_TIME])
            return await self.async_step_times()

        return self.async_show_form(
            step_id="remove_time",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_REMOVE_TIME): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=value,
                                    label=_format_time(value),
                                )
                                for value in self._times
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_completion(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Configure optional completion triggers and save the reminder."""

        errors: dict[str, str] = {}
        if user_input is not None:
            triggers = user_input.get(CONF_COMPLETION_TRIGGERS, [])
            if triggers:
                try:
                    await async_validate_trigger_config(self.hass, triggers)
                except (probatio.Invalid, HomeAssistantError):
                    errors[CONF_COMPLETION_TRIGGERS] = "invalid_trigger"

            if not errors:
                self._data[CONF_COMPLETION_TRIGGERS] = triggers
                return self._finish()

        return self.async_show_form(
            step_id="completion",
            data_schema=_completion_schema(
                (user_input or {}).get(
                    CONF_COMPLETION_TRIGGERS,
                    self._data.get(CONF_COMPLETION_TRIGGERS, []),
                )
            ),
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
        self._times = list(values.get(CONF_REMINDER_TIMES, [DEFAULT_REMINDER_TIME]))
        self._weekdays = list(values.get(CONF_WEEKDAYS, DEFAULT_WEEKDAYS))
        self._schedule_pattern = _pattern_for_days(self._weekdays)

    def _finish(self) -> SubentryFlowResult:
        """Persist the fully assembled reminder."""

        self._data.update(
            {
                CONF_REMINDER_ID: self._reminder_id,
                CONF_REMINDER_TIMES: self._times,
                CONF_WEEKDAYS: self._weekdays,
            }
        )
        title = f"Reminder: {self._data[CONF_REMINDER_NAME]}"
        if self._reconfigure:
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                data=self._data,
                title=title,
            )
        return self.async_create_entry(
            title=title,
            data=self._data,
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


def _details_schema(values: dict[str, Any]) -> probatio.Schema:
    """Build the compact reminder details schema."""

    return probatio.Schema(
        {
            probatio.Required(
                CONF_REMINDER_NAME,
                default=values.get(CONF_REMINDER_NAME, DEFAULT_REMINDER_NAME),
            ): selector.TextSelector(),
            probatio.Required(
                CONF_REMINDER_COLOR,
                default=values.get(CONF_REMINDER_COLOR, list(DEFAULT_REMINDER_COLOR)),
            ): selector.ColorRGBSelector(),
            probatio.Required(
                CONF_ENABLED,
                default=values.get(CONF_ENABLED, DEFAULT_ENABLED),
            ): selector.BooleanSelector(),
        }
    )


def _schedule_schema(pattern: str, first_time: str) -> probatio.Schema:
    """Build the repeat-pattern and primary-time schema."""

    return probatio.Schema(
        {
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
                CONF_FIRST_TIME,
                default=first_time,
            ): selector.TimeSelector(),
        }
    )


def _custom_days_schema(weekdays: list[str]) -> probatio.Schema:
    """Build a weekday multi-select for custom schedules."""

    return probatio.Schema(
        {
            probatio.Required(
                CONF_WEEKDAYS,
                default=weekdays,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_WEEKDAY_OPTIONS,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def _completion_schema(triggers: list[dict[str, Any]]) -> probatio.Schema:
    """Build the optional completion trigger schema."""

    return probatio.Schema(
        {
            probatio.Optional(
                CONF_COMPLETION_TRIGGERS,
                default=triggers,
            ): selector.TriggerSelector()
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


def _format_times(times: list[str]) -> str:
    """Format configured times for the time-management menu."""

    return ", ".join(_format_time(value) for value in times)


def _format_time(value: str) -> str:
    """Format an ISO time without unnecessary seconds."""

    parsed = time.fromisoformat(value)
    return parsed.strftime("%H:%M:%S" if parsed.second else "%H:%M")


def _normalize_time(value: str | time) -> str:
    """Normalize a selector time value to HH:MM:SS."""

    if isinstance(value, time):
        return value.replace(microsecond=0).isoformat()
    return time.fromisoformat(str(value)).replace(microsecond=0).isoformat()
