"""Content step — schema, validation, and apply for message templates and zone overrides."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers.selector import BooleanSelector
from homeassistant.helpers.template import Template, TemplateError
import voluptuous as vol

from ....const import DOMAIN
from ...helpers import content_selector, get_camera_zones, title_selector, zone_phrase_selector
from ..context import PROFILE_PHASE_DEFAULTS, PROFILE_PHASE_ORDER

if TYPE_CHECKING:
    from ..context import FlowContext


def build_content_schema(draft: dict[str, Any], ctx: FlowContext) -> vol.Schema:
    """Build the content step form schema."""
    template_presets = ctx.hass.data.get(DOMAIN, {}).get("template_presets", {})
    schema_dict: dict[Any, Any] = {
        vol.Optional("title_template", default=draft.get("title_template", "")): title_selector(
            template_presets
        ),
    }

    enable_emojis = ctx.entry.options.get("enable_emojis", True)

    for phase_name in PROFILE_PHASE_ORDER:
        if phase_name == "genai" and not ctx.genai_available:
            continue
        defaults = PROFILE_PHASE_DEFAULTS[phase_name]
        phase_data = draft.get("phases", {}).get(phase_name, {})
        fields: dict[Any, Any] = {
            vol.Optional("enabled", default=phase_data.get("enabled", True)): BooleanSelector(),
            vol.Optional(
                "message_template",
                default=phase_data.get("message_template", defaults.content.message_template),
            ): content_selector(template_presets, phase=phase_name),
            vol.Optional(
                "subtitle_template",
                default=phase_data.get("subtitle_template", defaults.content.subtitle_template),
            ): content_selector(template_presets, phase=phase_name),
        }
        if enable_emojis:
            fields[
                vol.Optional(
                    "emoji_message",
                    default=phase_data.get("emoji_message", defaults.content.emoji_message),
                )
            ] = BooleanSelector()
            fields[
                vol.Optional(
                    "emoji_subtitle",
                    default=phase_data.get("emoji_subtitle", defaults.content.emoji_subtitle),
                )
            ] = BooleanSelector()
        if phase_name == "genai":
            fields[
                vol.Optional(
                    "title_prefix_enabled",
                    default=phase_data.get("title_prefix_enabled", True),
                )
            ] = BooleanSelector()
        schema_dict[vol.Optional(f"{phase_name}_content")] = section(
            vol.Schema(fields), SectionConfig(collapsed=(phase_name != "initial"))
        )

    cameras = draft["cameras"]
    fid = ctx.frigate_entry_id
    camera_zones = get_camera_zones(ctx.hass, fid, cameras[0]) if len(cameras) == 1 else []
    if camera_zones:
        existing_overrides = draft.get("zone_overrides", {})
        zone_fields: dict[Any, Any] = {}
        for zone in camera_zones:
            zone_fields[vol.Optional(zone, default=existing_overrides.get(zone, ""))] = (
                zone_phrase_selector(template_presets)
            )
        schema_dict[vol.Optional("zone_overrides")] = section(
            vol.Schema(zone_fields), SectionConfig(collapsed=True)
        )

    return vol.Schema(schema_dict)


def validate_content_input(
    draft: dict[str, Any], user_input: dict[str, Any], ctx: FlowContext
) -> dict[str, str]:
    """Validate content step input. Returns error dict (empty = valid)."""
    template_id_map: dict[str, str] = ctx.hass.data.get(DOMAIN, {}).get("template_id_map", {})
    candidates: list[str] = []

    title = (user_input.get("title_template") or "").strip()
    if title:
        candidates.append(template_id_map.get(title, title))

    for phase_name in PROFILE_PHASE_ORDER:
        phase_sec = user_input.get(f"{phase_name}_content", {})
        for key in ("message_template", "subtitle_template"):
            val = (phase_sec.get(key) or "").strip()
            if val:
                candidates.append(template_id_map.get(val, val))

    cameras = draft.get("cameras", [])
    fid = ctx.frigate_entry_id
    if len(cameras) == 1:
        zone_sec = user_input.get("zone_overrides", {})
        for zone in get_camera_zones(ctx.hass, fid, cameras[0]):
            val = (zone_sec.get(zone) or "").strip()
            if val:
                candidates.append(val)

    for candidate in candidates:
        try:
            Template(candidate, ctx.hass).ensure_valid()
        except TemplateError:
            return {"base": "invalid_template"}

    return {}


def apply_content_input(
    draft: dict[str, Any], user_input: dict[str, Any], ctx: FlowContext
) -> None:
    """Apply content input to draft data."""
    title_tpl = (user_input.get("title_template") or "").strip()
    if title_tpl:
        draft["title_template"] = title_tpl
    else:
        draft.pop("title_template", None)

    _submit_content_phases(draft, user_input)
    # Drop legacy profile-level prefix text overrides (now global-only).
    draft.pop("title_genai_prefixes", None)

    cameras = draft["cameras"]
    fid = ctx.frigate_entry_id
    if len(cameras) == 1:
        camera_zones = get_camera_zones(ctx.hass, fid, cameras[0])
        zone_sec = user_input.get("zone_overrides", {})
        zone_overrides = {z: v for z in camera_zones if (v := (zone_sec.get(z) or "").strip())}
        if zone_overrides:
            draft["zone_overrides"] = zone_overrides
        else:
            draft.pop("zone_overrides", None)
    else:
        draft.pop("zone_overrides", None)


def _submit_content_phases(data: dict, user_input: dict) -> None:
    """Extract content fields from user_input into data['phases']."""
    for phase_name in PROFILE_PHASE_ORDER:
        phase_sec = user_input.get(f"{phase_name}_content", {})
        if not phase_sec:
            continue
        phases = data.setdefault("phases", {})
        phase = dict(phases.get(phase_name, {}))
        phase["enabled"] = phase_sec.get("enabled", True)
        msg = (phase_sec.get("message_template") or "").strip()
        default_msg = PROFILE_PHASE_DEFAULTS[phase_name].content.message_template
        phase["message_template"] = msg or default_msg
        phase["subtitle_template"] = (phase_sec.get("subtitle_template") or "").strip()
        if "emoji_message" in phase_sec:
            phase["emoji_message"] = phase_sec["emoji_message"]
        if "emoji_subtitle" in phase_sec:
            phase["emoji_subtitle"] = phase_sec["emoji_subtitle"]
        if "title_prefix_enabled" in phase_sec:
            phase["title_prefix_enabled"] = phase_sec["title_prefix_enabled"]
        phases[phase_name] = phase
