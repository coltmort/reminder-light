"""Constants for the Reminder Light integration."""

from __future__ import annotations

DOMAIN = "reminder_light"

PLATFORMS = ["binary_sensor", "button"]

CONF_OUTPUT_LIGHT = "output_light"
CONF_ROTATION_SECONDS = "rotation_seconds"
CONF_BRIGHTNESS = "brightness"
CONF_REMINDER_NAME = "reminder_name"
CONF_REMINDER_TIME = "reminder_time"
CONF_REMINDER_COLOR = "reminder_color"
CONF_COMPLETION_ENTITY = "completion_entity"
CONF_COMPLETION_STATE = "completion_state"

DEFAULT_ROTATION_SECONDS = 30
DEFAULT_BRIGHTNESS = 180
DEFAULT_REMINDER_NAME = "Reminder"
DEFAULT_REMINDER_TIME = "09:00"
DEFAULT_REMINDER_COLOR = "#00AEEF"
DEFAULT_COMPLETION_STATE = "on"

STORE_VERSION = 1
