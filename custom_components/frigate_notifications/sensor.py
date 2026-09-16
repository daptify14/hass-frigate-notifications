"""Sensor entities for Notifications for Frigate."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, override
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from homeassistant.components.sensor import RestoreSensor, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    LAST_SENT_RECENT_LIMIT,
    LAST_SENT_TEXT_LIMIT,
    SIGNAL_LAST_SENT,
    SIGNAL_STATS,
)
from .data import (
    get_integration_subentry_id,
    isoformat_timestamp,
    iter_profile_subentries,
    profile_common_fields,
)
from .entity_base import (
    FrigateNotificationsIntegrationEntity,
    FrigateNotificationsProfileEntity,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .models import SentNotification
    from .review_history import ReviewRecord

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities from config entry."""
    async_add_entities(
        [
            FrigateNotificationsReviewDebugSensor(entry),
            FrigateNotificationsStatsSensor(entry),
        ],
        config_subentry_id=get_integration_subentry_id(entry),
    )

    for subentry in iter_profile_subentries(entry):
        fields = profile_common_fields(subentry)
        async_add_entities(
            [FrigateNotificationsLastSentSensor(entry, **fields)],
            config_subentry_id=subentry.subentry_id,
        )


def _recent_review_row(record: ReviewRecord) -> dict[str, Any]:
    """Compact attribute row for one retained review."""
    last = record.steps[-1]
    after = last.payload.get("after", {})
    data = after.get("data", {})
    return {
        "review_id": record.review_id,
        "camera": record.camera,
        "started_at": isoformat_timestamp(record.started_at),
        "last_lifecycle": str(last.lifecycle),
        "steps": len(record.steps),
        "truncated": record.truncated,
        "objects": list(data.get("objects", [])),
        "zones": list(data.get("zones", [])),
        "sub_labels": list(data.get("sub_labels", [])),
        "severity": after.get("severity", ""),
    }


class FrigateNotificationsReviewDebugSensor(FrigateNotificationsIntegrationEntity, SensorEntity):
    """Sensor showing the latest review message and the retained recent reviews."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "review_debug"
    _unrecorded_attributes = frozenset({"recent"})

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize review debug sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_review_debug"
        self._attr_native_value: str | None = None
        self._review_attrs: dict[str, Any] = {}

    @override
    async def async_added_to_hass(self) -> None:
        """Register in runtime_data so processor can push updates."""
        await super().async_added_to_hass()
        self._entry.runtime_data.debug_sensor = self

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Clear runtime_data reference."""
        self._entry.runtime_data.debug_sensor = None

    def update_from_review(self, msg_type: str, payload: dict[str, Any]) -> None:
        """Push a review message into the sensor (called by processor callback)."""
        after = payload.get("after", {})
        data = after.get("data", {})
        self._attr_native_value = after.get("id", "")
        self._review_attrs = {
            "review_id": after.get("id", ""),
            "camera": after.get("camera", ""),
            "objects": data.get("objects", []),
            "zones": data.get("zones", []),
            "severity": after.get("severity", ""),
            "detection_count": len(data.get("detections", [])),
            "message_type": msg_type,
        }
        self.async_write_ha_state()

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the latest message attributes plus the retained recent reviews."""
        history = self._entry.runtime_data.review_history
        if history is None:
            return self._review_attrs
        recent = [_recent_review_row(record) for record in history.records()]
        return {**self._review_attrs, "recent": recent}


class FrigateNotificationsStatsSensor(FrigateNotificationsIntegrationEntity, RestoreSensor):
    """Sensor tracking total notifications sent, with per-camera/profile breakdown."""

    _attr_native_unit_of_measurement = "notifications"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_translation_key = "stats"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize notifications-sent counter sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_stats"
        self._attr_native_value: int = 0
        self._by_camera: dict[str, int] = {}
        self._by_profile: dict[str, int] = {}

    @override
    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to stats signal."""
        await super().async_added_to_hass()

        last = await self.async_get_last_sensor_data()
        if last and last.native_value is not None:
            try:
                raw = last.native_value
                self._attr_native_value = int(raw) if isinstance(raw, (str, int, float)) else 0
            except (ValueError, TypeError):
                self._attr_native_value = 0

        last_state = await self.async_get_last_state()
        if last_state:
            attrs = last_state.attributes
            self._by_camera = dict(attrs.get("by_camera", {}))
            self._by_profile = dict(attrs.get("by_profile", {}))

        self._entry.runtime_data.stats_sensor = self

        signal = f"{SIGNAL_STATS}_{self._entry.entry_id}"
        self.async_on_remove(async_dispatcher_connect(self.hass, signal, self._on_stats_signal))

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Clear runtime_data reference."""
        self._entry.runtime_data.stats_sensor = None

    @callback
    def reset(self) -> None:
        """Zero all counters."""
        self._attr_native_value = 0
        self._by_camera = {}
        self._by_profile = {}
        self.async_write_ha_state()

    @callback
    def _on_stats_signal(self, camera: str, profile_name: str) -> None:
        """Increment counters on stats signal from dispatcher."""
        current = self._attr_native_value
        self._attr_native_value = (current if isinstance(current, int) else 0) + 1
        self._by_camera[camera] = self._by_camera.get(camera, 0) + 1
        self._by_profile[profile_name] = self._by_profile.get(profile_name, 0) + 1
        self.async_write_ha_state()

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return per-camera and per-profile counters."""
        return {"by_camera": self._by_camera, "by_profile": self._by_profile}


