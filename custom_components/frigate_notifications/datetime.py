"""Silence datetime entity for Notifications for Frigate."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import SIGNAL_SILENCE_STATE, SILENCE_DATETIMES_KEY
from .data import iter_profile_subentries, profile_common_fields
from .entity_base import FrigateNotificationsProfileEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up silence datetime entities from config entry."""
    for subentry in iter_profile_subentries(entry):
        fields = profile_common_fields(subentry)
        async_add_entities(
            [
                FrigateNotificationsSilenceDateTime(
                    hass,
                    entry,
                    **fields,
                    silence_duration=int(
                        subentry.data.get("silence_duration")
                        or entry.options.get("silence_duration", 30)
                    ),
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


class FrigateNotificationsSilenceDateTime(
    FrigateNotificationsProfileEntity, DateTimeEntity, RestoreEntity
):
    """DateTime entity representing when a profile's silence period expires."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "silenced_until"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry_id: str,
        *,
        cameras: tuple[str, ...],
        profile_name: str,
        provider: str,
        silence_duration: int,
    ) -> None:
        """Initialize silence datetime entity."""
        super().__init__(hass, entry, subentry_id, cameras, profile_name, provider=provider)
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_silenced_until"
        self._silence_duration = silence_duration
        self._cancel_timer: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        """Restore state and register in hass.data for cross-component access."""
        await super().async_added_to_hass()

        hass = self.hass
        hass.data.setdefault(SILENCE_DATETIMES_KEY, {})[self._subentry_id] = self

        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                restored = datetime.fromisoformat(last_state.state)
                if restored > dt_util.utcnow():
                    self._attr_native_value = restored
                    self._schedule_clear(restored)
                else:
                    self._attr_native_value = None
            except (ValueError, TypeError) as err:
                _LOGGER.warning(
                    "Could not restore silence state '%s' for %s: %s",
                    last_state.state,
                    self.entity_id,
                    err,
                )
                self._attr_native_value = None
        else:
            self._attr_native_value = None
        self._signal_state_update()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up timer and hass.data reference."""
        self._cancel_scheduled_timer()
        silence_map = self.hass.data.get(SILENCE_DATETIMES_KEY, {})
        silence_map.pop(self._subentry_id, None)

    async def async_set_value(self, value: datetime) -> None:
        """Set the silence-until datetime."""
        self._cancel_scheduled_timer()
        self._attr_native_value = value
        self.async_write_ha_state()
        self._signal_state_update()
        self._schedule_clear(value)

    def activate(self, duration_minutes: int | None = None) -> None:
        """Activate silence for the given duration (or profile default)."""
        minutes = duration_minutes if duration_minutes is not None else self._silence_duration
        until = dt_util.utcnow() + timedelta(minutes=minutes)
        self._cancel_scheduled_timer()
        self._attr_native_value = until
        self.async_write_ha_state()
        self._signal_state_update()
        self._schedule_clear(until)

    def clear(self) -> None:
        """Clear the silence timer immediately."""
        self._cancel_scheduled_timer()
        self._attr_native_value = None
        self.async_write_ha_state()
        self._signal_state_update()

    def _schedule_clear(self, until: datetime) -> None:
        """Schedule auto-clear when the silence period expires."""
        self._cancel_scheduled_timer()

        @callback
        def _on_expire(_now: datetime) -> None:
            self._cancel_timer = None
            self._attr_native_value = None
            self.async_write_ha_state()
            self._signal_state_update()

        self._cancel_timer = async_track_point_in_utc_time(self.hass, _on_expire, until)

    def _cancel_scheduled_timer(self) -> None:
        """Cancel any pending expiry timer."""
        if self._cancel_timer is not None:
            self._cancel_timer()
            self._cancel_timer = None

    @callback
    def _signal_state_update(self) -> None:
        """Broadcast the current silence deadline for dependent entities."""
        async_dispatcher_send(
            self.hass,
            f"{SIGNAL_SILENCE_STATE}_{self._entry.entry_id}_{self._subentry_id}",
            self._attr_native_value,
        )

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        """Return the default silence duration as an attribute."""
        return {"default_duration_minutes": self._silence_duration}
