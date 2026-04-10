"""Enable/disable switch entity for Notifications for Frigate."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

from .const import ENABLED_SWITCHES_KEY
from .data import iter_profile_subentries, profile_common_fields
from .entity_base import FrigateNotificationsProfileEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up enable/disable switches from config entry."""
    for subentry in iter_profile_subentries(entry):
        fields = profile_common_fields(subentry)
        async_add_entities(
            [FrigateNotificationsSwitch(hass, entry, **fields)],
            config_subentry_id=subentry.subentry_id,
        )


class FrigateNotificationsSwitch(FrigateNotificationsProfileEntity, SwitchEntity, RestoreEntity):
    """Switch entity to enable/disable a notification profile."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "enabled"

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
        """Initialize profile enabled switch."""
        super().__init__(hass, entry, subentry_id, cameras, profile_name, provider=provider)
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_enabled"
        self._attr_name = "Enabled"
        self._attr_is_on = True

    async def async_added_to_hass(self) -> None:
        """Restore state and register in hass.data for cross-component access."""
        await super().async_added_to_hass()
        self.hass.data.setdefault(ENABLED_SWITCHES_KEY, {})[self._subentry_id] = self
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"
        else:
            self._attr_is_on = True

    async def async_will_remove_from_hass(self) -> None:
        """Clean up hass.data reference."""
        switch_map = self.hass.data.get(ENABLED_SWITCHES_KEY, {})
        switch_map.pop(self._subentry_id, None)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the profile."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the profile."""
        self._attr_is_on = False
        self.async_write_ha_state()
