"""Binary sensor entities for Notifications for Frigate."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import SIGNAL_DISPATCH_PROBLEM, SIGNAL_SILENCE_STATE, SILENCE_DATETIMES_KEY
from .data import (
    get_available_frigate_cameras,
    get_integration_subentry_id,
    iter_profile_subentries,
    profile_common_fields,
)
from .entity_base import (
    FrigateNotificationsIntegrationEntity,
    FrigateNotificationsProfileEntity,
)
from .frigate_config import get_frigate_config_view

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .data import FrigateNotificationsConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FrigateNotificationsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensor entities from config entry."""
    mqtt_topic = ""
    if entry.runtime_data is not None:
        mqtt_topic = entry.runtime_data.mqtt_topic
    integration_subentry_id = get_integration_subentry_id(entry)
    integration_entities: list[BinarySensorEntity] = [
        FrigateNotificationsMqttConnectedBinarySensor(entry, mqtt_topic),
    ]

    frigate_entry_id = entry.data["frigate_entry_id"]
    available_cameras = get_available_frigate_cameras(hass, frigate_entry_id)
    integration_entities.extend(
        FrigateNotificationsCameraDiagnosticBinarySensor(entry, cam)
        for cam in sorted(available_cameras)
    )

    async_add_entities(integration_entities, config_subentry_id=integration_subentry_id)

    for subentry in iter_profile_subentries(entry):
        fields = profile_common_fields(subentry)
        async_add_entities(
            [
                FrigateNotificationsSilencedBinarySensor(hass, entry, **fields),
                FrigateNotificationsDispatchProblemBinarySensor(hass, entry, **fields),
            ],
            config_subentry_id=subentry.subentry_id,
        )


class FrigateNotificationsMqttConnectedBinarySensor(
    FrigateNotificationsIntegrationEntity, BinarySensorEntity
):
    """Binary sensor indicating whether MQTT is connected."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "mqtt_connected"

    def __init__(self, entry: ConfigEntry, mqtt_topic: str) -> None:
        """Initialize MQTT connection binary sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_mqtt_connected"
        self._attr_name = "MQTT connected"
        self._mqtt_topic = mqtt_topic
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Check and track MQTT connection status."""
        await super().async_added_to_hass()
        try:
            from homeassistant.components import mqtt

            self._attr_is_on = mqtt.is_connected(self.hass)
            self.async_on_remove(
                mqtt.async_subscribe_connection_status(self.hass, self._handle_connection_status)
            )
        except KeyError:
            self._attr_is_on = False

    @callback
    def _handle_connection_status(self, connected: bool) -> None:
        """Update state when the MQTT client connects or disconnects."""
        if self._attr_is_on != connected:
            self._attr_is_on = connected
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the subscribed topic."""
        return {"subscribed_topic": self._mqtt_topic}


