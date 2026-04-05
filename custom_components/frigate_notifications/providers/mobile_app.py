"""Mobile App notification provider for iOS and Android companion apps.

Emits both iOS and Android keys in the same payload — companion apps
ignore keys they do not understand.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from ..const import (
    ANDROID_IMAGE_URL_TEMPLATES,
    ANDROID_VIDEO_URL_TEMPLATES,
    ATTACHMENT_CONTENT_TYPES,
    ATTACHMENT_URL_TEMPLATES,
    VIDEO_CONTENT_TYPES,
    VIDEO_URL_TEMPLATES,
)
from ..enums import VideoType, resolved_platform
from ..message_builder import render_template
from .models import MobileAppConfig, NotifyCall, RenderedNotification

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..config import PhaseConfig
    from ..data import ProfileRuntime
    from ..models import Review


class MobileAppProvider:
    """Provider adapter for HA Companion App (iOS + Android)."""

    provider_id = "mobile_app"

    def build_notify_call(
        self,
        hass: HomeAssistant,
        profile: ProfileRuntime,
        review: Review,
        rendered: RenderedNotification,
    ) -> NotifyCall:
        """Build a NotifyCall with both iOS and Android keys."""
        phase = profile.get_phase(rendered.phase_name)
        if not isinstance(profile.provider_config, MobileAppConfig):
            msg = f"Expected MobileAppConfig, got {type(profile.provider_config)}"
            raise TypeError(msg)
        cfg = profile.provider_config

        ios_url, ios_content_type = self._resolve_ios_media(hass, rendered, rendered.attachment_ctx)
        android_image = self._resolve_android_image(hass, rendered, rendered.attachment_ctx)
        android_video = self._resolve_android_video(hass, rendered, rendered.attachment_ctx)
        actions = self._build_actions(hass, profile, rendered.action_ctx)

        data: dict[str, Any] = {
            "tag": rendered.tag,
            "group": rendered.group,
            "subtitle": rendered.subtitle,
            "url": rendered.click_url,
            "attachment": {
                "url": ios_url,
                "content-type": ios_content_type,
            },
            "push": {
                "sound": _build_sound_dict(
                    phase,
                    critical=rendered.critical,
                    alert_once_silent=rendered.alert_once_silent,
                ),
                "interruption-level": (
                    "critical" if rendered.critical else str(phase.delivery.interruption_level)
                ),
            },
            "actions": actions,
        }

        # Live View: tell the iOS companion app to show the camera's live stream.
        if rendered.media.video_kind == VideoType.LIVE_VIEW:
            camera_name = str(rendered.ctx.get("camera", ""))
            if camera_name:
                data["entity_id"] = f"camera.{camera_name}"

        data.update(
            self._build_android_data(
                profile=profile,
                rendered=rendered,
                cfg=cfg,
                android_image_url=android_image,
                android_video_url=android_video,
            )
        )

        service = profile.notify_target
        if service.startswith("notify."):
            service = service.removeprefix("notify.")

        return NotifyCall(
            service=service,
            service_data={
                "title": rendered.title,
                "message": rendered.message,
                "data": data,
            },
        )

    def _build_android_data(
        self,
        *,
        profile: ProfileRuntime,
        rendered: RenderedNotification,
        cfg: MobileAppConfig,
        android_image_url: str,
        android_video_url: str,
    ) -> dict[str, Any]:
        """Build Android companion-app keys."""
        phase_delivery = profile.get_phase(rendered.phase_name).delivery
        data: dict[str, Any] = {
            "image": android_image_url,
            "clickAction": rendered.click_url,
            "subject": rendered.subtitle,
            "ttl": 0 if rendered.critical else phase_delivery.ttl,
            "priority": "high" if rendered.critical else phase_delivery.priority,
            "importance": phase_delivery.importance,
            "channel": "alarm_stream" if rendered.critical else cfg.channel,
            "sticky": cfg.sticky,
            "persistent": cfg.persistent,
            "car_ui": cfg.android_auto,
        }

        if profile.alert_once and not rendered.critical:
            data["alert_once"] = True

        if android_video_url:
            data["video"] = android_video_url

        if cfg.color:
            data["color"] = cfg.color

        return data

    def _resolve_ios_media(
        self,
        hass: HomeAssistant,
        rendered: RenderedNotification,
        attachment_ctx: Mapping[str, Any],
    ) -> tuple[str, str]:
        """Resolve iOS attachment URL and content type."""
        url_template = ATTACHMENT_URL_TEMPLATES.get(
            rendered.media.still_kind,
            ATTACHMENT_URL_TEMPLATES["snapshot_cropped"],
        )
        url = render_template(hass, url_template, attachment_ctx)
        content_type = ATTACHMENT_CONTENT_TYPES.get(rendered.media.still_kind, "jpeg")

        # Video overrides attachment when set.
        if rendered.media.video_kind and rendered.media.video_kind != VideoType.NONE:
            video_tpl = VIDEO_URL_TEMPLATES.get(rendered.media.video_kind)
            if video_tpl:
                url = render_template(hass, video_tpl, attachment_ctx)
                content_type = VIDEO_CONTENT_TYPES.get(rendered.media.video_kind, "mp4")

        return url, content_type

    def _resolve_android_image(
        self,
        hass: HomeAssistant,
        rendered: RenderedNotification,
        attachment_ctx: Mapping[str, Any],
    ) -> str:
        """Resolve Android image URL (always still, with format=android)."""
        url_template = ANDROID_IMAGE_URL_TEMPLATES.get(
            rendered.media.still_kind,
            ANDROID_IMAGE_URL_TEMPLATES["snapshot_cropped"],
        )
        return render_template(hass, url_template, attachment_ctx)

    def _resolve_android_video(
        self,
        hass: HomeAssistant,
        rendered: RenderedNotification,
        attachment_ctx: Mapping[str, Any],
    ) -> str:
        """Resolve Android video URL (empty when no video)."""
        if not rendered.media.video_kind or rendered.media.video_kind == VideoType.NONE:
            return ""
        video_tpl = ANDROID_VIDEO_URL_TEMPLATES.get(rendered.media.video_kind)
        if not video_tpl:
            return ""
        return render_template(hass, video_tpl, attachment_ctx)

    def _build_actions(
        self,
        hass: HomeAssistant,
        profile: ProfileRuntime,
        action_ctx: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Build iOS/Android action buttons from action_config presets."""
        from ..action_presets import ACTION_PRESETS, resolve_uri_for_platform

        actions: list[dict[str, Any]] = []
        for action_cfg in profile.action_config:
            preset_id = action_cfg.get("preset", "none")

            preset = ACTION_PRESETS.get(preset_id, ACTION_PRESETS["none"])
            action_type = preset.get("type", "uri")

            if action_type == "none":
                continue

            if action_type == "silence":
                silence_id = f"silence-frigate_notifications:profile:{profile.profile_id}"
                actions.append(
                    {
                        "action": silence_id,
                        "title": action_cfg.get("title", preset.get("title", "")),
                        "uri": silence_id,
                        "icon": "",
                        "destructive": True,
                    }
                )
            elif action_type == "event":
                review_id = str(action_ctx.get("review_id", ""))
                event_id = (
                    f"custom-frigate_notifications:profile:{profile.profile_id}:review:{review_id}"
                )
                actions.append(
                    {
                        "action": event_id,
                        "title": action_cfg.get("title", preset.get("title", "")),
                        "icon": action_cfg.get("icon", preset.get("icon", "")),
                        "destructive": True,
                    }
                )
            elif action_type == "no_action":
                if resolved_platform(profile.provider) in ("android", "unknown"):
                    actions.append(
                        {
                            "action": "URI",
                            "title": action_cfg.get("title", preset.get("title", "")),
                            "uri": "noAction",
                            "icon": "",
                            "destructive": False,
                        }
                    )
            else:
                uri_tpl = resolve_uri_for_platform(
                    profile.provider,
                    preset,
                    override_uri=action_cfg.get("uri", ""),
                )
                actions.append(
                    {
                        "action": "URI",
                        "title": action_cfg.get("title", preset.get("title", "")),
                        "uri": render_template(hass, uri_tpl, action_ctx),
                        "icon": action_cfg.get("icon", preset.get("icon", "")),
                        "destructive": False,
                    }
                )
        return actions


def _build_sound_dict(
    phase: PhaseConfig,
    *,
    critical: bool = False,
    alert_once_silent: bool = False,
) -> dict[str, Any]:
    """Build the iOS push sound dict."""
    sound_dict: dict[str, Any] = {
        "name": phase.delivery.sound,
        "volume": phase.delivery.volume,
    }
    if critical:
        sound_dict["critical"] = 1
        sound_dict["volume"] = 1.0
    elif alert_once_silent:
        sound_dict["name"] = "none"
        sound_dict["volume"] = 0.0
    return sound_dict
