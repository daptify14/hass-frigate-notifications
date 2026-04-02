"""Provider factory, capability map, and protocol for notification delivery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from ..enums import Provider, ProviderFamily, provider_family

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..data import ProfileRuntime
    from ..models import Review
    from .models import NotifyCall, RenderedNotification


class NotificationProvider(Protocol):
    """Protocol that all notification providers implement."""

    provider_id: str

    def build_notify_call(
        self,
        hass: HomeAssistant,
        profile: ProfileRuntime,
        review: Review,
        rendered: RenderedNotification,
    ) -> NotifyCall:
        """Build the service call data for a notification."""
        ...


@dataclass(frozen=True)
class ProviderFamilyCapabilities:
    """Capabilities for a provider family."""

    supports_device_target: bool = True
    supports_service_target: bool = True
    supports_action_presets: bool = True
    supports_custom_actions: bool = True
    supports_video: bool = True
    supports_alert_once: bool = True
    media_variant: str = "mobile_app"
    delivery_variant: str = "mobile_app"
    max_actions: int = 3


PROVIDER_FAMILY_CAPABILITIES: dict[ProviderFamily, ProviderFamilyCapabilities] = {
    ProviderFamily.MOBILE_APP: ProviderFamilyCapabilities(),
    ProviderFamily.ANDROID_TV: ProviderFamilyCapabilities(
        supports_device_target=False,
        supports_service_target=True,
        supports_action_presets=False,
        supports_custom_actions=False,
        supports_video=False,
        supports_alert_once=False,
        media_variant="android_tv",
        delivery_variant="tv_overlay",
        max_actions=0,
    ),
}


def get_capabilities(provider: Provider) -> ProviderFamilyCapabilities:
    """Return the capabilities for a provider's family."""
    return PROVIDER_FAMILY_CAPABILITIES[provider_family(provider)]


def get_provider(provider: Provider) -> NotificationProvider:
    """Return the correct provider adapter for the given provider type."""
    from .android_tv import AndroidTvProvider
    from .mobile_app import MobileAppProvider

    family = provider_family(provider)
    if family == ProviderFamily.MOBILE_APP:
        return MobileAppProvider()
    if family == ProviderFamily.ANDROID_TV:
        return AndroidTvProvider()
    msg = f"Unknown provider family: {family!r}"
    raise ValueError(msg)
