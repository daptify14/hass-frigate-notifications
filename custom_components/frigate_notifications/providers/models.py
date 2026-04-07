"""Typed provider-specific delivery configuration dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..enums import AttachmentType, Phase, VideoType


@dataclass(frozen=True)
class MobileAppConfig:
    """Profile-level delivery config for iOS/Android companion app."""

    channel: str = "frigate"
    sticky: bool = False
    persistent: bool = False
    android_auto: bool = False
    color: str = ""


@dataclass(frozen=True)
class AndroidTvConfig:
    """Marker for Android TV provider (overlay settings live in PhaseConfig.tv)."""


@dataclass(frozen=True)
class RenderedMedia:
    """Resolved media settings for a rendered notification."""

    still_kind: AttachmentType
    video_kind: VideoType
    use_latest_detection: bool


@dataclass(frozen=True)
class RenderedNotification:
    """Provider-neutral rendered notification ready for provider formatting."""

    title: str
    message: str
    subtitle: str
    tag: str
    group: str
    click_url: str
    alert_once_silent: bool
    critical: bool
    phase_name: Phase
    media: RenderedMedia
    ctx: dict[str, Any] = field(default_factory=dict)
    attachment_ctx: dict[str, Any] = field(default_factory=dict)
    action_ctx: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NotifyCall:
    """Final service call payload for hass.services.async_call."""

    service: str
    service_data: dict[str, Any] = field(default_factory=dict)
