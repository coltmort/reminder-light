"""Constants for the Reminder Light integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "reminder_light"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CALENDAR]
SUBENTRY_TYPE_REMINDER = "reminder"

CONF_OUTPUT_LIGHT = "output_light"
CONF_ROTATION_SECONDS = "rotation_seconds"
CONF_BRIGHTNESS = "brightness"

CONF_REMINDER_ID = "reminder_id"
CONF_REMINDER_NAME = "reminder_name"
CONF_REMINDER_TIMES = "reminder_times"
CONF_WEEKDAYS = "weekdays"
CONF_REMINDER_COLOR = "reminder_color"
CONF_COMPLETION_TRIGGERS = "completion_triggers"
CONF_ENABLED = "enabled"

# Version 1 keys retained for config-entry migration.
CONF_REMINDER_TIME = "reminder_time"
CONF_COMPLETION_ENTITY = "completion_entity"
CONF_COMPLETION_STATE = "completion_state"

DEFAULT_ROTATION_SECONDS = 30
DEFAULT_BRIGHTNESS = 180
DEFAULT_REMINDER_NAME = "Reminder"
DEFAULT_REMINDER_TIME = "09:00:00"
DEFAULT_REMINDER_COLOR = (0, 174, 239)
DEFAULT_COMPLETION_STATE = "on"
DEFAULT_ENABLED = True

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DEFAULT_WEEKDAYS = list(WEEKDAYS)
MAX_DAILY_TIMES = 6
CALENDAR_EVENT_DURATION_MINUTES = 30

STORE_VERSION = 1
