"""Button entities for Notifications for Frigate."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .const import SILENCE_DATETIMES_KEY, STATS_SENSOR_KEY
from .data import get_integration_subentry_id, iter_profile_subentries, profile_common_fields
from .entity_base import FrigateNotificationsIntegrationEntity, FrigateNotificationsProfileEntity

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
    """Set up button entities from config entry."""
    async_add_entities(
        [FrigateNotificationsResetStatsButton(entry)],
        config_subentry_id=get_integration_subentry_id(entry),
    )

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
        provider: str,
    ) -> None:
        """Initialize silence button."""
        super().__init__(hass, entry, subentry_id, cameras, profile_name, provider=provider)
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_silence"
        self._attr_name = "Silence"

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
        provider: str,
    ) -> None:
        """Initialize clear-silence button."""
        super().__init__(hass, entry, subentry_id, cameras, profile_name, provider=provider)
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_clear_silence"
        self._attr_name = "Clear silence"

    async def async_press(self) -> None:
        """Clear silence on the profile's datetime entity."""
        silence_map = self.hass.data.get(SILENCE_DATETIMES_KEY, {})
        dt_entity = silence_map.get(self._subentry_id)
        if dt_entity is not None:
            dt_entity.clear()
        else:
            _LOGGER.warning("Silence datetime entity not found for profile %s", self._subentry_id)


class FrigateNotificationsResetStatsButton(FrigateNotificationsIntegrationEntity, ButtonEntity):
    """Button to reset the notifications-sent counter to zero."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "reset_stats"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize reset-stats button."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_reset_stats"
        self._attr_name = "Reset stats"

    async def async_press(self) -> None:
        """Reset the stats sensor for this config entry."""
        stats_map = self.hass.data.get(STATS_SENSOR_KEY, {})
        sensor = stats_map.get(self._entry.entry_id)
        if sensor is not None:
            sensor.reset()
        else:
            _LOGGER.warning("Stats sensor not found for entry %s", self._entry.entry_id)
