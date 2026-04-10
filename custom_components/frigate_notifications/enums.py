"""Enum definitions for Notifications for Frigate."""

from enum import StrEnum


class Lifecycle(StrEnum):
    """MQTT review message types."""

    NEW = "new"
    UPDATE = "update"
    END = "end"
    GENAI = "genai"


class Phase(StrEnum):
    """Notification dispatch phases."""

    INITIAL = "initial"
    UPDATE = "update"
    END = "end"
    GENAI = "genai"


class Severity(StrEnum):
    """Review severity levels."""

    ALERT = "alert"
    DETECTION = "detection"
    ANY = "any"


class ZoneMatchMode(StrEnum):
    """Zone matching strategies."""

    ANY = "any"
    ALL = "all"
    ORDERED = "ordered"


class TimeFilterMode(StrEnum):
    """Time-based notification filter modes."""

    DISABLED = "disabled"
    ONLY_DURING = "notify_only_during"
    NOT_DURING = "do_not_notify_during"


class GuardMode(StrEnum):
    """Guard entity operating modes."""

    INHERIT = "inherit"
    CUSTOM = "custom"
    DISABLED = "disabled"


class PresenceMode(StrEnum):
    """Presence filter modes."""

    INHERIT = "inherit"
    CUSTOM = "custom"
    DISABLED = "disabled"


class StateFilterMode(StrEnum):
    """State filter modes."""

    INHERIT = "inherit"
    CUSTOM = "custom"
    DISABLED = "disabled"


class Provider(StrEnum):
    """Notification delivery provider types."""

    APPLE = "apple"
    ANDROID = "android"
    CROSS_PLATFORM = "cross_platform"
    ANDROID_TV = "android_tv"


class ProviderFamily(StrEnum):
    """Transport adapter families for notification delivery."""

    MOBILE_APP = "mobile_app"
    ANDROID_TV = "android_tv"


_PROVIDER_TO_FAMILY: dict[Provider, ProviderFamily] = {
    Provider.APPLE: ProviderFamily.MOBILE_APP,
    Provider.ANDROID: ProviderFamily.MOBILE_APP,
    Provider.CROSS_PLATFORM: ProviderFamily.MOBILE_APP,
    Provider.ANDROID_TV: ProviderFamily.ANDROID_TV,
}

_PROVIDER_TO_PLATFORM: dict[Provider, str] = {
    Provider.APPLE: "ios",
    Provider.ANDROID: "android",
    Provider.CROSS_PLATFORM: "unknown",
    Provider.ANDROID_TV: "android_tv",
}


def provider_family(provider: Provider) -> ProviderFamily:
    """Return the transport adapter family for a provider."""
    try:
        return _PROVIDER_TO_FAMILY[provider]
    except KeyError as err:
        msg = f"Unknown provider: {provider!r}"
        raise ValueError(msg) from err


def resolved_platform(provider: Provider) -> str:
    """Return the platform string for URI/payload branching."""
    try:
        return _PROVIDER_TO_PLATFORM[provider]
    except KeyError as err:
        msg = f"Unknown provider: {provider!r}"
        raise ValueError(msg) from err


class AttachmentType(StrEnum):
    """Notification attachment types."""

    THUMBNAIL = "thumbnail"
    SNAPSHOT = "snapshot"
    SNAPSHOT_BBOX = "snapshot_bbox"
    SNAPSHOT_CROPPED = "snapshot_cropped"
    SNAPSHOT_CROPPED_BBOX = "snapshot_cropped_bbox"
    REVIEW_GIF = "review_gif"
    EVENT_GIF = "event_gif"


class RecognitionMode(StrEnum):
    """Recognition-based filtering modes."""

    DISABLED = "disabled"
    REQUIRE_RECOGNIZED = "require_recognized"
    EXCLUDE_SUB_LABELS = "exclude_sub_labels"


class VideoType(StrEnum):
    """Video attachment types for notifications."""

    CLIP_HLS = "clip_hls"
    CLIP_MP4 = "clip_mp4"
    LIVE_VIEW = "live_view"
    NONE = "none"
    REVIEW_GIF_VIDEO = "review_gif_video"


class TimeFilterOverride(StrEnum):
    """Per-profile time filter override modes."""

    INHERIT = "inherit"
    CUSTOM = "custom"
    DISABLED = "disabled"


class InterruptionLevel(StrEnum):
    """iOS notification interruption levels."""

    ACTIVE = "active"
    PASSIVE = "passive"
    TIME_SENSITIVE = "time-sensitive"


class ActionType(StrEnum):
    """Notification action button types."""

    URI = "uri"
    SILENCE = "silence"
    EVENT = "event"
    NO_ACTION = "no_action"
    NONE = "none"