class FrigateNotificationsSilencedBinarySensor(
    FrigateNotificationsProfileEntity, BinarySensorEntity
):
    """Binary sensor indicating whether a profile is currently silenced."""

    _attr_translation_key = "silenced"

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
        """Initialize silence binary sensor."""
        super().__init__(hass, entry, subentry_id, cameras, profile_name, provider=provider)
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_silenced"
        self._attr_name = "Silenced"
        self._attr_is_on = False
        self._cancel_timer: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        """Derive initial state and subscribe to silence updates."""
        await super().async_added_to_hass()
        signal = f"{SIGNAL_SILENCE_STATE}_{self._entry.entry_id}_{self._subentry_id}"
        self.async_on_remove(async_dispatcher_connect(self.hass, signal, self._on_silence_state))

        dt_entity = self.hass.data.get(SILENCE_DATETIMES_KEY, {}).get(self._subentry_id)
        self._update_from_datetime_value(None if dt_entity is None else dt_entity.native_value)

    @callback
    def _on_silence_state(self, silenced_until: datetime | None) -> None:
        """Handle silence deadline updates from the datetime entity."""
        self._update_from_datetime_value(silenced_until)

    def _update_from_datetime_value(self, silenced_until: datetime | None) -> None:
        """Derive silenced state from the datetime entity's current value."""
        self._cancel_expiry_timer()
        if silenced_until is None:
            self._set_silenced(False)
            return
        try:
            now = dt_util.utcnow()
            if silenced_until > now:
                self._set_silenced(True)
                self._schedule_expiry(silenced_until)
            else:
                self._set_silenced(False)
        except (ValueError, TypeError):
            self._set_silenced(False)

    @callback
    def _set_silenced(self, is_silenced: bool) -> None:
        """Update the binary sensor state."""
        if self._attr_is_on != is_silenced:
            self._attr_is_on = is_silenced
            if self.hass and self.enabled:
                self.async_write_ha_state()

    def _schedule_expiry(self, until: datetime) -> None:
        """Schedule state flip when silence expires."""
        self._cancel_expiry_timer()

        @callback
        def _on_expire(_now: datetime) -> None:
            self._cancel_timer = None
            self._set_silenced(False)

        self._cancel_timer = async_track_point_in_utc_time(self.hass, _on_expire, until)

    def _cancel_expiry_timer(self) -> None:
        """Cancel any pending expiry timer."""
        if self._cancel_timer is not None:
            self._cancel_timer()
            self._cancel_timer = None

    async def async_will_remove_from_hass(self) -> None:
        """Clean up timer."""
        self._cancel_expiry_timer()


class FrigateNotificationsCameraDiagnosticBinarySensor(
    FrigateNotificationsIntegrationEntity, BinarySensorEntity
):
    """Per-camera diagnostic: on = camera present in Frigate, attributes show capabilities."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, entry: ConfigEntry, camera: str) -> None:
        """Initialize camera diagnostic binary sensor."""
        super().__init__(entry)
        self._camera = camera
        self._attr_unique_id = f"{entry.entry_id}_camera_{camera}"
        self._attr_name = f"Camera {camera}"

    @property
    def is_on(self) -> bool:
        """Return whether the camera still exists in the linked Frigate config."""
        frigate_entry_id = self._entry.data["frigate_entry_id"]
        available = get_available_frigate_cameras(self.hass, frigate_entry_id)
        return self._camera in available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return camera capability attributes."""
        frigate_entry_id = self._entry.data["frigate_entry_id"]
        config_view = get_frigate_config_view(self.hass, frigate_entry_id)
        genai = (
            config_view.camera_supports_genai(self._camera) if config_view is not None else False
        )
        return {
            "camera": self._camera,
            "genai": genai,
        }


class FrigateNotificationsDispatchProblemBinarySensor(
    FrigateNotificationsProfileEntity, BinarySensorEntity
):
    """Problem sensor: on when the last dispatch attempt for this profile failed."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "dispatch_problem"

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
        """Initialize dispatch problem binary sensor."""
        super().__init__(hass, entry, subentry_id, cameras, profile_name, provider=provider)
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_dispatch_problem"
        self._attr_name = "Dispatch problem"
        self._attr_is_on = False
        self._last_error: str | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to dispatch problem signals."""
        await super().async_added_to_hass()
        signal = f"{SIGNAL_DISPATCH_PROBLEM}_{self._entry.entry_id}_{self._subentry_id}"
        self.async_on_remove(async_dispatcher_connect(self.hass, signal, self._on_dispatch_problem))

    @callback
    def _on_dispatch_problem(self, error_msg: str | None) -> None:
        """Handle dispatch problem signal."""
        is_problem = error_msg is not None
        if self._attr_is_on != is_problem or self._last_error != error_msg:
            self._attr_is_on = is_problem
            self._last_error = error_msg
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return last error details when in problem state."""
        if self._last_error is None:
            return {}
        return {"last_error": self._last_error}
