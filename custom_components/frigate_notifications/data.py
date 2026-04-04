"""Runtime types, shared helpers, and setup-time runtime config assembly."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import device_registry as dr
from homeassistant.util import slugify

from .action_presets import DEFAULT_PRESET_IDS, validate_preset_id
from .config import (
    DEFAULT_PHASE_END,
    DEFAULT_PHASE_GENAI,
    DEFAULT_PHASE_INITIAL,
    DEFAULT_PHASE_UPDATE,
    URGENCY_DEFAULTS,
    AndroidTvOverlay,
    PhaseConfig,
    PhaseContent,
    PhaseDelivery,
    PhaseMedia,
)
from .const import (
    DEFAULT_COOLDOWN_SECONDS,
    DEFAULT_EMOJI,
    DEFAULT_EMOJI_MAP,
    DEFAULT_GIF_URL,
    DEFAULT_GROUP,
    DEFAULT_INITIAL_DELAY,
    DEFAULT_PHASE_EMOJI_MAP,
    DEFAULT_SNAPSHOT_URL,
    DEFAULT_TAG,
    DEFAULT_TITLE_GENAI_PREFIXES,
    DEFAULT_TITLE_TEMPLATE,
    DOMAIN,
    FRIGATE_DOMAIN,
    SUBENTRY_TYPE_INTEGRATION,
    SUBENTRY_TYPE_PROFILE,
)
from .enums import (
    AttachmentType,
    GuardMode,
    InterruptionLevel,
    Phase,
    PresenceMode,
    Provider,
    ProviderFamily,
    RecognitionMode,
    Severity,
    StateFilterMode,
    TimeFilterMode,
    TimeFilterOverride,
    VideoType,
    ZoneMatchMode,
    provider_family,
)
from .providers.models import AndroidTvConfig, MobileAppConfig

if TYPE_CHECKING:
    from collections.abc import Iterator

    from homeassistant.config_entries import ConfigEntry, ConfigSubentry
    from homeassistant.core import HomeAssistant

    from .dispatcher import NotificationDispatcher
    from .processor import ReviewProcessor

_LOGGER = logging.getLogger(__name__)

type FrigateNotificationsConfigEntry = ConfigEntry[FrigateNotificationsRuntimeData]

# Runtime types.


@dataclass
class FrigateNotificationsRuntimeData:
    """Runtime data stored on the config entry."""

    processor: ReviewProcessor
    dispatcher: NotificationDispatcher
    mqtt_topic: str = ""
    integration_subentry_id: str | None = None


@dataclass(frozen=True)
class ProfileRuntime:
    """Merged runtime config for a single notification profile."""

    # Identity
    entry_id: str
    profile_id: str
    name: str
    cameras: tuple[str, ...]
    provider: Provider

    # Target (single service name).
    notify_target: str

    # Filtering
    objects: tuple[str, ...]
    severity: Severity
    guard_mode: GuardMode
    guard_entity: str | None
    required_zones: tuple[str, ...]
    zone_match_mode: ZoneMatchMode
    cooldown_seconds: int
    time_filter_mode: TimeFilterMode
    time_filter_start: str
    time_filter_end: str
    presence_entities: tuple[str, ...]
    state_entity: str | None
    state_filter_states: tuple[str, ...]

    # Templates (profile-level, shared across phases).
    title_template: str
    zone_overrides: dict[str, str]
    zone_aliases: dict[str, str]
    sub_label_overrides: dict[str, str]

    # Emojis (merged: default -> global -> profile).
    emoji_map: dict[str, str]
    default_emoji: str
    phase_emoji_map: dict[str, str]

    # Title
    title_genai_prefixes: dict[int, str]

    # Phases
    phases: dict[Phase, PhaseConfig]

    # Notification structure.
    silence_duration: int
    alert_once: bool
    tag: str
    group: str
    base_url: str

    snapshot_url: str = DEFAULT_SNAPSHOT_URL
    gif_url: str = DEFAULT_GIF_URL

    # Recognition filtering (defaults = disabled / permissive).
    recognition_mode: RecognitionMode = RecognitionMode.DISABLED
    required_sub_labels: tuple[str, ...] = ()
    excluded_sub_labels: tuple[str, ...] = ()

    # Provider-specific delivery config.
    provider_config: MobileAppConfig | AndroidTvConfig = field(default_factory=MobileAppConfig)

    # Action button presets (stored as preset IDs, resolved at render time).
    action_config: tuple[dict[str, Any], ...] = field(
        default_factory=lambda: tuple({"preset": p} for p in DEFAULT_PRESET_IDS)
    )

    # Tap action preset (what opens when user taps the notification body).
    tap_action: dict[str, Any] = field(default_factory=lambda: {"preset": "view_clip"})

    # Custom action sequence executed when user taps "Custom Action" button.
    on_button_action: tuple[dict[str, Any], ...] = ()

    # Frigate URL (for open_frigate preset, resolved from global options).
    frigate_url: str = ""

    # Frigate client_id path segment for multi-instance (e.g. "/my-instance" or "").
    client_id: str = ""

    def get_phase(self, phase: Phase) -> PhaseConfig:
        """Get phase config with fallback chain: explicit -> end-inherits-update -> defaults."""
        if phase in self.phases:
            return self.phases[phase]
        # End inherits from Update when not explicitly configured.
        if phase == Phase.END and Phase.UPDATE in self.phases:
            return self.phases[Phase.UPDATE]
        defaults = {
            Phase.INITIAL: DEFAULT_PHASE_INITIAL,
            Phase.UPDATE: DEFAULT_PHASE_UPDATE,
            Phase.END: DEFAULT_PHASE_END,
            Phase.GENAI: DEFAULT_PHASE_GENAI,
        }
        return defaults.get(phase, DEFAULT_PHASE_UPDATE)

    @property
    def is_multi_camera(self) -> bool:
        """Return True when this profile covers more than one camera."""
        return len(self.cameras) > 1


@dataclass(frozen=True)
class RuntimeConfig:
    """All active profiles, indexed by camera name."""

    profiles: dict[str, list[ProfileRuntime]] = field(default_factory=dict)
    initial_delay: float = DEFAULT_INITIAL_DELAY
    global_zone_aliases: dict[str, dict[str, str]] = field(default_factory=dict)
    template_id_map: dict[str, str] = field(default_factory=dict)


# Shared Frigate / subentry helpers.


def get_frigate_config(hass: HomeAssistant, frigate_entry_id: str) -> dict[str, Any]:
    """Return the Frigate camera config stored by the Frigate integration."""
    return hass.data["frigate"][frigate_entry_id]["config"]


def get_available_frigate_cameras(hass: HomeAssistant, frigate_entry_id: str) -> set[str]:
    """Return the current set of cameras exposed by the selected Frigate entry."""
    try:
        frigate_config = get_frigate_config(hass, frigate_entry_id)
    except KeyError:
        return set()
    return set(frigate_config["cameras"])


def get_frigate_camera_identifier(frigate_entry_id: str, camera_name: str) -> tuple[str, str]:
    """Return the device-registry identifier tuple for a Frigate camera."""
    return (FRIGATE_DOMAIN, f"{frigate_entry_id}:{slugify(camera_name)}")


def get_frigate_camera_device(
    hass: HomeAssistant,
    frigate_entry_id: str,
    camera_name: str,
) -> dr.DeviceEntry | None:
    """Return the existing Frigate device entry for a camera."""
    if camera_name not in get_available_frigate_cameras(hass, frigate_entry_id):
        return None
    return dr.async_get(hass).async_get_device(
        identifiers={get_frigate_camera_identifier(frigate_entry_id, camera_name)}
    )


def get_profile_device_identifiers(entry_id: str, subentry_id: str) -> set[tuple[str, str]]:
    """Return device registry identifiers for a profile device."""
    return {(DOMAIN, f"profile:{entry_id}:{subentry_id}")}


def get_profile_device_name(profile_name: str) -> str:
    """Return the human-facing device name for a notification profile."""
    return profile_name


def get_integration_subentry_id(entry: ConfigEntry) -> str | None:
    """Return the integration subentry ID for a config entry, if present."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_TYPE_INTEGRATION:
            return subentry.subentry_id
    return None


