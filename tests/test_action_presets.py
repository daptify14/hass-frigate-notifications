"""Tests for action_presets module."""

import logging

import pytest

from custom_components.frigate_notifications.action_presets import (
    ACTION_PRESETS,
    TAP_ACTION_OPTIONS,
    resolve_tap_url,
)
from custom_components.frigate_notifications.enums import Provider

from .factories import make_profile


class TestSelectorHelpers:
    """Tests for config flow selector helpers."""

    def test_tap_action_options_excludes_non_uri(self) -> None:
        """TAP_ACTION_OPTIONS excludes silence, custom_action, none."""
        excluded = {"silence", "custom_action", "none"}
        for pid in TAP_ACTION_OPTIONS:
            assert pid not in excluded
            assert pid in ACTION_PRESETS


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
        profile = make_profile(tap_action={"preset": "no_action"})
        result = resolve_tap_url(profile, {})
        assert result == "noAction"

    def test_custom_uri_override(self) -> None:
        """Custom URI override is used when present in tap_action."""
        profile = make_profile(tap_action={"preset": "view_clip", "uri": "{{ base_url }}/custom"})
        result = resolve_tap_url(profile, {"base_url": "https://ha.test"})
        assert result == "https://ha.test/custom"

    def test_unknown_preset_returns_noaction_and_warns(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Unknown preset ID degrades to noAction with warning."""
        profile = make_profile(
            provider=Provider.APPLE,
            tap_action={"preset": "nonexistent"},
        )
        with caplog.at_level(logging.WARNING):
            result = resolve_tap_url(profile, _BASE_CTX)
        assert result == "noAction"
        assert "Unknown tap_action preset nonexistent; using noAction" in caplog.text

    def test_template_variables_substituted(self) -> None:
        """Template variables are fully substituted."""
        profile = make_profile(provider=Provider.APPLE)
        ctx = {
            "base_url": "https://ha.test",
            "client_id": "/inst1",
            "detection_id": "det1",
            "camera": "front",
            "review_id": "rev1",
        }
        result = resolve_tap_url(profile, ctx)
        expected = "https://ha.test/api/frigate/inst1/notifications/det1/front/master.m3u8"
        assert result == expected

    def test_non_uri_preset_returns_noaction_and_warns(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Non-URI preset type degrades to noAction with warning."""
        profile = make_profile(
            provider=Provider.APPLE,
            tap_action={"preset": "silence"},
        )
        with caplog.at_level(logging.WARNING):
            result = resolve_tap_url(profile, _BASE_CTX)
        assert result == "noAction"
        assert (
            "Unsupported tap_action preset type silence for preset silence; using noAction"
            in caplog.text
        )

    def test_view_stream_includes_access_token(self) -> None:
        """view_stream preset uses access_token from pre-enriched context."""
        profile = make_profile(tap_action={"preset": "view_stream"})
        ctx = {**_BASE_CTX, "access_token": "tok123"}
        result = resolve_tap_url(profile, ctx)
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
        profile = make_profile(provider=provider)
        result = resolve_tap_url(profile, _BASE_CTX)
        assert expected_fragment in result
