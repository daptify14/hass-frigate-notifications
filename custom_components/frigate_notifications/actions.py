"""Notification action listener for Notifications for Frigate."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .const import DOMAIN
from .data import find_entry_for_profile
from .enums import Lifecycle, Phase
from .message_builder import build_context

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant

    from .data import FrigateNotificationsConfigEntry, ProfileRuntime
    from .dispatcher import NotificationDispatcher
    from .models import Review

_LOGGER = logging.getLogger(__name__)

_SILENCE_PREFIX = f"silence-{DOMAIN}:profile:"
_CUSTOM_PREFIX = f"custom-{DOMAIN}:profile:"


def setup_action_listener(
    hass: HomeAssistant,
    entry: FrigateNotificationsConfigEntry,
    dispatcher: NotificationDispatcher,
) -> CALLBACK_TYPE:
    """Listen for mobile_app notification action events and route them."""

    async def _handle_action(event: Event) -> None:
        action = event.data.get("action", "")

        # Silence action: silence-frigate_notifications:profile:{profile_id}
        if action.startswith(_SILENCE_PREFIX):
            profile_id = action[len(_SILENCE_PREFIX) :]
            matched_entry = find_entry_for_profile(hass, profile_id)
            dt_entity = (
                matched_entry.runtime_data.silence_datetimes.get(profile_id)
                if matched_entry is not None
                else None
            )
            if dt_entity is not None:
                dt_entity.activate()
                _LOGGER.debug("Silence activated via action for profile %s", profile_id)
            else:
                _LOGGER.warning("Silence action for unknown profile %s", profile_id)
            return

        if action.startswith(_CUSTOM_PREFIX):
            parsed_action = _parse_custom_action(action)
            if parsed_action is None:
                _LOGGER.debug("Malformed custom action: %s", action)
                return
            profile_id, review_id, action_camera = parsed_action

            from .dispatcher import execute_custom_actions

            profile = dispatcher.get_profile(profile_id)
            if profile is None:
                _LOGGER.debug("Custom action for unknown profile %s", profile_id)
                return

            if not profile.on_button_action:
                return

            review = entry.runtime_data.processor.get_review(review_id) if review_id else None
            if review is None:
                run_vars = {
                    "camera": profile.cameras[0] if len(profile.cameras) == 1 else action_camera,
                    "profile_id": profile.profile_id,
                    "profile_name": profile.name,
                }
                if review_id:
                    _LOGGER.debug(
                        "Review %s expired for button press on profile %s",
                        review_id[:25],
                        profile_id,
                    )
            else:
                run_vars = _build_button_action_run_vars(
                    hass, profile, review, dispatcher.global_zone_aliases
                )

            await execute_custom_actions(
                hass,
                profile.on_button_action,
                run_vars,
                profile.name,
            )

    return hass.bus.async_listen("mobile_app_notification_action", _handle_action)


def _parse_custom_action(action: str) -> tuple[str, str, str] | None:
    """Parse a custom action token."""
    remainder = action[len(_CUSTOM_PREFIX) :]
    try:
        profile_id, review_part = remainder.split(":review:", 1)
        review_id, camera = review_part.split(":camera:", 1)
    except ValueError:
        return None

    return (profile_id, review_id, camera)


def _build_button_action_run_vars(
    hass: HomeAssistant,
    profile: ProfileRuntime,
    review: Review,
    global_zone_aliases: dict[str, dict[str, str]],
) -> dict[str, object]:
    """Build button-action variables from the cached review context."""
    phase, lifecycle = _infer_review_phase(review)
    run_vars = build_context(
        review, profile, phase, lifecycle, hass=hass, global_zone_aliases=global_zone_aliases
    )
    run_vars["profile_id"] = profile.profile_id
    run_vars["profile_name"] = profile.name
    return run_vars


def _infer_review_phase(review: Review) -> tuple[Phase, Lifecycle]:
    """Infer the current review phase from cached review state."""
    if review.genai is not None:
        return (Phase.GENAI, Lifecycle.GENAI)
    if review.end_time is not None:
        return (Phase.END, Lifecycle.END)
    if review.before_objects or review.before_sub_labels or review.before_zones:
        return (Phase.UPDATE, Lifecycle.UPDATE)
    return (Phase.INITIAL, Lifecycle.NEW)
