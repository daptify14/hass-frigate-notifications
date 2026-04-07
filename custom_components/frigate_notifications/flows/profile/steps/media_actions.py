"""Media/actions step — schema, validation, and apply for attachments and action presets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers.selector import (
    ActionSelector,
    BooleanSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import voluptuous as vol

from ....const import VALID_TV_ATTACHMENTS
from ...helpers import ATTACHMENT_SELECTOR, TV_ATTACHMENT_SELECTOR, video_selector
from ..context import PROFILE_PHASE_DEFAULTS, PROFILE_PHASE_ORDER

if TYPE_CHECKING:
    from ..context import FlowContext


def build_media_actions_schema(draft: dict[str, Any], ctx: FlowContext) -> vol.Schema:
    """Build the media/actions step form schema."""
    caps = ctx.capabilities
    enabled = ctx.enabled_phases

    schema_dict: dict[Any, Any] = {}
    for phase_name in enabled:
        defaults = PROFILE_PHASE_DEFAULTS[phase_name]
        phase_data = draft.get("phases", {}).get(phase_name, {})
        attachment = phase_data.get("attachment", defaults.media.attachment)
        if caps.media_variant == "android_tv" and attachment not in VALID_TV_ATTACHMENTS:
            attachment = "snapshot_cropped"
        att_selector = (
            TV_ATTACHMENT_SELECTOR if caps.media_variant == "android_tv" else ATTACHMENT_SELECTOR
        )
        fields: dict[Any, Any] = {
            vol.Optional("attachment", default=attachment): att_selector,
        }
        if caps.supports_video:
            fields[vol.Optional("video", default=phase_data.get("video", defaults.media.video))] = (
                video_selector(ctx.provider)
            )
        if phase_name != "initial":
            fields[
                vol.Optional(
                    "use_latest_detection",
                    default=phase_data.get(
                        "use_latest_detection", defaults.media.use_latest_detection
                    ),
                )
            ] = BooleanSelector()
        schema_dict[vol.Optional(f"{phase_name}_media")] = section(
            vol.Schema(fields), SectionConfig(collapsed=(phase_name != "initial"))
        )

    if caps.supports_custom_actions:
        custom_fields: dict[Any, Any] = {
            vol.Optional(f"{pn}_custom_actions"): ActionSelector() for pn in enabled
        }
        schema_dict[vol.Optional("custom_actions")] = section(
            vol.Schema(custom_fields), SectionConfig(collapsed=True)
        )

    if caps.supports_action_presets:
        schema_dict.update(_build_action_preset_schema(draft))

    return vol.Schema(schema_dict)


def build_media_actions_suggested(draft: dict[str, Any], ctx: FlowContext) -> dict[str, Any]:
    """Build suggested values for media/actions form."""
    enabled = ctx.enabled_phases
    suggested: dict[str, Any] = {}

    custom_suggested: dict[str, Any] = {}
    for pn in enabled:
        phase_actions = draft.get("phases", {}).get(pn, {}).get("custom_actions")
        if phase_actions is not None:
            custom_suggested[f"{pn}_custom_actions"] = phase_actions
    if custom_suggested:
        suggested["custom_actions"] = custom_suggested
    if "on_button_action" in draft:
        suggested["on_button_action_section"] = {
            "on_button_action": draft["on_button_action"],
        }

    return suggested


def validate_media_actions_input(
    draft: dict[str, Any], user_input: dict[str, Any], ctx: FlowContext
) -> dict[str, str]:
    """Validate media/actions step input. Returns error dict (empty = valid)."""
    return {}


def apply_media_actions_input(
    draft: dict[str, Any], user_input: dict[str, Any], ctx: FlowContext
) -> None:
    """Apply media/actions input to draft data."""
    _submit_media_phases(draft, user_input)
    _submit_custom_actions(draft, user_input)
    _submit_action_presets(draft, user_input)


def _build_action_preset_schema(data: dict) -> dict[Any, Any]:
    """Build schema fields for tap action and action buttons."""
    from ....action_presets import (
        DEFAULT_PRESET_IDS,
        PRESET_OPTIONS,
        TAP_ACTION_OPTIONS,
        preset_select_options,
    )

    result: dict[Any, Any] = {}
    tap_options = preset_select_options(TAP_ACTION_OPTIONS)
    action_options = preset_select_options(PRESET_OPTIONS)

    current_tap = data.get("tap_action", {})
    tap_default = current_tap.get("preset", "view_clip")
    result[vol.Optional("tap_action")] = section(
        vol.Schema(
            {
                vol.Optional("tap_preset", default=tap_default): SelectSelector(
                    SelectSelectorConfig(options=tap_options, mode=SelectSelectorMode.DROPDOWN)
                ),
            }
        ),
        SectionConfig(collapsed=True),
    )

    action_config = data.get("action_config", [])
    action_defaults = ["none", "none", "none"]
    if "action_config" not in data:
        action_defaults[: len(DEFAULT_PRESET_IDS)] = list(DEFAULT_PRESET_IDS)
    for i in range(3):
        if i < len(action_config):
            action_defaults[i] = action_config[i].get("preset", "none")
    result[vol.Optional("actions_config")] = section(
        vol.Schema(
            {
                vol.Optional(f"action_{i + 1}", default=action_defaults[i]): SelectSelector(
                    SelectSelectorConfig(options=action_options, mode=SelectSelectorMode.DROPDOWN)
                )
                for i in range(3)
            }
        ),
        SectionConfig(collapsed=True),
    )

    result[vol.Optional("on_button_action_section")] = section(
        vol.Schema({vol.Optional("on_button_action"): ActionSelector()}),
        SectionConfig(collapsed=True),
    )
    return result


def _submit_media_phases(data: dict, user_input: dict) -> None:
    """Extract media fields from user_input into data['phases']."""
    for phase_name in PROFILE_PHASE_ORDER:
        phase_sec = user_input.get(f"{phase_name}_media", {})
        if not phase_sec:
            continue
        phases = data.setdefault("phases", {})
        phase = dict(phases.get(phase_name, {}))
        if "attachment" in phase_sec:
            phase["attachment"] = phase_sec["attachment"]
        if "video" in phase_sec:
            phase["video"] = phase_sec["video"]
        if "use_latest_detection" in phase_sec:
            phase["use_latest_detection"] = phase_sec["use_latest_detection"]
        phases[phase_name] = phase


def _submit_custom_actions(data: dict, user_input: dict) -> None:
    """Extract custom actions per phase from user_input."""
    custom_sec = user_input.get("custom_actions", {})
    for phase_name in PROFILE_PHASE_ORDER:
        custom = custom_sec.get(f"{phase_name}_custom_actions")
        phases = data.setdefault("phases", {})
        phase = dict(phases.get(phase_name, {}))
        if custom:
            phase["custom_actions"] = custom
        else:
            phase.pop("custom_actions", None)
        phases[phase_name] = phase


def _submit_action_presets(data: dict, user_input: dict) -> None:
    """Extract tap action and button presets from user_input."""
    if "tap_action" in user_input:
        tap_sec = user_input.get("tap_action", {})
        data["tap_action"] = {"preset": tap_sec.get("tap_preset", "view_clip")}

    if "actions_config" in user_input:
        actions_sec = user_input.get("actions_config", {})
        action_config: list[dict[str, Any]] = []
        for key in ("action_1", "action_2", "action_3"):
            preset_id = actions_sec.get(key)
            if preset_id and preset_id != "none":
                action_config.append({"preset": preset_id})
        data["action_config"] = action_config

    button_sec = user_input.get("on_button_action_section", {})
    button_action = button_sec.get("on_button_action")
    if button_action:
        data["on_button_action"] = button_action
    else:
        data.pop("on_button_action", None)