def _without_token(url: str) -> str:
    """Drop the camera access token from a URL before it is persisted as an attribute."""
    parts = urlsplit(url)
    if not parts.query:
        return url
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if k != "token"])
    return urlunsplit(parts._replace(query=query))


def _sent_attributes(sent: SentNotification) -> dict[str, Any]:
    """Full attribute set for the latest delivered notification."""
    return {
        "sent_at": isoformat_timestamp(sent.sent_at),
        "review_id": sent.review_id,
        "camera": sent.camera,
        "lifecycle": str(sent.lifecycle),
        "phase": str(sent.phase),
        "title": sent.title[:LAST_SENT_TEXT_LIMIT],
        "message": sent.message[:LAST_SENT_TEXT_LIMIT],
        "subtitle": sent.subtitle[:LAST_SENT_TEXT_LIMIT],
        "tag": sent.tag,
        "group": sent.group,
        "click_url": _without_token(sent.click_url),
        "service": sent.service,
        "objects": list(sent.objects),
        "zones": list(sent.zones),
        "sub_labels": list(sent.sub_labels),
        "severity": sent.severity,
    }


class FrigateNotificationsLastSentSensor(FrigateNotificationsProfileEntity, RestoreSensor):
    """Sensor showing the last notification sent for a profile and its recent history."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "last_sent"
    _unrecorded_attributes = frozenset({"recent"})

    def __init__(
        self,
        entry: ConfigEntry,
        subentry_id: str,
        *,
        cameras: tuple[str, ...],
        profile_name: str,
        provider: str,
    ) -> None:
        """Initialize last-sent sensor."""
        super().__init__(entry, subentry_id, cameras, profile_name, provider=provider)
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_last_sent"
        self._attr_native_value: str | None = None
        self._last_sent_attrs: dict[str, Any] = {}
        self._recent: list[dict[str, Any]] = []

    @override
    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to last_sent signal."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            self._attr_native_value = last_state.state
            attrs = dict(last_state.attributes)
            recent = attrs.pop("recent", [])
            self._recent = list(recent) if isinstance(recent, list) else []
            self._last_sent_attrs = attrs

        signal = f"{SIGNAL_LAST_SENT}_{self._entry.entry_id}_{self._subentry_id}"
        self.async_on_remove(async_dispatcher_connect(self.hass, signal, self._on_last_sent_signal))

    @callback
    def _on_last_sent_signal(self, sent: SentNotification) -> None:
        """Update from dispatcher signal."""
        self._attr_native_value = sent.review_id
        self._last_sent_attrs = _sent_attributes(sent)
        row = {
            key: self._last_sent_attrs[key] for key in ("sent_at", "review_id", "phase", "title")
        }
        self._recent = [row, *self._recent][:LAST_SENT_RECENT_LIMIT]
        self.async_write_ha_state()

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return last sent notification details and the recent list."""
        return {**self._last_sent_attrs, "recent": self._recent}
