"""Tests for notification providers."""

from homeassistant.core import HomeAssistant
import pytest

from custom_components.frigate_notifications.config import (
    AndroidTvOverlay,
    PhaseConfig,
)
from custom_components.frigate_notifications.enums import AttachmentType, Phase, Provider, VideoType
from custom_components.frigate_notifications.providers.android_tv import AndroidTvProvider
from custom_components.frigate_notifications.providers.base import get_provider
from custom_components.frigate_notifications.providers.mobile_app import MobileAppProvider
from custom_components.frigate_notifications.providers.models import (
    AndroidTvConfig,
    MobileAppConfig,
    NotifyCall,
    RenderedMedia,
    RenderedNotification,
)

from .factories import make_profile, make_review


def _make_rendered(
    *,
    phase_name: Phase = Phase.INITIAL,
    still_kind: AttachmentType = AttachmentType.SNAPSHOT_CROPPED,
    video_kind: VideoType = VideoType.NONE,
    use_latest_detection: bool = False,
    alert_once_silent: bool = False,
    critical: bool = False,
    click_url: str = "noAction",
) -> RenderedNotification:
    """Build a RenderedNotification with minimal defaults."""
    ctx: dict[str, str] = {
        "base_url": "https://hass.test",
        "client_id": "",
        "detection_id": "det1",
        "review_id": "rev1",
        "camera": "driveway",
        "latest_detection_id": "det2",
    }
    attachment_ctx = ctx
    if use_latest_detection and ctx.get("latest_detection_id"):
        attachment_ctx = {**ctx, "detection_id": ctx["latest_detection_id"]}
    action_ctx = {**ctx, "access_token": ""}
    return RenderedNotification(
        title="Test Title",
        message="Test Message",
        subtitle="Test Subtitle",
        tag="test-tag",
        group="test-group",
        click_url=click_url,
        alert_once_silent=alert_once_silent,
        critical=critical,
        phase_name=phase_name,
        media=RenderedMedia(
            still_kind=still_kind,
            video_kind=video_kind,
            use_latest_detection=use_latest_detection,
        ),
        ctx=ctx,
        attachment_ctx=attachment_ctx,
        action_ctx=action_ctx,
    )


@pytest.mark.parametrize(
    ("provider", "expected_type"),
    [
        (Provider.APPLE, MobileAppProvider),
        (Provider.ANDROID, MobileAppProvider),
        (Provider.CROSS_PLATFORM, MobileAppProvider),
        (Provider.ANDROID_TV, AndroidTvProvider),
    ],
)
def test_get_provider_returns_correct_type(provider: Provider, expected_type: type) -> None:
    assert isinstance(get_provider(provider), expected_type)


