"""Sensor entities for Notifications for Frigate."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import RestoreSensor, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DEBUG_SENSOR_KEY,
    DOMAIN,
    SIGNAL_LAST_SENT,
    SIGNAL_STATS,
)
from .data import get_integration_subentry_id, iter_profile_subentries, profile_common_fields
from .entity_base import (
    FrigateNotificationsIntegrationEntity,
    FrigateNotificationsProfileEntity,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

_LOGGER = logging.getLogger(__name__)


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
            [FrigateNotificationsLastSentSensor(hass, entry, **fields)],
            config_subentry_id=subentry.subentry_id,
        )


class FrigateNotificationsReviewDebugSensor(FrigateNotificationsIntegrationEntity, SensorEntity):
    """Sensor showing the latest review message for debugging."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "review_debug"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize review debug sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_review_debug"
        self._attr_name = "Review debug"
        self._attr_native_value: str | None = None
        self._review_attrs: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        """Register in hass.data so processor can push updates."""
        await super().async_added_to_hass()
        self.hass.data.setdefault(DOMAIN, {})[f"{DEBUG_SENSOR_KEY}_{self._entry.entry_id}"] = self

    async def async_will_remove_from_hass(self) -> None:
        """Remove hass.data reference."""
        self.hass.data.get(DOMAIN, {}).pop(f"{DEBUG_SENSOR_KEY}_{self._entry.entry_id}", None)

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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return debug attributes."""
        return self._review_attrs


class FrigateNotificationsStatsSensor(FrigateNotificationsIntegrationEntity, RestoreSensor):
    """Sensor tracking total notifications sent, with per-camera/profile breakdown."""

    _attr_native_unit_of_measurement = "notifications"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_translation_key = "stats"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize notifications-sent counter sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_stats"
        self._attr_name = "Notifications sent"
        self._attr_native_value: int = 0
        self._by_camera: dict[str, int] = {}
        self._by_profile: dict[str, int] = {}

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

        signal = f"{SIGNAL_STATS}_{self._entry.entry_id}"
        self.async_on_remove(async_dispatcher_connect(self.hass, signal, self._on_stats_signal))

    @callback
    def _on_stats_signal(self, camera: str, profile_name: str) -> None:
        """Increment counters on stats signal from dispatcher."""
        current = self._attr_native_value
        self._attr_native_value = (current if isinstance(current, int) else 0) + 1
        self._by_camera[camera] = self._by_camera.get(camera, 0) + 1
        self._by_profile[profile_name] = self._by_profile.get(profile_name, 0) + 1
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return per-camera and per-profile counters."""
        return {"by_camera": self._by_camera, "by_profile": self._by_profile}


class FrigateNotificationsLastSentSensor(FrigateNotificationsProfileEntity, RestoreSensor):
    """Sensor showing the last notification sent for a profile."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "last_sent"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry_id: str,
        *,
        cameras: tuple[str, ...],
        profile_name: str,
        provider: str,
    ) -> None:
        """Initialize last-sent sensor."""
        super().__init__(hass, entry, subentry_id, cameras, profile_name, provider=provider)
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_last_sent"
        self._attr_name = "Last sent"
        self._attr_native_value: str | None = None
        self._last_sent_attrs: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to last_sent signal."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            self._attr_native_value = last_state.state
            self._last_sent_attrs = dict(last_state.attributes)

        signal = f"{SIGNAL_LAST_SENT}_{self._entry.entry_id}_{self._subentry_id}"
        self.async_on_remove(async_dispatcher_connect(self.hass, signal, self._on_last_sent_signal))

    @callback
    def _on_last_sent_signal(self, review_id: str, phase: str, title: str, message: str) -> None:
        """Update from dispatcher signal."""
        self._attr_native_value = review_id
        self._last_sent_attrs = {
            "review_id": review_id,
            "phase": phase,
            "title": title,
            "message": message,
        }
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return last sent notification details."""
        return self._last_sent_attrs
