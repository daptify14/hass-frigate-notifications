"""Named action button presets for notification profiles."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from .enums import ActionType, Provider, VideoType, resolved_platform
from .media import ATTACHMENT_URL_TEMPLATES, VIDEO_URL_TEMPLATES

if TYPE_CHECKING:
    from homeassistant.helpers.selector import SelectOptionDict

    from .data import ProfileRuntime

# Separate from HA's Template engine: uses StrictUndefined so a missing
# variable in a URI template fails loudly instead of rendering empty.
_JINJA_ENV = SandboxedEnvironment(undefined=StrictUndefined)
_LOGGER = logging.getLogger(__name__)

ACTION_PRESETS: dict[str, dict[str, str]] = {
    "view_clip": {
        "type": ActionType.URI,
        "title": "View Clip",
        "uri_ios": VIDEO_URL_TEMPLATES[VideoType.CLIP_HLS],
        "uri_android": VIDEO_URL_TEMPLATES[VideoType.CLIP_MP4],
        "uri": VIDEO_URL_TEMPLATES[VideoType.CLIP_HLS],
        "icon": "sfsymbols:play.rectangle",
    },
    "view_snapshot": {
        "type": ActionType.URI,
        "title": "View Snapshot",
        "uri": ATTACHMENT_URL_TEMPLATES["snapshot"],
        "icon": "sfsymbols:photo",
    },
    "view_gif": {
        "type": ActionType.URI,
        "title": "View GIF",
        "uri": ATTACHMENT_URL_TEMPLATES["review_gif"],
        "icon": "sfsymbols:photo.on.rectangle",
    },
    "view_stream": {
        "type": ActionType.URI,
        "title": "View Live Stream",
        "uri": (
            "{{ base_url }}/api/camera_proxy_stream/camera.{{ camera }}?token={{ access_token }}"
        ),
        "icon": "sfsymbols:video.fill",
    },
    "silence": {
        "type": ActionType.SILENCE,
        "title": "Silence Notifications",
    },
    "open_ha_app": {
        "type": ActionType.URI,
        "title": "Open HA (App)",
        "uri": "/lovelace",
        "icon": "sfsymbols:house.fill",
    },
    "open_ha_web": {
        "type": ActionType.URI,
        "title": "Open HA (Browser)",
        "uri": "{{ base_url }}/lovelace",
        "icon": "sfsymbols:house",
    },
    "open_frigate": {
        "type": ActionType.URI,
        "title": "Open Frigate",
        "uri": "{{ frigate_url }}",
        "icon": "sfsymbols:video",
    },
    "custom_action": {
        "type": ActionType.EVENT,
        "title": "Custom Action",
        "icon": "sfsymbols:bolt",
    },
    "no_action": {
        "type": ActionType.NO_ACTION,
        "title": "",
    },
    "none": {
        "type": ActionType.NONE,
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


def resolve_tap_url(
    profile: ProfileRuntime,
    ctx: Mapping[str, Any],
) -> str:
    """Resolve the tap action preset to a rendered URL string.

    Caller is expected to pass a context already enriched with access_token.
    """
    tap_cfg: dict[str, Any] = profile.tap_action or {}
    preset_id = tap_cfg.get("preset", "view_clip")

    if tap_cfg.get("uri"):
        return _JINJA_ENV.from_string(tap_cfg["uri"]).render(ctx)

    preset = ACTION_PRESETS.get(preset_id)
    if preset is None:
        _LOGGER.warning("Unknown tap_action preset %s; using noAction", preset_id)
        return "noAction"

    action_type = preset.get("type", ActionType.URI)

    if action_type == ActionType.NO_ACTION:
        return "noAction"

    if action_type != ActionType.URI:
        _LOGGER.warning(
            "Unsupported tap_action preset type %s for preset %s; using noAction",
            action_type,
            preset_id,
        )
        return "noAction"

    uri_tpl = resolve_uri_for_platform(profile.provider, preset)
    return _JINJA_ENV.from_string(uri_tpl).render(ctx)
