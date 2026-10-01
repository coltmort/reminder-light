"""Live color preview support for Reminder Light config flows."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_BRIGHTNESS,
    CONF_OUTPUT_LIGHT,
    CONF_REMINDER_COLOR,
    CONF_TEST_COLOR,
    DEFAULT_BRIGHTNESS,
    DOMAIN,
)

_PREVIEW_OFF_DELAY = 0.5
_DATA_ACTIVE_FLOWS = "preview_active_flows"
_DATA_PENDING_STOPS = "preview_pending_stops"


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/start_preview",
        probatio.Required("flow_id"): str,
        probatio.Required("flow_type"): probatio.Any(
            "config_flow",
            "options_flow",
            "config_subentries_flow",
            "repair_flow",
        ),
        probatio.Required("user_input"): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def async_start_color_preview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Start or update a reminder color preview."""

    flow_id = msg["flow_id"]
    integration_data = hass.data.setdefault(DOMAIN, {})
    active_flows: set[str] = integration_data.setdefault(_DATA_ACTIVE_FLOWS, set())
    pending_stops: dict[str, Callable[[], None]] = integration_data.setdefault(
        _DATA_PENDING_STOPS, {}
    )

    if cancel_pending_stop := pending_stops.pop(flow_id, None):
        cancel_pending_stop()

    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        connection.send_error(
            msg["id"], "not_configured", "Reminder Light is not configured"
        )
        return

    entry = entries[0]
    user_input = msg["user_input"]
    preview_enabled = user_input.get(CONF_TEST_COLOR, False)
    rgb_color = user_input.get(CONF_REMINDER_COLOR)

    try:
        if preview_enabled and _valid_rgb_color(rgb_color):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: entry.data[CONF_OUTPUT_LIGHT],
                    ATTR_RGB_COLOR: rgb_color,
                    ATTR_BRIGHTNESS: entry.data.get(
                        CONF_BRIGHTNESS, DEFAULT_BRIGHTNESS
                    ),
                },
                blocking=True,
            )
            active_flows.add(flow_id)
        else:
            was_active = flow_id in active_flows
            active_flows.discard(flow_id)
            if was_active and not active_flows:
                await _async_turn_off(hass, entry.data[CONF_OUTPUT_LIGHT])
    except HomeAssistantError as err:
        was_active = flow_id in active_flows
        active_flows.discard(flow_id)
        if was_active and not active_flows:
            with suppress(HomeAssistantError):
                await _async_turn_off(hass, entry.data[CONF_OUTPUT_LIGHT])
        connection.send_error(msg["id"], "preview_failed", str(err))
        return

    connection.send_result(msg["id"])
    connection.send_message(
        websocket_api.event_message(
            msg["id"],
            {
                "state": "on" if flow_id in active_flows else "off",
                "attributes": {},
            },
        )
    )
    connection.subscriptions[msg["id"]] = _preview_cleanup(
        hass,
        flow_id,
        entry.data[CONF_OUTPUT_LIGHT],
        preview_enabled and _valid_rgb_color(rgb_color),
    )


def _valid_rgb_color(value: Any) -> bool:
    """Return whether a live form value is a usable RGB color."""

    return (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(channel, int) and 0 <= channel <= 255 for channel in value)
    )


@callback
def _preview_cleanup(
    hass: HomeAssistant,
    flow_id: str,
    output_light: str,
    preview_active: bool,
) -> Callable[[], None]:
    """Return a subscription cleanup that turns off abandoned previews."""

    @callback
    def async_cleanup() -> None:
        if not preview_active:
            return

        integration_data = hass.data.setdefault(DOMAIN, {})
        pending_stops: dict[str, Callable[[], None]] = integration_data.setdefault(
            _DATA_PENDING_STOPS, {}
        )
        if cancel_pending_stop := pending_stops.pop(flow_id, None):
            cancel_pending_stop()

        @callback
        def async_stop_preview(_now: Any) -> None:
            active_flows: set[str] = integration_data.setdefault(
                _DATA_ACTIVE_FLOWS, set()
            )
            active_flows.discard(flow_id)
            pending_stops.pop(flow_id, None)
            if not active_flows:
                hass.async_create_task(_async_turn_off(hass, output_light))

        pending_stops[flow_id] = async_call_later(
            hass, _PREVIEW_OFF_DELAY, async_stop_preview
        )

    return async_cleanup


async def _async_turn_off(hass: HomeAssistant, output_light: str) -> None:
    """Turn off the shared reminder light."""

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: output_light},
        blocking=True,
    )
