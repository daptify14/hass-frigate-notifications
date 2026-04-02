"""Android TV / Fire TV notification provider.

Produces overlay notifications with still images only.
Uses the separate "Notifications for Android TV" HA integration.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from ..const import ATTACHMENT_URL_TEMPLATES
from ..message_builder import render_template
from .models import AndroidTvConfig, NotifyCall, RenderedNotification

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..data import ProfileRuntime
    from ..models import Review

# GIF attachment types that must fall back to a still snapshot.
_GIF_KINDS = frozenset({"review_gif", "event_gif", "gif"})


class AndroidTvProvider:
    """Provider adapter for Android TV / Fire TV overlay notifications."""

    provider_id = "android_tv"

    def build_notify_call(
        self,
        hass: HomeAssistant,
        profile: ProfileRuntime,
        review: Review,
        rendered: RenderedNotification,
    ) -> NotifyCall:
        """Build a TV overlay NotifyCall (stills only, no actions)."""
        if not isinstance(profile.provider_config, AndroidTvConfig):
            msg = f"Expected AndroidTvConfig, got {type(profile.provider_config)}"
            raise TypeError(msg)
        phase = profile.get_phase(rendered.phase_name)
        ctx = rendered.ctx

        attachment_ctx = ctx
        if rendered.media.use_latest_detection and ctx.get("latest_detection_id"):
            attachment_ctx = {**ctx, "detection_id": ctx["latest_detection_id"]}

        image_url = self._resolve_still_image(hass, rendered, attachment_ctx)

        data: dict[str, Any] = {
            "image": {"url": image_url},
            "fontsize": phase.tv.fontsize,
            "position": phase.tv.position,
            "duration": phase.tv.duration,
            "transparency": phase.tv.transparency,
            "interrupt": phase.tv.interrupt,
            "timeout": phase.tv.timeout,
        }

        if phase.tv.color:
            data["color"] = phase.tv.color

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

    def _resolve_still_image(
        self,
        hass: HomeAssistant,
        rendered: RenderedNotification,
        attachment_ctx: Mapping[str, Any],
    ) -> str:
        """Resolve a still image URL, falling back from GIF to snapshot."""
        still_kind = rendered.media.still_kind
        if still_kind in _GIF_KINDS:
            still_kind = "snapshot_cropped"
        url_template = ATTACHMENT_URL_TEMPLATES.get(
            still_kind, ATTACHMENT_URL_TEMPLATES["snapshot_cropped"]
        )
        return render_template(hass, url_template, attachment_ctx)