class TestMobileAppProvider:
    @pytest.mark.parametrize(
        ("target", "expected_service"),
        [
            ("notify.mobile_app_iphone", "mobile_app_iphone"),
            ("mobile_app_phone", "mobile_app_phone"),
        ],
        ids=["strips-prefix", "no-prefix"],
    )
    def test_service_name_resolution(
        self, target: str, expected_service: str, hass: HomeAssistant
    ) -> None:
        provider = MobileAppProvider()
        profile = make_profile(notify_target=target)
        call = provider.build_notify_call(hass, profile, make_review(), _make_rendered())
        assert call.service == expected_service

    def test_image_attachment_urls(self, hass: HomeAssistant) -> None:
        """Notify call includes iOS attachment and Android image URL."""
        provider = MobileAppProvider()
        call = provider.build_notify_call(hass, make_profile(), make_review(), _make_rendered())
        data = call.service_data["data"]
        # iOS attachment
        assert "attachment" in data
        assert data["attachment"]["content-type"] == "jpeg"
        assert "snapshot.jpg" in data["attachment"]["url"]
        # Android image
        assert "image" in data
        assert "format=android" in data["image"]

    def test_ios_sound_default(self, hass: HomeAssistant) -> None:
        provider = MobileAppProvider()
        call = provider.build_notify_call(hass, make_profile(), make_review(), _make_rendered())
        sound = call.service_data["data"]["push"]["sound"]
        assert sound["name"] == "default"
        assert sound["volume"] == 1.0

    def test_alert_once_silent_forces_no_sound(self, hass: HomeAssistant) -> None:
        provider = MobileAppProvider()
        rendered = _make_rendered(alert_once_silent=True)
        call = provider.build_notify_call(hass, make_profile(), make_review(), rendered)
        sound = call.service_data["data"]["push"]["sound"]
        assert sound["name"] == "none"
        assert sound["volume"] == 0.0

    def test_critical_forces_loud_sound(self, hass: HomeAssistant) -> None:
        provider = MobileAppProvider()
        rendered = _make_rendered(critical=True)
        call = provider.build_notify_call(hass, make_profile(), make_review(), rendered)
        sound = call.service_data["data"]["push"]["sound"]
        assert sound["critical"] == 1
        assert sound["volume"] == 1.0
        assert call.service_data["data"]["push"]["interruption-level"] == "critical"
        data = call.service_data["data"]
        assert data["channel"] == "alarm_stream"
        assert data["priority"] == "high"
        assert data["ttl"] == 0

    def test_android_keys_present(self, hass: HomeAssistant) -> None:
        provider = MobileAppProvider()
        call = provider.build_notify_call(hass, make_profile(), make_review(), _make_rendered())
        data = call.service_data["data"]
        assert "clickAction" in data
        assert "channel" in data
        assert "importance" in data
        assert "sticky" in data
        assert "persistent" in data
        assert "car_ui" in data

    def test_alert_once_android_flag(self, hass: HomeAssistant) -> None:
        provider = MobileAppProvider()
        profile = make_profile(alert_once=True)
        call = provider.build_notify_call(hass, profile, make_review(), _make_rendered())
        assert call.service_data["data"]["alert_once"] is True

    def test_video_kind_sets_ios_video(self, hass: HomeAssistant) -> None:
        provider = MobileAppProvider()
        rendered = _make_rendered(video_kind=VideoType.CLIP_MP4)
        call = provider.build_notify_call(hass, make_profile(), make_review(), rendered)
        data = call.service_data["data"]
        assert "clip.mp4" in data["attachment"]["url"]
        assert data["attachment"]["content-type"] == "mp4"
        assert "video" in data
        assert "clip.mp4" in data["video"]

    def test_use_latest_detection_swaps_id(self, hass: HomeAssistant) -> None:
        provider = MobileAppProvider()
        rendered = _make_rendered(use_latest_detection=True)
        call = provider.build_notify_call(hass, make_profile(), make_review(), rendered)
        data = call.service_data["data"]
        # Should use latest_detection_id (det2) not detection_id (det1)
        assert "det2" in data["attachment"]["url"]

    def test_actions_from_presets(self, hass: HomeAssistant) -> None:
        provider = MobileAppProvider()
        profile = make_profile(
            action_config=(
                {"preset": "view_clip"},
                {"preset": "silence"},
            ),
        )
        call = provider.build_notify_call(hass, profile, make_review(), _make_rendered())
        actions = call.service_data["data"]["actions"]
        assert len(actions) == 2
        assert actions[0]["action"] == "URI"
        assert "silence-frigate_notifications" in actions[1]["action"]

    def test_color_included_when_set(self, hass: HomeAssistant) -> None:
        provider = MobileAppProvider()
        profile = make_profile(provider_config=MobileAppConfig(color="#FF0000"))
        call = provider.build_notify_call(hass, profile, make_review(), _make_rendered())
        assert call.service_data["data"]["color"] == "#FF0000"

    def test_review_gif_video_uses_mp4_format(self, hass: HomeAssistant) -> None:
        """review_gif_video requests MP4 from Frigate and sets mp4 content-type."""
        provider = MobileAppProvider()
        rendered = _make_rendered(video_kind=VideoType.REVIEW_GIF_VIDEO)
        call = provider.build_notify_call(hass, make_profile(), make_review(), rendered)
        data = call.service_data["data"]
        # iOS: Frigate serves MP4 via ?format=mp4
        assert "review_preview.gif?format=mp4" in data["attachment"]["url"]
        assert data["attachment"]["content-type"] == "mp4"
        # Android: also gets MP4 URL
        assert "review_preview.gif?format=mp4" in data["video"]

    def test_android_gif_image_no_format_param(self, hass: HomeAssistant) -> None:
        """GIF attachment URLs for Android omit ?format=android (only valid on JPEGs)."""
        provider = MobileAppProvider()
        rendered = _make_rendered(still_kind=AttachmentType.REVIEW_GIF)
        call = provider.build_notify_call(hass, make_profile(), make_review(), rendered)
        data = call.service_data["data"]
        assert "review_preview.gif" in data["image"]
        assert "format=android" not in data["image"]

    def test_no_video_omits_android_video(self, hass: HomeAssistant) -> None:
        """video_kind=none means no 'video' key in Android data."""
        provider = MobileAppProvider()
        rendered = _make_rendered(video_kind=VideoType.NONE)
        call = provider.build_notify_call(hass, make_profile(), make_review(), rendered)
        assert "video" not in call.service_data["data"]

    def test_live_view_sets_entity_id(self, hass: HomeAssistant) -> None:
        """live_view video kind injects entity_id for iOS live camera stream."""
        provider = MobileAppProvider()
        rendered = _make_rendered(video_kind=VideoType.LIVE_VIEW)
        call = provider.build_notify_call(hass, make_profile(), make_review(), rendered)
        assert call.service_data["data"]["entity_id"] == "camera.driveway"

    def test_live_view_preserves_still_attachment(self, hass: HomeAssistant) -> None:
        """live_view does not override the still attachment (no URL template exists)."""
        provider = MobileAppProvider()
        rendered = _make_rendered(video_kind=VideoType.LIVE_VIEW)
        call = provider.build_notify_call(hass, make_profile(), make_review(), rendered)
        data = call.service_data["data"]
        assert data["attachment"]["content-type"] == "jpeg"
        assert "snapshot" in data["attachment"]["url"]

    def test_live_view_omits_android_video(self, hass: HomeAssistant) -> None:
        """live_view has no Android video template, so no 'video' key."""
        provider = MobileAppProvider()
        rendered = _make_rendered(video_kind=VideoType.LIVE_VIEW)
        call = provider.build_notify_call(hass, make_profile(), make_review(), rendered)
        assert "video" not in call.service_data["data"]

    def test_action_type_event(self, hass: HomeAssistant) -> None:
        """custom_action preset produces an event-type action."""
        provider = MobileAppProvider()
        profile = make_profile(action_config=({"preset": "custom_action"},))
        call = provider.build_notify_call(hass, profile, make_review(), _make_rendered())
        actions = call.service_data["data"]["actions"]
        assert len(actions) == 1
        assert actions[0]["action"].startswith("custom-frigate_notifications:")
        assert ":review:" in actions[0]["action"]

    def test_action_type_none_skipped(self, hass: HomeAssistant) -> None:
        """Action preset 'none' produces no action entry."""
        provider = MobileAppProvider()
        profile = make_profile(action_config=({"preset": "none"},))
        call = provider.build_notify_call(hass, profile, make_review(), _make_rendered())
        actions = call.service_data["data"]["actions"]
        assert len(actions) == 0

    def test_action_type_no_action_android(self, hass: HomeAssistant) -> None:
        """no_action preset produces a URI noAction for android provider."""
        provider = MobileAppProvider()
        profile = make_profile(
            provider=Provider.ANDROID,
            action_config=({"preset": "no_action"},),
        )
        call = provider.build_notify_call(hass, profile, make_review(), _make_rendered())
        actions = call.service_data["data"]["actions"]
        assert len(actions) == 1
        assert actions[0]["uri"] == "noAction"

    def test_action_type_no_action_ios_skipped(self, hass: HomeAssistant) -> None:
        """no_action preset is skipped for iOS provider."""
        provider = MobileAppProvider()
        profile = make_profile(
            provider=Provider.APPLE,
            action_config=({"preset": "no_action"},),
        )
        call = provider.build_notify_call(hass, profile, make_review(), _make_rendered())
        actions = call.service_data["data"]["actions"]
        assert len(actions) == 0


