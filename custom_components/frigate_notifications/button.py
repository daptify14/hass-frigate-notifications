"""Silence/clear button entities for Notifications for Frigate."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .const import SILENCE_DATETIMES_KEY
from .data import iter_profile_subentries, profile_common_fields
from .entity_base import FrigateNotificationsProfileEntity
from .enums import Provider

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
    """Set up silence/clear buttons from config entry."""
    for subentry in iter_profile_subentries(entry):
        fields = profile_common_fields(subentry)
        async_add_entities(
            [
                FrigateNotificationsSilenceButton(hass, entry, **fields),
                FrigateNotificationsClearSilenceButton(hass, entry, **fields),
            ],
            config_subentry_id=subentry.subentry_id,
        )


class FrigateNotificationsSilenceButton(FrigateNotificationsProfileEntity, ButtonEntity):
    """Button to silence a profile for its default duration."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "silence"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry_id: str,
        *,
        cameras: tuple[str, ...],
        profile_name: str,
        provider: str = Provider.APPLE,
    ) -> None:
        """Initialize silence button."""
        super().__init__(hass, entry, subentry_id, cameras, profile_name, provider=provider)
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_silence"
        self._attr_name = "Silence"

    async def async_added_to_hass(self) -> None:
        """Reconcile profile device on startup."""
        await super().async_added_to_hass()

    async def async_press(self) -> None:
        """Activate silence on the profile's datetime entity."""
        silence_map = self.hass.data.get(SILENCE_DATETIMES_KEY, {})
        dt_entity = silence_map.get(self._subentry_id)
        if dt_entity is not None:
            dt_entity.activate()
        else:
            _LOGGER.warning("Silence datetime entity not found for profile %s", self._subentry_id)


class FrigateNotificationsClearSilenceButton(FrigateNotificationsProfileEntity, ButtonEntity):
    """Button to clear a profile's silence timer."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "clear_silence"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry_id: str,
        *,
        cameras: tuple[str, ...],
        profile_name: str,
        provider: str = Provider.APPLE,
    ) -> None:
        """Initialize clear-silence button."""
        super().__init__(hass, entry, subentry_id, cameras, profile_name, provider=provider)
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_clear_silence"
        self._attr_name = "Clear silence"

    async def async_added_to_hass(self) -> None:
        """Reconcile profile device on startup."""
        await super().async_added_to_hass()

    async def async_press(self) -> None:
        """Clear silence on the profile's datetime entity."""
        silence_map = self.hass.data.get(SILENCE_DATETIMES_KEY, {})
        dt_entity = silence_map.get(self._subentry_id)
        if dt_entity is not None:
            dt_entity.clear()
        else:
            _LOGGER.warning("Silence datetime entity not found for profile %s", self._subentry_id)
