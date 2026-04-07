"""Delivery step — schema, validation, and apply for per-phase delivery and rate limiting."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    TextSelector,
)
import voluptuous as vol

from ....enums import Provider
from ...helpers import (
    DELAY_SELECTOR,
    IMPORTANCE_SELECTOR,
    INTERRUPTION_SELECTOR,
    PRIORITY_SELECTOR,
    SILENCE_SELECTOR,
    TTL_SELECTOR,
    URGENCY_SELECTOR,
    VOLUME_SELECTOR,
    normalize_interruption_level,
    tv_overlay_delivery_fields,
)
from ..context import PROFILE_PHASE_DEFAULTS, PROFILE_PHASE_ORDER

if TYPE_CHECKING:
    from ..context import FlowContext

_TV_OVERLAY_KEYS = (
    "tv_fontsize",
    "tv_position",
    "tv_duration",
    "tv_transparency",
    "tv_interrupt",
    "tv_timeout",
    "tv_color",
)

_ANDROID_KEYS = (
    "android_channel",
    "android_sticky",
    "android_persistent",
    "android_auto",
    "android_color",
)


def build_delivery_schema(draft: dict[str, Any], ctx: FlowContext) -> vol.Schema:
    """Build the delivery step form schema."""
    caps = ctx.capabilities
    enabled = ctx.enabled_phases
    provider = ctx.provider

    schema_dict: dict[Any, Any] = {}
    for phase_name in enabled:
        defaults = PROFILE_PHASE_DEFAULTS[phase_name]
        phase_data = draft.get("phases", {}).get(phase_name, {})
        fields: dict[Any, Any] = {}
        if caps.delivery_variant == "mobile_app":
            if provider == Provider.APPLE:
                fields[
                    vol.Optional("sound", default=phase_data.get("sound", defaults.delivery.sound))
                ] = TextSelector()
                fields[
                    vol.Optional(
                        "volume",
                        default=int(phase_data.get("volume", defaults.delivery.volume) * 100),
                    )
                ] = VOLUME_SELECTOR
                fields[
                    vol.Optional(
                        "interruption_level",
                        default=normalize_interruption_level(
                            phase_data.get(
                                "interruption_level", defaults.delivery.interruption_level
                            )
                        ),
                    )
                ] = INTERRUPTION_SELECTOR
            elif provider == Provider.ANDROID:
                fields[
                    vol.Optional(
                        "importance",
                        default=phase_data.get("importance", defaults.delivery.importance),
                    )
                ] = IMPORTANCE_SELECTOR
                fields[
                    vol.Optional(
                        "priority",
                        default=phase_data.get("priority", defaults.delivery.priority),
                    )
                ] = PRIORITY_SELECTOR
                fields[
                    vol.Optional(
                        "ttl",
                        default=phase_data.get("ttl", defaults.delivery.ttl),
                    )
                ] = TTL_SELECTOR
            else:
                urgency_default = phase_data.get("urgency", defaults.delivery.urgency) or "normal"
                fields[vol.Optional("urgency", default=urgency_default)] = URGENCY_SELECTOR
        fields[vol.Optional("delay", default=phase_data.get("delay", defaults.delivery.delay))] = (
            DELAY_SELECTOR
        )
        if caps.delivery_variant == "mobile_app":
            fields[
                vol.Optional(
                    "critical", default=phase_data.get("critical", defaults.delivery.critical)
                )
            ] = BooleanSelector()
        elif caps.delivery_variant == "tv_overlay":
            tv_fields, _tv_sugg = tv_overlay_delivery_fields(phase_data)
            fields.update(tv_fields)
        schema_dict[vol.Optional(f"{phase_name}_delivery")] = section(
            vol.Schema(fields), SectionConfig(collapsed=(phase_name != "initial"))
        )

    rate_fields: dict[Any, Any] = {
        vol.Optional("silence_duration"): SILENCE_SELECTOR,
        vol.Optional("cooldown_override"): NumberSelector(
            NumberSelectorConfig(min=0, max=3600, step=1, unit_of_measurement="seconds")
        ),
    }
    if caps.supports_alert_once:
        rate_fields[vol.Optional("alert_once")] = BooleanSelector()
    schema_dict[vol.Optional("rate_limiting")] = section(
        vol.Schema(rate_fields), SectionConfig(collapsed=True)
    )

    if draft.get("provider") in (Provider.ANDROID, Provider.CROSS_PLATFORM):
        schema_dict.update(_build_android_delivery_schema(draft))

    return vol.Schema(schema_dict)


def build_delivery_suggested(draft: dict[str, Any], ctx: FlowContext) -> dict[str, Any]:
    """Build suggested values for delivery form."""
    caps = ctx.capabilities
    suggested: dict[str, Any] = {}

    rate_suggested: dict[str, Any] = {}
    if "silence_duration" in draft:
        rate_suggested["silence_duration"] = draft["silence_duration"]
    if "cooldown_override" in draft:
        rate_suggested["cooldown_override"] = draft["cooldown_override"]
    if caps.supports_alert_once:
        rate_suggested["alert_once"] = draft.get("alert_once", False)
    if rate_suggested:
        suggested["rate_limiting"] = rate_suggested

    return suggested


def validate_delivery_input(
    draft: dict[str, Any], user_input: dict[str, Any], ctx: FlowContext
) -> dict[str, str]:
    """Validate delivery step input. Returns error dict (empty = valid)."""
    return {}


def apply_delivery_input(
    draft: dict[str, Any], user_input: dict[str, Any], ctx: FlowContext
) -> None:
    """Apply delivery input to draft data."""
    _submit_delivery_phases(draft, user_input)
    _submit_rate_limiting(draft, user_input)
    _submit_android_delivery(draft, user_input)


def _build_android_delivery_schema(data: dict) -> dict[Any, Any]:
    """Build schema fields for profile-level Android/mobile delivery options."""
    return {
        vol.Optional("android_delivery"): section(
            vol.Schema(
                {
                    vol.Optional(
                        "android_channel", default=data.get("android_channel", "frigate")
                    ): TextSelector(),
                    vol.Optional(
                        "android_sticky", default=data.get("android_sticky", False)
                    ): BooleanSelector(),
                    vol.Optional(
                        "android_persistent", default=data.get("android_persistent", False)
                    ): BooleanSelector(),
                    vol.Optional(
                        "android_auto", default=data.get("android_auto", False)
                    ): BooleanSelector(),
                    vol.Optional(
                        "android_color", default=data.get("android_color", "")
                    ): TextSelector(),
                }
            ),
            SectionConfig(collapsed=True),
        )
    }


def _submit_delivery_phases(data: dict, user_input: dict) -> None:
    """Extract delivery fields from user_input into data['phases']."""
    for phase_name in PROFILE_PHASE_ORDER:
        phase_sec = user_input.get(f"{phase_name}_delivery", {})
        if not phase_sec:
            continue
        phases = data.setdefault("phases", {})
        phase = dict(phases.get(phase_name, {}))
        for key in ("sound", "critical", "delay", "importance", "priority", "urgency"):
            if key in phase_sec:
                phase[key] = phase_sec[key]
        if "volume" in phase_sec:
            phase["volume"] = float(phase_sec["volume"]) / 100.0
        if "interruption_level" in phase_sec:
            phase["interruption_level"] = normalize_interruption_level(
                phase_sec["interruption_level"]
            )
        if "ttl" in phase_sec:
            phase["ttl"] = int(phase_sec["ttl"])
        for tv_key in _TV_OVERLAY_KEYS:
            if tv_key in phase_sec:
                phase[tv_key] = phase_sec[tv_key]
        phases[phase_name] = phase


def _submit_rate_limiting(data: dict, user_input: dict) -> None:
    """Extract rate limiting fields from user_input."""
    rate_sec = user_input.get("rate_limiting", {})
    silence = rate_sec.get("silence_duration")
    if silence is not None:
        data["silence_duration"] = silence
    else:
        data.pop("silence_duration", None)
    cooldown = rate_sec.get("cooldown_override")
    if cooldown is not None:
        data["cooldown_override"] = int(cooldown)
    else:
        data.pop("cooldown_override", None)
    if rate_sec.get("alert_once", False):
        data["alert_once"] = True
    else:
        data.pop("alert_once", None)


def _submit_android_delivery(data: dict, user_input: dict) -> None:
    """Extract android delivery config from user_input."""
    android_sec = user_input.get("android_delivery", {})
    if android_sec:
        for key in _ANDROID_KEYS:
            val = android_sec.get(key)
            if val is not None:
                data[key] = val
