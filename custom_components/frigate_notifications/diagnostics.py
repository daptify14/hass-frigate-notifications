"""Diagnostic data for Notifications for Frigate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import SUBENTRY_TYPE_PROFILE
from .data import get_available_frigate_cameras

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import FrigateNotificationsConfigEntry

REDACT_KEYS = {"base_url", "name", "notify_target", "notify_service", "notify_device"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: FrigateNotificationsConfigEntry,
) -> dict[str, Any]:
    """Return diagnostic data for a config entry."""
    frigate_entry_id = entry.data["frigate_entry_id"]
    cameras = sorted(get_available_frigate_cameras(hass, frigate_entry_id))

    profiles: list[dict[str, Any]] = []
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_PROFILE:
            continue
        profiles.append(
            async_redact_data(
                {"subentry_id": subentry.subentry_id, **dict(subentry.data)},
                REDACT_KEYS,
            )
        )

    mqtt_topic = ""
    if entry.runtime_data is not None:
        mqtt_topic = entry.runtime_data.mqtt_topic

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), REDACT_KEYS),
        },
        "options": async_redact_data(dict(entry.options), REDACT_KEYS),
        "cameras": cameras,
        "profiles": profiles,
        "mqtt": {"topic": mqtt_topic},
    }
