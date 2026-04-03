"""Basics step — schema, validation, and apply for profile identity and targets."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.selector import (
    DeviceSelector,
    DeviceSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)
import voluptuous as vol

from ....const import DEFAULT_GROUP, DEFAULT_TAG
from ....enums import Provider
from ...helpers import humanized_options, notify_service_selector, profile_title

if TYPE_CHECKING:
    from ..context import FlowContext

_PROVIDER_OPTIONS = ["apple", "android", "cross_platform", "android_tv"]
_PASS_IDENTITY = 1
_PASS_TARGETS = 2


def build_basics_schema(
    draft: dict[str, Any],
    ctx: FlowContext,
    *,
    pass_number: int,
) -> vol.Schema:
    """Build the basics form schema.

    pass_number=1: identity + provider fields
    pass_number=2: identity (read-only if reconfiguring) + target + tag/group fields
    """
    schema_dict: dict[Any, Any] = {}

    if ctx.is_reconfiguring:
        schema_dict[vol.Required("name", default=draft["name"])] = TextSelector(
            TextSelectorConfig(read_only=True)
        )
        schema_dict[vol.Required("cameras", default=draft["cameras"])] = SelectSelector(
            SelectSelectorConfig(
                options=humanized_options(ctx.available_cameras),
                multiple=True,
                mode=SelectSelectorMode.LIST,
                read_only=True,
            )
        )
        schema_dict[vol.Required("provider", default=draft["provider"])] = SelectSelector(
            SelectSelectorConfig(
                options=_PROVIDER_OPTIONS,
                translation_key="provider",
                mode=SelectSelectorMode.DROPDOWN,
                read_only=True,
            )
        )
    else:
        schema_dict[vol.Required("name")] = TextSelector()
        schema_dict[vol.Required("cameras")] = SelectSelector(
            SelectSelectorConfig(
                options=humanized_options(ctx.available_cameras),
                multiple=True,
                mode=SelectSelectorMode.LIST,
            )
        )
        schema_dict[vol.Required("provider", default=Provider.APPLE)] = SelectSelector(
            SelectSelectorConfig(
                options=_PROVIDER_OPTIONS,
                translation_key="provider",
                mode=SelectSelectorMode.DROPDOWN,
            )
        )

    if pass_number == _PASS_TARGETS:
        provider = draft.get("provider", Provider.APPLE)
        if provider in (Provider.APPLE, Provider.ANDROID):
            schema_dict[vol.Optional("notify_device")] = DeviceSelector(
                DeviceSelectorConfig(integration="mobile_app")
            )
        schema_dict[vol.Optional("notify_service")] = notify_service_selector(ctx.hass)
        if provider != Provider.ANDROID_TV:
            schema_dict[vol.Optional("tag", default=DEFAULT_TAG)] = TextSelector()
            schema_dict[vol.Optional("group", default=DEFAULT_GROUP)] = TextSelector()

    return vol.Schema(schema_dict)


def build_basics_suggested(draft: dict[str, Any]) -> dict[str, Any]:
    """Build suggested values dict for the basics form."""
    suggested = dict(draft)
    suggested.setdefault("tag", DEFAULT_TAG)
    suggested.setdefault("group", DEFAULT_GROUP)
    return suggested


def validate_basics_input(
    draft: dict[str, Any],
    user_input: dict[str, Any],
    ctx: FlowContext,
    *,
    pass_number: int,
    has_duplicate_title: Callable[[str], bool],
) -> dict[str, str]:
    """Validate basics step input. Returns error dict (empty = valid)."""
    errors: dict[str, str] = {}

    if pass_number == _PASS_IDENTITY:
        name = user_input["name"].strip()
        cameras = sorted(user_input["cameras"])
        missing = [c for c in cameras if c not in ctx.available_cameras]
        if missing and not ctx.is_reconfiguring:
            errors["cameras"] = "camera_not_found"
        if not errors and has_duplicate_title(profile_title(cameras, name)):
            errors["name"] = "profile_name_duplicate"
    else:
        provider = draft.get("provider", Provider.APPLE)
        has_device = bool(user_input.get("notify_device"))
        has_service = bool((user_input.get("notify_service") or "").strip())

        if provider in (Provider.CROSS_PLATFORM, Provider.ANDROID_TV):
            if not has_service:
                errors["notify_service"] = "notify_service_required"
            elif provider == Provider.ANDROID_TV and user_input[
                "notify_service"
            ].strip().startswith("notify.mobile_app_"):
                errors["notify_service"] = "tv_notify_service_invalid"
        elif has_device and has_service:
            errors["notify_service"] = "notify_target_exclusive"
        elif not has_device and not has_service:
            errors["notify_device"] = "notify_target_required"

    return errors


def apply_basics_input(
    draft: dict[str, Any],
    user_input: dict[str, Any],
    ctx: FlowContext,
    *,
    pass_number: int,
) -> None:
    """Apply basics input to draft data."""
    if pass_number == _PASS_IDENTITY:
        draft["name"] = user_input["name"].strip()
        draft["cameras"] = sorted(user_input["cameras"])
        draft["provider"] = user_input["provider"]
    else:
        has_device = bool(user_input.get("notify_device"))
        if has_device:
            draft["notify_device"] = user_input["notify_device"]
            draft.pop("notify_service", None)
        else:
            draft["notify_service"] = user_input["notify_service"].strip()
            draft.pop("notify_device", None)
        if draft.get("provider") != Provider.ANDROID_TV:
            draft["tag"] = (user_input.get("tag") or DEFAULT_TAG).strip() or DEFAULT_TAG
            draft["group"] = (user_input.get("group") or DEFAULT_GROUP).strip() or DEFAULT_GROUP
        else:
            draft.pop("tag", None)
            draft.pop("group", None)
