"""Tests for enum definitions."""

import pytest

from custom_components.frigate_notifications.enums import (
    Provider,
    ProviderFamily,
    provider_family,
    resolved_platform,
)
from custom_components.frigate_notifications.providers.base import (
    PROVIDER_FAMILY_CAPABILITIES,
    get_capabilities,
)


class TestProviderFamily:
    """Tests for provider_family() mapping."""

    @pytest.mark.parametrize(
        ("provider", "expected"),
        [
            (Provider.APPLE, ProviderFamily.MOBILE_APP),
            (Provider.ANDROID, ProviderFamily.MOBILE_APP),
            (Provider.CROSS_PLATFORM, ProviderFamily.MOBILE_APP),
            (Provider.ANDROID_TV, ProviderFamily.ANDROID_TV),
        ],
    )
    def test_provider_family_mapping(self, provider: Provider, expected: ProviderFamily) -> None:
        assert provider_family(provider) == expected


class TestResolvedPlatform:
    """Tests for resolved_platform() mapping."""

    @pytest.mark.parametrize(
        ("provider", "expected"),
        [
            (Provider.APPLE, "ios"),
            (Provider.ANDROID, "android"),
            (Provider.CROSS_PLATFORM, "unknown"),
            (Provider.ANDROID_TV, "android_tv"),
        ],
    )
    def test_resolved_platform_mapping(self, provider: Provider, expected: str) -> None:
        assert resolved_platform(provider) == expected


class TestProviderCapabilities:
    """Tests for capability map and get_capabilities()."""

    def test_mobile_app_capabilities_defaults(self) -> None:
        """MOBILE_APP family has full capabilities."""
        caps = get_capabilities(Provider.APPLE)
        assert caps.supports_video is True
        assert caps.supports_action_presets is True
        assert caps.supports_alert_once is True
        assert caps.max_actions == 3
        assert caps.media_variant == "mobile_app"
        assert caps.delivery_variant == "mobile_app"

    def test_android_tv_capabilities_restricted(self) -> None:
        """ANDROID_TV family has restricted capabilities."""
        caps = get_capabilities(Provider.ANDROID_TV)
        assert caps.supports_video is False
        assert caps.supports_action_presets is False
        assert caps.supports_custom_actions is False
        assert caps.supports_alert_once is False
        assert caps.max_actions == 0
        assert caps.media_variant == "android_tv"
        assert caps.delivery_variant == "tv_overlay"

    def test_all_families_covered(self) -> None:
        """Every ProviderFamily has a capability entry."""
        for family in ProviderFamily:
            assert family in PROVIDER_FAMILY_CAPABILITIES
