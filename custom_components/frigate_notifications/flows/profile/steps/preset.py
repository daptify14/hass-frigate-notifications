"""Preset step — schema, validation, and apply for profile preset selection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)
import voluptuous as vol

from ....const import DOMAIN

if TYPE_CHECKING:
    from ..context import FlowContext

_PRESET_BASE_URL = (
    "https://github.com/daptify14/hass-frigate-notifications"
    "/blob/main/custom_components/frigate_notifications/presets/profiles"
)


def _build_preset_details_markdown(presets: list) -> str:
    """Build a flat list of preset descriptions with source links."""
    blocks: list[str] = []
    for p in presets:
        yaml_url = f"{_PRESET_BASE_URL}/{p.id}.yaml"
        lines = [f"**{p.name}**"]
        if p.description:
            lines.append(p.description)
        lines.append(f"[View preset source]({yaml_url})")
        blocks.append("\n\n".join(lines))
    return "\n\n" + "\n\n---\n\n".join(blocks)


def build_preset_schema(draft: dict[str, Any], ctx: FlowContext) -> vol.Schema:
    """Build the preset selection form schema."""
    profile_presets = ctx.hass.data.get(DOMAIN, {}).get("profile_presets", [])

    preset_options = [
        SelectOptionDict(value=p.id, label=f"{p.name} \u2014 {p.summary}") for p in profile_presets
    ] + [
        SelectOptionDict(value="custom", label="Custom \u2014 start from scratch"),
    ]
    default_preset = profile_presets[0].id if profile_presets else "custom"
    default_name = profile_presets[0].name if profile_presets else "Custom"

    return vol.Schema(
        {
            vol.Required("preset", default=default_preset): SelectSelector(
                SelectSelectorConfig(
                    options=preset_options,
                    mode=SelectSelectorMode.LIST,
                )
            ),
            vol.Optional("preset_info"): section(
                vol.Schema(
                    {
                        vol.Optional("default_preset", default=default_name): TextSelector(
                            TextSelectorConfig(read_only=True)
                        ),
                    }
                ),
                SectionConfig(collapsed=True),
            ),
        }
    )


def validate_preset_input(
    draft: dict[str, Any], user_input: dict[str, Any], ctx: FlowContext
) -> dict[str, str]:
    """Validate preset step input. Returns error dict (empty = valid)."""
    return {}


def apply_preset_input(draft: dict[str, Any], user_input: dict[str, Any], ctx: FlowContext) -> None:
    """Apply preset selection to draft data."""
    profile_presets = ctx.hass.data.get(DOMAIN, {}).get("profile_presets", [])
    preset_id = user_input.get("preset", "custom")

    if preset_id != "custom":
        preset = next((p for p in profile_presets if p.id == preset_id), None)
        if preset is not None:
            draft.update(preset.to_profile_data(genai_available=ctx.genai_available))
            draft["_preset_id"] = preset.id
            draft["_preset_version"] = preset.version


def preset_description_placeholders(ctx: FlowContext) -> dict[str, str]:
    """Build description placeholders for the preset step."""
    profile_presets = ctx.hass.data.get(DOMAIN, {}).get("profile_presets", [])
    return {"preset_details": _build_preset_details_markdown(profile_presets)}
