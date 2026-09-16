"""Diagnostic data for Notifications for Frigate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import SUBENTRY_TYPE_PROFILE
from .data import get_available_frigate_cameras

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import FrigateNotificationsConfigEntry
    from .review_history import ReviewHistory

REDACT_KEYS = {
    "base_url",
    "frigate_url",
    "name",
    "notify_target",
    "notify_service",
    "notify_device",
}


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

    mqtt_topic = entry.runtime_data.mqtt_topic
    history = entry.runtime_data.review_history

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
        "review_history": _summarize_history(history) if history is not None else None,
    }


def _summarize_history(history: ReviewHistory) -> list[dict[str, Any]]:
    """Summarize retained reviews without sub-labels or GenAI text."""
    summaries = []
    for record in history.records():
        steps = []
        for step in record.steps:
            data = step.payload.get("after", {}).get("data", {})
            steps.append(
                {
                    "lifecycle": str(step.lifecycle),
                    "received_at": step.received_at,
                    "objects": list(data.get("objects", [])),
                    "zones": list(data.get("zones", [])),
                    "severity": step.payload.get("after", {}).get("severity", ""),
                    "detection_count": len(data.get("detections", [])),
                }
            )
        summaries.append(
            {
                "review_id": record.review_id,
                "camera": record.camera,
                "started_at": record.started_at,
                "truncated": record.truncated,
                "steps": steps,
            }
        )
    return summaries
