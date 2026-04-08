"""Shared selectors, constants, and helper functions for config flow modules."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
import voluptuous as vol

from ..config import VALID_INTERRUPTION_LEVELS
from ..const import (
    FRIGATE_DOMAIN,
    GUARD_ENTITY_DOMAINS,
    format_camera_text,
    humanize_zone,
)
from ..data import get_available_frigate_cameras
from ..enums import Provider, resolved_platform
from ..frigate_config import get_frigate_config_view
from ..media import (
    VALID_ATTACHMENTS,
    VALID_TV_ATTACHMENTS,
    VALID_VIDEOS,
    VALID_VIDEOS_NO_HLS,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

INTERRUPTION_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=VALID_INTERRUPTION_LEVELS,
        translation_key="interruption_level",
        mode=SelectSelectorMode.DROPDOWN,
    )
)
ATTACHMENT_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=VALID_ATTACHMENTS,
        translation_key="attachment",
        mode=SelectSelectorMode.DROPDOWN,
    )
)
TV_ATTACHMENT_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=VALID_TV_ATTACHMENTS,
        translation_key="attachment",
        mode=SelectSelectorMode.DROPDOWN,
    )
)


def video_selector(provider: str) -> SelectSelector:
    """Build a video selector appropriate for the provider.

    Android omits HLS (unsupported). All other platforms show all options.
    """
    platform = resolved_platform(Provider(provider))
    options = list(VALID_VIDEOS_NO_HLS) if platform == "android" else list(VALID_VIDEOS)
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            translation_key="video",
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


VOLUME_SELECTOR = NumberSelector(
    NumberSelectorConfig(min=0, max=100, step=5, unit_of_measurement="%")
)
DELAY_SELECTOR = NumberSelector(
    NumberSelectorConfig(min=0, max=300, step=1, unit_of_measurement="s")
)
IMPORTANCE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=["default", "low", "min", "high", "max"],
        translation_key="importance",
        mode=SelectSelectorMode.DROPDOWN,
    )
)
PRIORITY_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=["default", "low", "min", "high", "max"],
        translation_key="priority",
        mode=SelectSelectorMode.DROPDOWN,
    )
)
TTL_SELECTOR = NumberSelector(
    NumberSelectorConfig(min=0, max=86400, step=1, unit_of_measurement="seconds")
)
URGENCY_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=["quiet", "normal", "urgent"],
        translation_key="urgency",
        mode=SelectSelectorMode.DROPDOWN,
    )
)
SILENCE_SELECTOR = NumberSelector(
    NumberSelectorConfig(min=1, max=480, step=1, unit_of_measurement="min")
)
INITIAL_DELAY_SELECTOR = NumberSelector(
    NumberSelectorConfig(min=0, max=10, step=0.5, unit_of_measurement="s")
)
GUARD_ENTITY_SELECTOR = EntitySelector(EntitySelectorConfig(domain=list(GUARD_ENTITY_DOMAINS)))

_EXCLUDED_NOTIFY_PREFIXES = ("mobile_app_", "send_message")
_EXCLUDED_NOTIFY_SERVICES = ("persistent_notification", "notify")


def notify_service_selector(hass: HomeAssistant) -> SelectSelector:
    """Build a SelectSelector listing available notify services, excluding per-device ones."""
    notify_services = hass.services.async_services().get("notify", {})
    options = [
        SelectOptionDict(value=f"notify.{name}", label=f"notify.{name}")
        for name in sorted(notify_services)
        if not any(name.startswith(p) for p in _EXCLUDED_NOTIFY_PREFIXES)
        and name not in _EXCLUDED_NOTIFY_SERVICES
    ]
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def content_selector(template_presets: dict, phase: str | None = None) -> SelectSelector:
    """Build a SelectSelector for content template fields (message/subtitle)."""
    options = [
        SelectOptionDict(value=t.id, label=t.label)
        for t in template_presets.get("content", [])
        if not t.phases or phase is None or phase in t.phases
    ]
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def zone_phrase_selector(template_presets: dict) -> SelectSelector:
    """Build a SelectSelector for zone phrase override fields."""
    options = [
        SelectOptionDict(value=t.value, label=t.label)
        for t in template_presets.get("zone_phrases", [])
    ]
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def title_selector(template_presets: dict) -> SelectSelector:
    """Build a SelectSelector for title template fields."""
    options = [
        SelectOptionDict(value=t.id, label=t.label) for t in template_presets.get("titles", [])
    ]
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def tv_overlay_delivery_fields(
    phase_data: dict,
) -> tuple[dict[Any, Any], dict[str, Any]]:
    """Build TV overlay schema fields and suggested values."""
    suggested = {
        "tv_fontsize": phase_data.get("tv_fontsize", "medium"),
        "tv_position": phase_data.get("tv_position", "bottom-right"),
        "tv_duration": phase_data.get("tv_duration", 5),
        "tv_transparency": phase_data.get("tv_transparency", "0%"),
        "tv_interrupt": phase_data.get("tv_interrupt", False),
        "tv_timeout": phase_data.get("tv_timeout", 30),
        "tv_color": phase_data.get("tv_color", ""),
    }
    fields: dict[Any, Any] = {
        vol.Optional("tv_fontsize", default=suggested["tv_fontsize"]): SelectSelector(
            SelectSelectorConfig(
                options=["small", "medium", "large", "max"],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional("tv_position", default=suggested["tv_position"]): SelectSelector(
            SelectSelectorConfig(
                options=["bottom-right", "bottom-left", "top-right", "top-left", "center"],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional("tv_duration", default=suggested["tv_duration"]): NumberSelector(
            NumberSelectorConfig(min=1, max=60, step=1, unit_of_measurement="seconds")
        ),
        vol.Optional("tv_transparency", default=suggested["tv_transparency"]): SelectSelector(
            SelectSelectorConfig(
                options=["0%", "25%", "50%", "75%", "100%"],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional("tv_interrupt", default=suggested["tv_interrupt"]): BooleanSelector(),
        vol.Optional("tv_timeout", default=suggested["tv_timeout"]): NumberSelector(
            NumberSelectorConfig(min=5, max=120, step=5, unit_of_measurement="seconds")
        ),
        vol.Optional("tv_color", default=suggested["tv_color"]): TextSelector(),
    }
    return fields, suggested


def normalize_interruption_level(value: str) -> str:
    """Normalize interruption-level values to the current selector vocabulary."""
    if value == "time_sensitive":
        return "time-sensitive"
    return value


def humanized_options(values: list[str]) -> list[SelectOptionDict]:
    """Build SelectSelector options with humanized labels."""
    return [SelectOptionDict(value=value, label=humanize_zone(value)) for value in values]


def profile_title(cameras: list[str], profile_name: str) -> str:
    """Build a self-describing subentry title for a profile."""
    return f"{format_camera_text(cameras)} / {profile_name.strip()}"


_TEMPLATES_DOC_URL = (
    "https://github.com/daptify14/hass-frigate-notifications"
    "/blob/main/docs/reference/templates.md#built-in-templates"
)


def profile_placeholders(data: dict[str, Any]) -> dict[str, str]:
    """Build description_placeholders for profile subentry steps."""
    cameras = data.get("cameras", [])
    return {
        "camera_name": format_camera_text(cameras),
        "profile_name": data.get("name", ""),
        "templates_url": _TEMPLATES_DOC_URL,
    }


def get_available_cameras(hass: HomeAssistant, frigate_entry_id: str) -> list[str]:
    """Return available camera names from the linked Frigate instance (sorted for UI)."""
    return sorted(get_available_frigate_cameras(hass, frigate_entry_id))


def get_camera_zones(hass: HomeAssistant, frigate_entry_id: str, camera: str) -> list[str]:
    """Return zone names for a specific camera."""
    if not camera:
        return []
    config_view = get_frigate_config_view(hass, frigate_entry_id)
    if config_view is None:
        return []
    return list(config_view.get_camera_zones(camera))


def get_tracked_objects(hass: HomeAssistant, frigate_entry_id: str, camera: str) -> list[str]:
    """Return tracked object types for a specific camera."""
    config_view = get_frigate_config_view(hass, frigate_entry_id)
    if config_view is None:
        return []
    return list(config_view.get_tracked_objects(camera))


def camera_supports_genai(hass: HomeAssistant, frigate_entry_id: str, camera: str) -> bool:
    """Check if a specific camera has GenAI review descriptions enabled."""
    config_view = get_frigate_config_view(hass, frigate_entry_id)
    if config_view is None:
        return False
    return config_view.camera_supports_genai(camera)


def supports_genai(hass: HomeAssistant, frigate_entry_id: str) -> bool:
    """Check if the linked Frigate instance has any GenAI-enabled cameras."""
    config_view = get_frigate_config_view(hass, frigate_entry_id)
    if config_view is None:
        return False
    return config_view.any_genai_enabled()


def get_camera_recognition(
    hass: HomeAssistant, frigate_entry_id: str, camera: str
) -> dict[str, bool]:
    """Detect per-camera recognition capabilities via entity registry."""
    ent_reg = er.async_get(hass)
    prefix = f"{frigate_entry_id}:sensor_recognized"
    return {
        "face": ent_reg.async_get_entity_id("sensor", FRIGATE_DOMAIN, f"{prefix}_face:{camera}")
        is not None,
        "lpr": ent_reg.async_get_entity_id("sensor", FRIGATE_DOMAIN, f"{prefix}_plate:{camera}")
        is not None,
    }


def discover_typed_sub_labels(
    hass: HomeAssistant, frigate_entry_id: str, camera: str | None = None
) -> list[tuple[str, str]]:
    """Discover typed sub-labels from entity registry.

    When camera is provided, scopes results to that camera's recognition capabilities.
    When camera is None, returns all known identities (for global options flow).

    Returns list of (type, name) tuples, e.g. [("face", "Alice"), ("lpr", "Alice's Car")].
    """
    ent_reg = er.async_get(hass)

    if camera:
        recognition = get_camera_recognition(hass, frigate_entry_id, camera)
        active_types = {t for t, enabled in recognition.items() if enabled}
    else:
        active_types = {"face", "lpr"}

    prefix = f"{frigate_entry_id}:"
    type_prefixes = {
        "face": f"{prefix}sensor_global_face:",
        "lpr": f"{prefix}sensor_global_plate:",
    }

    results: list[tuple[str, str]] = []
    for entity in er.async_entries_for_config_entry(ent_reg, frigate_entry_id):
        if entity.domain != "sensor":
            continue
        uid = entity.unique_id or ""
        for typ, uid_prefix in type_prefixes.items():
            if typ in active_types and uid.startswith(uid_prefix):
                name = uid.removeprefix(uid_prefix)
                results.append((typ, name))
                break

    return sorted(results, key=lambda x: (x[0], x[1]))


def discover_camera_sub_labels(
    hass: HomeAssistant, frigate_entry_id: str, camera: str
) -> list[tuple[str, str]]:
    """Camera-scoped typed sub-labels for profile filtering step."""
    if frigate_entry_id not in hass.data.get(FRIGATE_DOMAIN, {}):
        return []
    return discover_typed_sub_labels(hass, frigate_entry_id, camera=camera)


def discover_all_sub_labels(hass: HomeAssistant, frigate_entry_id: str) -> list[tuple[str, str]]:
    """All typed sub-labels for global options flow."""
    if frigate_entry_id not in hass.data.get(FRIGATE_DOMAIN, {}):
        return []
    return discover_typed_sub_labels(hass, frigate_entry_id, camera=None)


def build_base_url_options(
    hass: HomeAssistant, current_options: dict[str, Any]
) -> tuple[list[SelectOptionDict], str]:
    """Build selectable Home Assistant URL options and a suggested default."""
    options: list[SelectOptionDict] = []
    suggested = current_options.get("base_url") or ""
    if hass.config.external_url:
        options.append(
            SelectOptionDict(
                value=hass.config.external_url,
                label=f"External: {hass.config.external_url}",
            )
        )
        if not suggested:
            suggested = hass.config.external_url
    if hass.config.internal_url:
        options.append(
            SelectOptionDict(
                value=hass.config.internal_url,
                label=f"Internal: {hass.config.internal_url}",
            )
        )
        if not suggested:
            suggested = hass.config.internal_url
    return options, suggested


def build_frigate_url_options(
    hass: HomeAssistant, current_options: dict[str, Any], frigate_entry_id: str
) -> tuple[list[SelectOptionDict], str]:
    """Build selectable Frigate URL options and a suggested default."""
    options: list[SelectOptionDict] = []
    suggested = current_options.get("frigate_url") or ""

    if hass.data.get("hassio"):
        options.append(
            SelectOptionDict(
                value="/ccab4aaf_frigate/ingress",
                label="Frigate Addon (ingress)",
            )
        )
        options.append(
            SelectOptionDict(
                value="/ccab4aaf_frigate-fa/ingress",
                label="Frigate Full Access (ingress)",
            )
        )

    for ce in hass.config_entries.async_entries("frigate"):
        if ce.entry_id == frigate_entry_id:
            url = ce.data.get("url", "")
            if url:
                options.append(SelectOptionDict(value=url, label=f"Frigate: {url}"))
            break

    return options, suggested
