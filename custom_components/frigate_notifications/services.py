"""Service registration for Notifications for Frigate."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import DOMAIN, REVIEW_HISTORY_MAX_REVIEWS
from .data import find_entry_for_profile, isoformat_timestamp, iter_loaded_entries
from .enums import ReplayOutcome
from .replay import ReplayOverrides, ReplayResult, replay_review

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse

    from .data import FrigateNotificationsConfigEntry, ProfileRuntime
    from .datetime import FrigateNotificationsSilenceDateTime
    from .review_history import ReviewHistory, ReviewRecord

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

_REPLAY_FIELDS = {
    vol.Required("entity_id"): cv.entity_id,
    vol.Optional("review_id"): str,
    vol.Optional("run_filters", default=False): bool,
    vol.Optional("title_template", default=""): str,
    vol.Optional("message_template", default=""): str,
    vol.Optional("subtitle_template", default=""): str,
}

PREVIEW_SCHEMA = vol.Schema(
    {
        **_REPLAY_FIELDS,
        vol.Optional("last", default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=REVIEW_HISTORY_MAX_REVIEWS)
        ),
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


def _resolve_profile_entity(
    hass: HomeAssistant, entity_id: str
) -> tuple[FrigateNotificationsConfigEntry, ProfileRuntime]:
    """Map a profile's Enabled switch entity to its entry and profile, or raise."""
    for entry in iter_loaded_entries(hass):
        for profile_id, switch in entry.runtime_data.enabled_switches.items():
            if switch.entity_id != entity_id:
                continue
            profile = entry.runtime_data.dispatcher.get_profile(profile_id)
            if profile is not None:
                return entry, profile
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="profile_not_found",
        translation_placeholders={"profile_id": entity_id},
    )


def _select_records(
    history: ReviewHistory | None, profile: ProfileRuntime, data: dict[str, Any]
) -> list[ReviewRecord]:
    """Pick the retained reviews a call refers to, restricted to the profile's cameras."""
    if history is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="review_history_disabled"
        )
    review_id = data.get("review_id")
    if review_id:
        record = history.get(review_id)
        if record is None or record.camera not in profile.cameras:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="review_not_found",
                translation_placeholders={"review_id": review_id},
            )
        return [record]
    records = history.latest(profile.cameras, data.get("last", 1))
    if not records:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_review_history")
    return list(records)


def _replay_for_call(call: ServiceCall) -> list[ReplayResult]:
    """Resolve the profile and reviews for a replay call and run the replay."""
    entry, profile = _resolve_profile_entity(call.hass, call.data["entity_id"])
    records = _select_records(entry.runtime_data.review_history, profile, call.data)
    dispatcher = entry.runtime_data.dispatcher
    overrides = ReplayOverrides(
        title_template=call.data["title_template"],
        message_template=call.data["message_template"],
        subtitle_template=call.data["subtitle_template"],
    )
    return [
        replay_review(
            call.hass,
            dispatcher.runtime_config,
            dispatcher.filter_chain,
            entry.runtime_data,
            profile,
            record,
            run_filters=call.data["run_filters"],
            overrides=overrides,
        )
        for record in records
    ]


def _serialize_result(result: ReplayResult) -> dict[str, Any]:
    """Turn a replay into plain dicts for an action response."""
    rows = []
    for row in result.rows:
        item: dict[str, Any] = {
            "step": row.step,
            "lifecycle": str(row.lifecycle),
            "received_at": isoformat_timestamp(row.received_at),
            "outcome": str(row.outcome),
        }
        if row.phase is not None:
            item["phase"] = str(row.phase)
        if row.fired_at is not None:
            item["fired_at"] = isoformat_timestamp(row.fired_at)
        if row.detail:
            item["detail"] = row.detail
        if row.outcome is ReplayOutcome.RENDERED and row.rendered and row.notify_call:
            item.update(
                {
                    "title": row.rendered.title,
                    "message": row.rendered.message,
                    "subtitle": row.rendered.subtitle,
                    "tag": row.rendered.tag,
                    "group": row.rendered.group,
                    "click_url": row.rendered.click_url,
                    "service": f"notify.{row.notify_call.service}",
                    "service_data": row.notify_call.service_data,
                }
            )
        rows.append(item)
    record = result.record
    return {
        "review_id": record.review_id,
        "camera": record.camera,
        "started_at": isoformat_timestamp(record.started_at),
        "truncated": record.truncated,
        "rows": rows,
    }


def _build_response(call: ServiceCall, results: list[ReplayResult]) -> ServiceResponse:
    return {
        "filters": "evaluated_now" if call.data["run_filters"] else "none",
        "reviews": [_serialize_result(result) for result in results],
    }


async def _handle_preview_notification(call: ServiceCall) -> ServiceResponse:
    """Handle the preview_notification action."""
    return _build_response(call, _replay_for_call(call))


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
    hass.services.async_register(
        DOMAIN,
        "preview_notification",
        _handle_preview_notification,
        schema=PREVIEW_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    _LOGGER.debug("Registered %s services", DOMAIN)
