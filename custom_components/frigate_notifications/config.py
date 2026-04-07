"""Phase configuration dataclasses for Notifications for Frigate."""

from dataclasses import dataclass, field
from typing import Any

from .const import DEFAULT_MESSAGE_TEMPLATE
from .enums import AttachmentType, InterruptionLevel, VideoType

URGENCY_DEFAULTS: dict[str, dict[str, Any]] = {
    "quiet": {
        "ios_sound": "none",
        "ios_interruption": "passive",
        "android_importance": "low",
        "android_priority": "default",
        "android_ttl": 0,
    },
    "normal": {
        "ios_sound": "default",
        "ios_interruption": "active",
        "android_importance": "default",
        "android_priority": "default",
        "android_ttl": 0,
    },
    "urgent": {
        "ios_sound": "default",
        "ios_interruption": "time-sensitive",
        "android_importance": "high",
        "android_priority": "high",
        "android_ttl": 0,
    },
}


@dataclass(frozen=True)
class PhaseContent:
    """Content templates for a notification phase."""

    title_template: str = ""
    message_template: str = ""
    subtitle_template: str = ""
    emoji_message: bool = True
    emoji_subtitle: bool = False
    title_prefix_enabled: bool = True


@dataclass(frozen=True)
class PhaseDelivery:
    """Delivery settings for a notification phase."""

    # iOS fields
    sound: str = "default"
    volume: float = 1.0
    interruption_level: InterruptionLevel = InterruptionLevel.ACTIVE
    # Android fields
    importance: str = "high"
    priority: str = "high"
    ttl: int = 0
    # Portable urgency (cross-platform)
    urgency: str = ""
    # Shared
    critical: bool = False
    delay: float = 0.0
    enabled: bool = True


@dataclass(frozen=True)
class PhaseMedia:
    """Media settings for a notification phase."""

    attachment: AttachmentType = AttachmentType.SNAPSHOT_CROPPED
    video: VideoType = VideoType.NONE
    use_latest_detection: bool = False


@dataclass(frozen=True)
class AndroidTvOverlay:
    """Android TV overlay settings."""

    fontsize: str = "medium"
    position: str = "bottom-right"
    duration: int = 5
    transparency: str = "0%"
    interrupt: bool = False
    timeout: int = 30
    color: str = ""


@dataclass(frozen=True)
class PhaseConfig:
    """Configuration for a single notification phase."""

    content: PhaseContent = field(default_factory=PhaseContent)
    delivery: PhaseDelivery = field(default_factory=PhaseDelivery)
    media: PhaseMedia = field(default_factory=PhaseMedia)
    tv: AndroidTvOverlay = field(default_factory=AndroidTvOverlay)
    custom_actions: tuple[dict[str, Any], ...] = ()


DEFAULT_PHASE_INITIAL = PhaseConfig(
    content=PhaseContent(
        message_template=DEFAULT_MESSAGE_TEMPLATE,
        subtitle_template="merged_subjects",
    ),
    delivery=PhaseDelivery(
        sound="default",
        volume=1.0,
        interruption_level=InterruptionLevel.ACTIVE,
    ),
    media=PhaseMedia(attachment=AttachmentType.SNAPSHOT_CROPPED),
)

DEFAULT_PHASE_UPDATE = PhaseConfig(
    content=PhaseContent(
        message_template=DEFAULT_MESSAGE_TEMPLATE,
        subtitle_template="merged_subjects",
    ),
    delivery=PhaseDelivery(sound="none", volume=0.0),
    media=PhaseMedia(
        attachment=AttachmentType.REVIEW_GIF,
        use_latest_detection=True,
    ),
)

DEFAULT_PHASE_END = PhaseConfig(
    content=PhaseContent(
        message_template=DEFAULT_MESSAGE_TEMPLATE,
        subtitle_template="merged_subjects",
    ),
    delivery=PhaseDelivery(sound="none", volume=0.0, delay=5.0),
    media=PhaseMedia(
        attachment=AttachmentType.REVIEW_GIF,
        use_latest_detection=True,
    ),
)

DEFAULT_PHASE_GENAI = PhaseConfig(
    content=PhaseContent(
        message_template="genai_summary",
        subtitle_template="merged_subjects",
        emoji_message=False,
    ),
    delivery=PhaseDelivery(
        sound="default",
        volume=1.0,
        interruption_level=InterruptionLevel.PASSIVE,
    ),
    media=PhaseMedia(
        attachment=AttachmentType.REVIEW_GIF,
        use_latest_detection=True,
    ),
)
