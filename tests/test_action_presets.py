"""Tests for action_presets module."""

import logging

import pytest

from custom_components.frigate_notifications.action_presets import (
    ACTION_PRESETS,
    CUSTOM_URL_PRESET,
    TAP_ACTION_OPTIONS,
    is_valid_tap_url,
    resolve_tap_url,
)
from custom_components.frigate_notifications.enums import Provider


class TestSelectorHelpers:
    """Tests for config flow selector helpers."""

    def test_tap_action_options_excludes_non_uri(self) -> None:
        """TAP_ACTION_OPTIONS excludes silence, custom_action, none."""
        excluded = {"silence", "custom_action", "none"}
        for pid in TAP_ACTION_OPTIONS:
            assert pid not in excluded
            assert pid in ACTION_PRESETS or pid == CUSTOM_URL_PRESET


class TestIsValidTapUrl:
    """Tests for is_valid_tap_url."""

    @pytest.mark.parametrize(
        "value",
        ["/dashboard-cameras/live", "/lovelace", "https://ha.test/x", "http://10.0.0.5:8123"],
    )
    def test_accepts_paths_and_http_urls(self, value: str) -> None:
        assert is_valid_tap_url(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "//evil.test/x",
            "/\\evil.test/x",
            "/cams/live\n",
            "dashboard/live",
            "ftp://ha.test",
            "https://",
            "https://?x=1",
            "http://[bad",
            "javascript:alert(1)",
            "app://com.example.app",
        ],
    )
    def test_rejects_other_values(self, value: str) -> None:
        assert is_valid_tap_url(value) is False


_BASE_CTX: dict[str, str] = {
    "base_url": "https://ha.test",
    "client_id": "",
    "detection_id": "det1",
    "camera": "driveway",
    "review_id": "rev1",
}


class TestResolveTapUrl:
    """Tests for resolve_tap_url."""

    def test_no_action_returns_noaction(self) -> None:
        """no_action preset returns 'noAction'."""
        result = resolve_tap_url({"preset": "no_action"}, Provider.APPLE, {})
        assert result == "noAction"

    def test_none_config_uses_view_clip(self) -> None:
        """A missing tap config falls back to the View Clip preset."""
        result = resolve_tap_url(None, Provider.ANDROID, _BASE_CTX)
        assert result.endswith("/det1/driveway/clip.mp4")

    def test_custom_uri_override(self) -> None:
        """Custom URI override is used when present in tap_action."""
        tap = {"preset": "view_clip", "uri": "{{ base_url }}/custom"}
        result = resolve_tap_url(tap, Provider.APPLE, {"base_url": "https://ha.test"})
        assert result == "https://ha.test/custom"

    def test_custom_url_preset_returns_stored_path(self) -> None:
        """Custom URL preset returns its stored path unchanged."""
        tap = {"preset": CUSTOM_URL_PRESET, "uri": "/cams/live"}
        assert resolve_tap_url(tap, Provider.APPLE, _BASE_CTX) == "/cams/live"

    @pytest.mark.parametrize("uri", ["/{{", '/{{ "/evil.test" }}'])
    def test_custom_url_preset_is_not_templated(self, uri: str) -> None:
        """Custom URL text is returned literally, never rendered as a template."""
        tap = {"preset": CUSTOM_URL_PRESET, "uri": uri}
        assert resolve_tap_url(tap, Provider.APPLE, _BASE_CTX) == uri

    def test_custom_url_preset_without_url_returns_noaction_and_warns(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Custom URL preset with no stored URL degrades to noAction."""
        with caplog.at_level(logging.WARNING):
            result = resolve_tap_url({"preset": CUSTOM_URL_PRESET}, Provider.APPLE, _BASE_CTX)
        assert result == "noAction"
        assert "Custom URL tap_action has no URL; using noAction" in caplog.text

    def test_unknown_preset_returns_noaction_and_warns(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Unknown preset ID degrades to noAction with warning."""
        with caplog.at_level(logging.WARNING):
            result = resolve_tap_url({"preset": "nonexistent"}, Provider.APPLE, _BASE_CTX)
        assert result == "noAction"
        assert "Unknown tap_action preset nonexistent; using noAction" in caplog.text

    def test_template_variables_substituted(self) -> None:
        """Template variables are fully substituted."""
        ctx = {
            "base_url": "https://ha.test",
            "client_id": "/inst1",
            "detection_id": "det1",
            "camera": "front",
            "review_id": "rev1",
        }
        result = resolve_tap_url({"preset": "view_clip"}, Provider.APPLE, ctx)
        expected = "https://ha.test/api/frigate/inst1/notifications/det1/front/master.m3u8"
        assert result == expected

    def test_non_uri_preset_returns_noaction_and_warns(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Non-URI preset type degrades to noAction with warning."""
        with caplog.at_level(logging.WARNING):
            result = resolve_tap_url({"preset": "silence"}, Provider.APPLE, _BASE_CTX)
        assert result == "noAction"
        assert (
            "Unsupported tap_action preset type silence for preset silence; using noAction"
            in caplog.text
        )

    def test_view_stream_includes_access_token(self) -> None:
        """view_stream preset uses access_token from pre-enriched context."""
        ctx = {**_BASE_CTX, "access_token": "tok123"}
        result = resolve_tap_url({"preset": "view_stream"}, Provider.APPLE, ctx)
        assert "token=tok123" in result
        assert "camera_proxy_stream/camera.driveway" in result

    @pytest.mark.parametrize(
        ("provider", "expected_fragment"),
        [
            (Provider.APPLE, "master.m3u8"),
            (Provider.ANDROID, "clip.mp4"),
            (Provider.CROSS_PLATFORM, "master.m3u8"),
            (Provider.ANDROID_TV, "master.m3u8"),
        ],
    )
    def test_provider_uri_selection(self, provider: Provider, expected_fragment: str) -> None:
        """Each provider selects the correct URI variant."""
        result = resolve_tap_url({"preset": "view_clip"}, provider, _BASE_CTX)
        assert expected_fragment in result
