"""Service registration for Notifications for Frigate."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import voluptuous as vol

from .const import DOMAIN
from .data import find_entry_for_profile

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

    from .datetime import FrigateNotificationsSilenceDateTime

_LOGGER = logging.getLogger(__name__)

SILENCE_SCHEMA = vol.Schema(
    {
        vol.Required("profile_id"): str,
        vol.Optional("duration"): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
    }
)

CLEAR_SILENCE_SCHEMA = vol.Schema(
    {
        vol.Required("profile_id"): str,
    }
)


def _get_silence_entity(
    hass: HomeAssistant, profile_id: str
) -> FrigateNotificationsSilenceDateTime:
    """Look up the silence datetime entity for a profile, or raise."""
    entry = find_entry_for_profile(hass, profile_id)
    if entry is not None:
        entity = entry.runtime_data.silence_datetimes.get(profile_id)
        if entity is not None:
            return entity
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="profile_not_found",
        translation_placeholders={"profile_id": profile_id},
    )


async def _handle_silence_profile(call: ServiceCall) -> None:
    """Handle the silence_profile service call."""
    hass = call.hass
    profile_id = call.data["profile_id"]
    duration = call.data.get("duration")

    entity = _get_silence_entity(hass, profile_id)
    try:
        entity.activate(duration_minutes=duration)
    except HomeAssistantError as err:
        _LOGGER.exception("Failed to silence profile %s", profile_id)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="silence_failed",
        ) from err


async def _handle_clear_silence(call: ServiceCall) -> None:
    """Handle the clear_silence service call."""
    hass = call.hass
    profile_id = call.data["profile_id"]

    entity = _get_silence_entity(hass, profile_id)
    try:
        entity.clear()
    except HomeAssistantError as err:
        _LOGGER.exception("Failed to clear silence for profile %s", profile_id)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="clear_silence_failed",
        ) from err


def register_services(hass: HomeAssistant) -> None:
    """Register domain-level services (idempotent, called once from async_setup)."""
    if hass.services.has_service(DOMAIN, "silence_profile"):
        return

    hass.services.async_register(
        DOMAIN,
        "silence_profile",
        _handle_silence_profile,
        schema=SILENCE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "clear_silence",
        _handle_clear_silence,
        schema=CLEAR_SILENCE_SCHEMA,
    )
    _LOGGER.debug("Registered %s services: silence_profile, clear_silence", DOMAIN)
