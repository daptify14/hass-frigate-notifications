"""Named action button presets for notification profiles."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from .const import _CAM, _DET, _FN, _REV
from .enums import Provider, resolved_platform

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.selector import SelectOptionDict

    from .data import ProfileRuntime

_JINJA_ENV = SandboxedEnvironment(undefined=StrictUndefined)
_LOGGER = logging.getLogger(__name__)

ACTION_PRESETS: dict[str, dict[str, str]] = {
    "view_clip": {
        "type": "uri",
        "title": "View Clip",
        "uri_ios": f"{_FN}/{_DET}/{_CAM}/master.m3u8",
        "uri_android": f"{_FN}/{_DET}/{_CAM}/clip.mp4",
        "uri": f"{_FN}/{_DET}/{_CAM}/master.m3u8",
        "icon": "sfsymbols:play.rectangle",
    },
    "view_snapshot": {
        "type": "uri",
        "title": "View Snapshot",
        "uri": f"{_FN}/{_DET}/snapshot.jpg",
        "icon": "sfsymbols:photo",
    },
    "view_gif": {
        "type": "uri",
        "title": "View GIF",
        "uri": f"{_FN}/{_REV}/review_preview.gif",
        "icon": "sfsymbols:photo.on.rectangle",
    },
    "view_stream": {
        "type": "uri",
        "title": "View Live Stream",
        "uri": (
            "{{ base_url }}/api/camera_proxy_stream/camera.{{ camera }}?token={{ access_token }}"
        ),
        "icon": "sfsymbols:video.fill",
    },
    "silence": {
        "type": "silence",
        "title": "Silence Notifications",
    },
    "open_ha_app": {
        "type": "uri",
        "title": "Open HA (App)",
        "uri": "/lovelace",
        "icon": "sfsymbols:house.fill",
    },
    "open_ha_web": {
        "type": "uri",
        "title": "Open HA (Browser)",
        "uri": "{{ base_url }}/lovelace",
        "icon": "sfsymbols:house",
    },
    "open_frigate": {
        "type": "uri",
        "title": "Open Frigate",
        "uri": "{{ frigate_url }}",
        "icon": "sfsymbols:video",
    },
    "custom_action": {
        "type": "event",
        "title": "Custom Action",
        "icon": "sfsymbols:bolt",
    },
    "no_action": {
        "type": "no_action",
        "title": "",
    },
    "none": {
        "type": "none",
        "title": "",
    },
}

DEFAULT_PRESET_IDS = ("view_clip", "view_snapshot", "silence")

PRESET_OPTIONS = [
    "view_clip",
    "view_snapshot",
    "view_gif",
    "view_stream",
    "silence",
    "open_ha_app",
    "open_ha_web",
    "open_frigate",
    "custom_action",
    "no_action",
    "none",
]

TAP_ACTION_OPTIONS = [
    "view_clip",
    "view_snapshot",
    "view_gif",
    "view_stream",
    "open_ha_app",
    "open_ha_web",
    "open_frigate",
    "no_action",
]

_PRESET_LABELS: dict[str, str] = {
    "view_clip": "View Clip",
    "view_snapshot": "View Snapshot",
    "view_gif": "View GIF",
    "view_stream": "View Live Stream",
    "silence": "Silence Notifications",
    "open_ha_app": "Open HA (App)",
    "open_ha_web": "Open HA (Browser)",
    "open_frigate": "Open Frigate",
    "custom_action": "Custom Action",
    "no_action": "No Action (Android)",
    "none": "None (empty slot)",
}


def preset_select_options(preset_ids: list[str]) -> list[SelectOptionDict]:
    """Build SelectOptionDict-compatible options for a list of preset IDs."""
    return [{"value": pid, "label": _PRESET_LABELS.get(pid, pid)} for pid in preset_ids]


def validate_preset_id(preset_id: str, *, field_name: str) -> None:
    """Raise ValueError when a preset id is not defined."""
    if preset_id not in ACTION_PRESETS:
        msg = f"Unknown {field_name} preset {preset_id!r}"
        raise ValueError(msg)


def resolve_uri_for_platform(
    provider: Provider,
    preset: dict[str, str],
    override_uri: str = "",
) -> str:
    """Pick the correct URI template based on the resolved platform."""
    if override_uri:
        return override_uri
    platform = resolved_platform(provider)
    if platform == "android" and "uri_android" in preset:
        return preset["uri_android"]
    if platform == "ios" and "uri_ios" in preset:
        return preset["uri_ios"]
    return preset.get("uri", "")


def _enrich_tap_ctx(hass: HomeAssistant | None, ctx: Mapping[str, Any]) -> Mapping[str, Any]:
    """Add camera access_token to context if available."""
    if hass is None:
        return ctx
    camera_name = str(ctx.get("camera", ""))
    if not camera_name:
        return ctx
    camera_state = hass.states.get(f"camera.{camera_name}")
    if camera_state is None:
        return ctx
    return {**ctx, "access_token": camera_state.attributes.get("access_token", "")}


def resolve_tap_url(
    profile: ProfileRuntime,
    ctx: Mapping[str, Any],
    hass: HomeAssistant | None = None,
) -> str:
    """Resolve the tap action preset to a rendered URL string."""
    tap_cfg: dict[str, Any] = profile.tap_action or {}
    preset_id = tap_cfg.get("preset", "view_clip")
    enriched = _enrich_tap_ctx(hass, ctx)

    if tap_cfg.get("uri"):
        return _JINJA_ENV.from_string(tap_cfg["uri"]).render(enriched)

    preset = ACTION_PRESETS.get(preset_id)
    if preset is None:
        _LOGGER.warning("Unknown tap_action preset %s; using noAction", preset_id)
        return "noAction"

    action_type = preset.get("type", "uri")

    if action_type == "no_action":
        return "noAction"

    if action_type != "uri":
        _LOGGER.warning(
            "Unsupported tap_action preset type %s for preset %s; using noAction",
            action_type,
            preset_id,
        )
        return "noAction"

    uri_tpl = resolve_uri_for_platform(profile.provider, preset)
    return _JINJA_ENV.from_string(uri_tpl).render(enriched)