class TestAndroidTvProvider:
    def test_basic_call_structure(self, hass: HomeAssistant) -> None:
        provider = AndroidTvProvider()
        profile = make_profile(
            notify_target="notify.fire_tv_stick",
            provider=Provider.ANDROID_TV,
            provider_config=AndroidTvConfig(),
        )
        call = provider.build_notify_call(hass, profile, make_review(), _make_rendered())
        assert isinstance(call, NotifyCall)
        assert call.service == "fire_tv_stick"
        assert call.service_data["title"] == "Test Title"
        assert "actions" not in call.service_data["data"]
        assert "color" not in call.service_data["data"]

    def test_stills_only_no_gif(self, hass: HomeAssistant) -> None:
        """GIF attachment types fall back to snapshot_cropped."""
        provider = AndroidTvProvider()
        profile = make_profile(
            provider=Provider.ANDROID_TV,
            provider_config=AndroidTvConfig(),
        )
        rendered = _make_rendered(still_kind=AttachmentType.REVIEW_GIF)
        call = provider.build_notify_call(hass, profile, make_review(), rendered)
        data = call.service_data["data"]
        assert "snapshot.jpg" in data["image"]["url"]

    def test_overlay_settings_from_phase(self, hass: HomeAssistant) -> None:
        provider = AndroidTvProvider()
        profile = make_profile(
            provider=Provider.ANDROID_TV,
            provider_config=AndroidTvConfig(),
        )
        call = provider.build_notify_call(hass, profile, make_review(), _make_rendered())
        data = call.service_data["data"]
        assert data["fontsize"] == "medium"
        assert data["position"] == "bottom-right"
        assert data["duration"] == 5

    def test_use_latest_detection(self, hass: HomeAssistant) -> None:
        provider = AndroidTvProvider()
        profile = make_profile(
            provider=Provider.ANDROID_TV,
            provider_config=AndroidTvConfig(),
        )
        rendered = _make_rendered(use_latest_detection=True)
        call = provider.build_notify_call(hass, profile, make_review(), rendered)
        assert "det2" in call.service_data["data"]["image"]["url"]

    def test_color_included_when_set(self, hass: HomeAssistant) -> None:
        """TV color is included in data when phase.tv.color is non-empty."""
        provider = AndroidTvProvider()
        color_phase = PhaseConfig(tv=AndroidTvOverlay(color="#FF0000"))
        profile = make_profile(
            provider=Provider.ANDROID_TV,
            provider_config=AndroidTvConfig(),
            phases={Phase.INITIAL: color_phase},
        )
        call = provider.build_notify_call(hass, profile, make_review(), _make_rendered())
        assert call.service_data["data"]["color"] == "#FF0000"