def iter_profile_subentries(entry: ConfigEntry) -> Iterator[ConfigSubentry]:
    """Yield subentries that are notification profiles."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_TYPE_PROFILE:
            yield subentry


def profile_common_fields(subentry: ConfigSubentry) -> dict[str, Any]:
    """Extract common entity-constructor fields from a profile subentry."""
    return {
        "subentry_id": subentry.subentry_id,
        "cameras": tuple(subentry.data["cameras"]),
        "profile_name": subentry.data["name"],
        "provider": subentry.data.get("provider", Provider.APPLE),
    }


# Option resolution helpers.


def resolve_time_filter(
    profile_data: dict, global_opts: Mapping
) -> tuple[TimeFilterMode, str, str]:
    """Resolve time filter settings from profile + global inheritance."""
    override = profile_data.get("time_filter_override", TimeFilterOverride.INHERIT)
    if override == TimeFilterOverride.CUSTOM:
        return (
            TimeFilterMode(profile_data.get("time_filter_mode", TimeFilterMode.DISABLED)),
            profile_data.get("time_filter_start", ""),
            profile_data.get("time_filter_end", ""),
        )
    if override == TimeFilterOverride.DISABLED:
        return (TimeFilterMode.DISABLED, "", "")
    # inherit
    return (
        TimeFilterMode(global_opts.get("shared_time_filter_mode", TimeFilterMode.DISABLED)),
        global_opts.get("shared_time_filter_start", ""),
        global_opts.get("shared_time_filter_end", ""),
    )


def resolve_guard_entity(profile_data: dict, global_opts: Mapping) -> tuple[GuardMode, str | None]:
    """Resolve guard entity settings from profile + global inheritance."""
    mode = GuardMode(profile_data.get("guard_mode", GuardMode.INHERIT))
    if mode == GuardMode.CUSTOM:
        return (GuardMode.CUSTOM, profile_data.get("guard_entity"))
    if mode == GuardMode.DISABLED:
        return (GuardMode.DISABLED, None)
    # inherit
    return (GuardMode.INHERIT, global_opts.get("shared_guard_entity"))


def resolve_presence(profile_data: dict, global_opts: Mapping) -> tuple[str, ...]:
    """Resolve presence entities from profile + global inheritance."""
    mode = PresenceMode(profile_data.get("presence_mode", PresenceMode.INHERIT))
    if mode == PresenceMode.CUSTOM:
        return tuple(profile_data.get("presence_entities", []))
    if mode == PresenceMode.DISABLED:
        return ()
    # inherit
    return tuple(global_opts.get("shared_presence_entities", []))


def resolve_state_filter(
    profile_data: dict, global_opts: Mapping
) -> tuple[str | None, tuple[str, ...]]:
    """Resolve state filter from profile + global inheritance."""
    mode = StateFilterMode(profile_data.get("state_filter_mode", StateFilterMode.INHERIT))
    if mode == StateFilterMode.CUSTOM:
        return (
            profile_data.get("state_entity"),
            tuple(profile_data.get("state_filter_states", [])),
        )
    if mode == StateFilterMode.DISABLED:
        return (None, ())
    # inherit
    return (
        global_opts.get("shared_state_entity"),
        tuple(global_opts.get("shared_state_filter_states", [])),
    )


def build_emoji_map(global_opts: Mapping[str, Any]) -> dict[str, str]:
    """Build the emoji_map by merging defaults with global options."""
    if not global_opts.get("enable_emojis", True):
        return {}
    base = dict(DEFAULT_EMOJI_MAP)
    base.update(global_opts.get("emoji_map", {}))
    return base


def build_phase_emoji_map(global_opts: Mapping[str, Any]) -> dict[str, str]:
    """Build phase_emoji_map by merging defaults with global overrides."""
    if not global_opts.get("enable_emojis", True):
        return dict.fromkeys(DEFAULT_PHASE_EMOJI_MAP, "")
    base = dict(DEFAULT_PHASE_EMOJI_MAP)
    base.update(global_opts.get("phase_emoji_map", {}))
    return base


def _build_global_genai_prefixes(global_opts: Mapping[str, Any]) -> dict[int, str]:
    """Build GenAI title prefixes: system defaults -> global options."""
    merged = dict(DEFAULT_TITLE_GENAI_PREFIXES)
    merged.update({int(k): v for k, v in global_opts.get("title_genai_prefixes", {}).items()})
    return merged


# Private runtime build helpers.

_FALLBACK_DELIVERY: dict[str, Any] = {
    "ios_sound": "default",
    "ios_interruption": "active",
    "android_importance": "high",
    "android_priority": "high",
    "android_ttl": 0,
}


def _expand_urgency(pd: dict) -> dict[str, Any]:
    """Expand portable urgency to concrete iOS + Android delivery values.

    Explicit concrete fields in pd take precedence over urgency defaults.
    """
    urgency = pd.get("urgency", "")
    base = URGENCY_DEFAULTS.get(urgency, _FALLBACK_DELIVERY)
    return {
        "sound": pd.get("sound", base["ios_sound"]),
        "interruption_level": pd.get("interruption_level", base["ios_interruption"]),
        "importance": pd.get("importance", base["android_importance"]),
        "priority": pd.get("priority", base["android_priority"]),
        "ttl": int(pd.get("ttl", base["android_ttl"])),
    }


def _build_phases(phases_data: dict) -> dict[Phase, PhaseConfig]:
    """Build PhaseConfig dict from raw subentry data."""
    result: dict[Phase, PhaseConfig] = {}
    for phase_key, pd in phases_data.items():
        expanded = _expand_urgency(pd)
        result[Phase(phase_key)] = PhaseConfig(
            content=PhaseContent(
                title_template=pd.get("title_template", ""),
                message_template=pd.get("message_template", ""),
                subtitle_template=pd.get("subtitle_template", ""),
                emoji_message=pd.get("emoji_message", True),
                emoji_subtitle=pd.get("emoji_subtitle", False),
                title_prefix_enabled=pd.get("title_prefix_enabled", True),
            ),
            delivery=PhaseDelivery(
                sound=expanded["sound"],
                volume=float(pd.get("volume", 1.0)),
                interruption_level=InterruptionLevel(expanded["interruption_level"]),
                importance=expanded["importance"],
                priority=expanded["priority"],
                ttl=expanded["ttl"],
                urgency=pd.get("urgency", ""),
                critical=pd.get("critical", False),
                delay=float(pd.get("delay", 0.0)),
                enabled=pd.get("enabled", True),
            ),
            media=PhaseMedia(
                attachment=AttachmentType(pd.get("attachment", AttachmentType.SNAPSHOT_CROPPED)),
                video=pd.get("video", VideoType.NONE),
                use_latest_detection=pd.get("use_latest_detection", False),
            ),
            tv=AndroidTvOverlay(
                fontsize=pd.get("tv_fontsize", "medium"),
                position=pd.get("tv_position", "bottom-right"),
                duration=int(pd.get("tv_duration", 5)),
                transparency=pd.get("tv_transparency", "0%"),
                interrupt=bool(pd.get("tv_interrupt", False)),
                timeout=int(pd.get("tv_timeout", 30)),
                color=pd.get("tv_color", ""),
            ),
            custom_actions=tuple(pd.get("custom_actions", [])),
        )
    return result


def _resolve_notify_target(hass: HomeAssistant, profile_data: dict) -> str:
    """Resolve notify target from device ID or service name."""
    device_id = profile_data.get("notify_device", "")
    if device_id:
        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(device_id)
        if device is None:
            _LOGGER.warning("Notify target device %s not found in device registry", device_id)
            return ""
        return f"notify.mobile_app_{slugify(device.name)}"
    return profile_data.get("notify_service", "")


def _build_provider_config(p: dict) -> MobileAppConfig | AndroidTvConfig:
    """Build the typed provider config from profile subentry data."""
    if provider_family(Provider(p.get("provider", Provider.APPLE))) == ProviderFamily.ANDROID_TV:
        return AndroidTvConfig()
    return MobileAppConfig(
        channel=p.get("android_channel", "frigate"),
        sticky=bool(p.get("android_sticky", False)),
        persistent=bool(p.get("android_persistent", False)),
        android_auto=bool(p.get("android_auto", False)),
        color=p.get("android_color", ""),
    )


def _resolve_client_id(hass: HomeAssistant, frigate_entry_id: str) -> str:
    """Resolve Frigate client_id path segment (e.g. "/my-instance" or "")."""
    ce = hass.config_entries.async_get_entry(frigate_entry_id)
    if ce is None:
        return ""
    cid = ce.data.get("client_id", "")
    return f"/{cid}" if cid else ""


def _validate_profile_presets(
    profile_id: str,
    tap_action: Mapping[str, Any],
    action_config: tuple[dict[str, Any], ...],
) -> None:
    """Validate stored preset ids before building ProfileRuntime."""
    validate_preset_id(
        str(tap_action.get("preset", "view_clip")),
        field_name=f"tap_action for profile {profile_id}",
    )
    for index, action in enumerate(action_config, start=1):
        validate_preset_id(
            str(action.get("preset", "none")),
            field_name=f"action_config[{index}] for profile {profile_id}",
        )


@dataclass(frozen=True)
class _GlobalDefaults:
    """Resolved global options used when building per-profile configs."""

    available_cameras: set[str]
    global_opts: Mapping[str, Any]
    base_url: str
    frigate_url: str
    client_id: str
    emoji_map: dict[str, str]
    phase_emoji_map: dict[str, str]
    default_emoji: str
    genai_prefixes: dict[int, str]
    sub_label_overrides: dict[str, str]
    default_silence_duration: int
    default_cooldown_seconds: int
    default_title_template: str
    global_zone_aliases: dict[str, dict[str, str]]


def _resolve_global_defaults(hass: HomeAssistant, entry: ConfigEntry) -> _GlobalDefaults:
    """Resolve global options and Frigate config into defaults for profile building."""
    global_opts = entry.options
    frigate_entry_id = entry.data["frigate_entry_id"]
    available_cameras = get_available_frigate_cameras(hass, frigate_entry_id)
    fallback_base_url = entry.data.get("base_url") or hass.config.external_url or ""
    emojis_enabled = global_opts.get("enable_emojis", True)

    return _GlobalDefaults(
        available_cameras=available_cameras,
        global_opts=global_opts,
        base_url=global_opts.get("base_url", fallback_base_url),
        frigate_url=global_opts.get("frigate_url", ""),
        client_id=_resolve_client_id(hass, frigate_entry_id),
        emoji_map=build_emoji_map(global_opts),
        phase_emoji_map=build_phase_emoji_map(global_opts),
        default_emoji=(global_opts.get("default_emoji", DEFAULT_EMOJI) if emojis_enabled else ""),
        genai_prefixes=_build_global_genai_prefixes(global_opts),
        sub_label_overrides=(
            dict(global_opts.get("sub_label_overrides", {})) if emojis_enabled else {}
        ),
        default_silence_duration=int(global_opts.get("silence_duration", 30)),
        default_cooldown_seconds=int(global_opts.get("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS)),
        default_title_template=global_opts.get("title_template", DEFAULT_TITLE_TEMPLATE),
        global_zone_aliases=dict(global_opts.get("zone_aliases", {})),
    )


def _build_profile(
    hass: HomeAssistant,
    entry_id: str,
    subentry: ConfigSubentry,
    defaults: _GlobalDefaults,
) -> ProfileRuntime | None:
    """Build a ProfileRuntime from a profile subentry, or None if no valid cameras."""
    p = dict(subentry.data)
    raw_cameras = tuple(p["cameras"])

    valid_cameras = tuple(cam for cam in raw_cameras if cam in defaults.available_cameras)
    if not valid_cameras:
        _LOGGER.warning(
            "No available cameras for profile %s (configured: %s), skipping",
            p.get("name", subentry.subentry_id),
            raw_cameras,
        )
        return None

    for cam in raw_cameras:
        if cam not in defaults.available_cameras:
            _LOGGER.warning(
                "Camera %s not available for profile %s, skipping camera",
                cam,
                p.get("name", subentry.subentry_id),
            )

    silence = p.get("silence_duration") or defaults.default_silence_duration

    time_filter_mode, time_filter_start, time_filter_end = resolve_time_filter(
        p, defaults.global_opts
    )
    guard_mode, guard_entity = resolve_guard_entity(p, defaults.global_opts)
    presence_entities = resolve_presence(p, defaults.global_opts)
    state_entity, state_filter_states = resolve_state_filter(p, defaults.global_opts)

    zone_overrides = dict(p.get("zone_overrides", {}))
    if len(valid_cameras) == 1:
        zone_aliases = dict(defaults.global_zone_aliases.get(valid_cameras[0], {}))
    else:
        zone_aliases = {}

    action_config = tuple(
        p.get(
            "action_config",
            [{"preset": pid} for pid in DEFAULT_PRESET_IDS],
        )
    )
    tap_action = dict(p.get("tap_action", {"preset": "view_clip"}))
    _validate_profile_presets(subentry.subentry_id, tap_action, action_config)

    return ProfileRuntime(
        entry_id=entry_id,
        profile_id=subentry.subentry_id,
        name=p["name"],
        cameras=valid_cameras,
        provider=Provider(p.get("provider", Provider.APPLE)),
        notify_target=_resolve_notify_target(hass, p),
        objects=tuple(p.get("objects", [])),
        severity=Severity(p.get("severity", Severity.ALERT)),
        guard_mode=guard_mode,
        guard_entity=guard_entity,
        required_zones=tuple(p.get("required_zones", [])),
        zone_match_mode=ZoneMatchMode(p.get("zone_match_mode", ZoneMatchMode.ANY)),
        cooldown_seconds=int(
            p["cooldown_override"]
            if p.get("cooldown_override") is not None
            else defaults.default_cooldown_seconds
        ),
        time_filter_mode=time_filter_mode,
        time_filter_start=time_filter_start,
        time_filter_end=time_filter_end,
        presence_entities=presence_entities,
        state_entity=state_entity,
        state_filter_states=state_filter_states,
        recognition_mode=RecognitionMode(p.get("recognition_mode", RecognitionMode.DISABLED)),
        required_sub_labels=tuple(p.get("include_sub_labels", [])),
        excluded_sub_labels=tuple(p.get("exclude_sub_labels", [])),
        title_template=(p.get("title_template") or defaults.default_title_template),
        zone_overrides=zone_overrides,
        zone_aliases=zone_aliases,
        sub_label_overrides=dict(defaults.sub_label_overrides),
        emoji_map=dict(defaults.emoji_map),
        default_emoji=defaults.default_emoji,
        phase_emoji_map=dict(defaults.phase_emoji_map),
        title_genai_prefixes=dict(defaults.genai_prefixes),
        phases=_build_phases(p.get("phases", {})),
        silence_duration=int(silence),
        alert_once=bool(p.get("alert_once", False)),
        tag=p.get("tag", DEFAULT_TAG),
        group=p.get("group", DEFAULT_GROUP),
        base_url=defaults.base_url,
        provider_config=_build_provider_config(p),
        action_config=action_config,
        tap_action=tap_action,
        frigate_url=defaults.frigate_url,
        client_id=defaults.client_id,
        on_button_action=tuple(p.get("on_button_action", [])),
    )


# Public runtime assembly.


def build_runtime_config(hass: HomeAssistant, entry: ConfigEntry) -> RuntimeConfig:
    """Build RuntimeConfig from the main entry and profile subentries."""
    defaults = _resolve_global_defaults(hass, entry)

    profiles_by_camera: dict[str, list[ProfileRuntime]] = {}
    for se in iter_profile_subentries(entry):
        profile = _build_profile(hass, entry.entry_id, se, defaults)
        if profile is None:
            continue
        for cam in profile.cameras:
            profiles_by_camera.setdefault(cam, []).append(profile)

    template_id_map: dict[str, str] = hass.data.get(DOMAIN, {}).get("template_id_map", {})

    return RuntimeConfig(
        profiles=profiles_by_camera,
        initial_delay=float(defaults.global_opts.get("initial_delay", DEFAULT_INITIAL_DELAY)),
        global_zone_aliases=defaults.global_zone_aliases,
        template_id_map=template_id_map,
    )
