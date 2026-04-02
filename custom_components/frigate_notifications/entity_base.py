"""Base entity classes for Notifications for Frigate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, FRIGATE_DOMAIN
from .data import (
    get_frigate_camera_device,
    get_frigate_camera_identifier,
    get_profile_device_identifiers,
    get_profile_device_name,
)
from .enums import Provider

_PROVIDER_MODEL: dict[str, str] = {
    Provider.APPLE: "Apple Mobile Profile",
    Provider.ANDROID: "Android Mobile Profile",
    Provider.CROSS_PLATFORM: "Cross-Platform Mobile Profile",
    Provider.ANDROID_TV: "Android TV Profile",
}

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


class FrigateNotificationsIntegrationEntity(Entity):
    """Base entity for integration-level (service) devices."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize integration-level entity."""
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="FN",
            manufacturer="Notifications for Frigate",
            entry_type=DeviceEntryType.SERVICE,
        )


class FrigateNotificationsProfileEntity(Entity):
    """Base entity that groups profile entities onto a child service device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry_id: str,
        cameras: tuple[str, ...],
        profile_name: str,
        provider: str = Provider.APPLE,
    ) -> None:
        """Initialize profile-level entity."""
        self._entry = entry
        self._subentry_id = subentry_id
        self._cameras = cameras
        self._profile_name = profile_name
        self._frigate_entry_id = entry.data["frigate_entry_id"]
        self._profile_device_name = get_profile_device_name(profile_name)
        self._device_model = _PROVIDER_MODEL.get(provider, "Notification Profile")

        device_info: DeviceInfo = DeviceInfo(
            identifiers=get_profile_device_identifiers(entry.entry_id, subentry_id),
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Notifications for Frigate",
            model=self._device_model,
            name=self._profile_device_name,
        )
        if self._frigate_entry_id:
            if len(cameras) > 1:
                # Multi-camera: link to Frigate server device
                device_info["via_device"] = (FRIGATE_DOMAIN, self._frigate_entry_id)
            else:
                frigate_dev = get_frigate_camera_device(hass, self._frigate_entry_id, cameras[0])
                if frigate_dev is not None:
                    device_info["via_device"] = get_frigate_camera_identifier(
                        self._frigate_entry_id, cameras[0]
                    )
        self._attr_device_info = device_info

    async def async_added_to_hass(self) -> None:
        """Ensure the profile device metadata stays in sync on startup."""
        await super().async_added_to_hass()
        await self._async_reconcile_profile_device()

    async def _async_reconcile_profile_device(self) -> None:
        """Keep the child device metadata and parent link in sync on reloads."""
        device_id = None
        if self.registry_entry is not None:
            device_id = self.registry_entry.device_id
        elif self.device_entry is not None:
            device_id = self.device_entry.id

        if device_id is None:
            return

        dev_reg = dr.async_get(self.hass)
        device = dev_reg.async_get(device_id)
        if device is None:
            return

        if self._frigate_entry_id:
            if len(self._cameras) > 1:
                # Multi-camera: resolve Frigate server device
                parent_device = dev_reg.async_get_device(
                    identifiers={(FRIGATE_DOMAIN, self._frigate_entry_id)}
                )
            else:
                parent_device = get_frigate_camera_device(
                    self.hass, self._frigate_entry_id, self._cameras[0]
                )
        else:
            parent_device = None

        name = self._profile_device_name if device.name_by_user is None else device.name
        updated_device = dev_reg.async_update_device(
            device_id,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Notifications for Frigate",
            model=self._device_model,
            name=name,
            via_device_id=parent_device.id if parent_device is not None else None,
        )
        if updated_device is not None:
            self.device_entry = updated_device
