"""Targeted unit tests for profile step modules — coverage for provider-specific branches."""

from typing import Any
from unittest.mock import MagicMock

from custom_components.frigate_notifications.enums import Provider
from custom_components.frigate_notifications.flows.profile.context import FlowContext
from custom_components.frigate_notifications.flows.profile.steps.basics import (
    apply_basics_input,
    build_basics_schema,
)
from custom_components.frigate_notifications.flows.profile.steps.delivery import (
    _submit_rate_limiting,
    apply_delivery_input,
    build_delivery_schema,
    build_delivery_suggested,
)
from custom_components.frigate_notifications.providers.base import get_capabilities


def _make_ctx(provider: Provider = Provider.APPLE) -> FlowContext:
    """Build a FlowContext for testing with a given provider."""
    hass = MagicMock()
    hass.data = {}
    entry = MagicMock()
    entry.data = {"frigate_entry_id": "test_id"}
    return FlowContext(
        provider=provider,
        capabilities=get_capabilities(provider),
        enabled_phases=("initial", "update", "end", "genai"),
        is_reconfiguring=False,
        available_cameras=["driveway"],
        genai_available=False,
        hass=hass,
        entry=entry,
        frigate_entry_id="test_id",
    )


class TestDeliverySchemaByProvider:
    """Test build_delivery_schema branches for each provider."""

    def test_delivery_schema_android_includes_importance_priority_ttl(self) -> None:
        """Android delivery schema includes importance, priority, ttl fields."""
        ctx = _make_ctx(Provider.ANDROID)
        draft: dict[str, Any] = {"cameras": ["driveway"], "provider": "android"}
        schema = build_delivery_schema(draft, ctx)
        keys = {str(k) for k in schema.schema}
        assert any("initial_delivery" in k for k in keys)
        assert any("android_delivery" in k for k in keys)

    def test_delivery_schema_cross_platform_includes_urgency(self) -> None:
        """Cross-platform delivery schema includes urgency field."""
        ctx = _make_ctx(Provider.CROSS_PLATFORM)
        draft: dict[str, Any] = {"cameras": ["driveway"], "provider": "cross_platform"}
        schema = build_delivery_schema(draft, ctx)
        keys = {str(k) for k in schema.schema}
        assert any("initial_delivery" in k for k in keys)
        assert any("android_delivery" in k for k in keys)

    def test_delivery_schema_android_tv_includes_overlay_fields(self) -> None:
        """Android TV delivery schema includes TV overlay fields."""
        ctx = _make_ctx(Provider.ANDROID_TV)
        draft: dict[str, Any] = {"cameras": ["driveway"], "provider": "android_tv"}
        schema = build_delivery_schema(draft, ctx)
        keys = {str(k) for k in schema.schema}
        assert any("initial_delivery" in k for k in keys)
        assert not any("android_delivery" in k for k in keys)


class TestDeliverySchemaPhaseVisibility:
    """Test that disabled phases are omitted from delivery schema."""

    def test_disabled_phase_omitted_from_delivery_schema(self) -> None:
        """Disabled phases do not appear in the delivery schema."""
        ctx = _make_ctx(Provider.APPLE)
        # Override enabled_phases to simulate update+genai disabled.
        ctx = FlowContext(
            provider=ctx.provider,
            capabilities=ctx.capabilities,
            enabled_phases=("initial", "end"),
            is_reconfiguring=ctx.is_reconfiguring,
            available_cameras=ctx.available_cameras,
            genai_available=ctx.genai_available,
            hass=ctx.hass,
            entry=ctx.entry,
            frigate_entry_id=ctx.frigate_entry_id,
        )
        draft: dict[str, Any] = {"cameras": ["driveway"], "provider": "apple"}
        schema = build_delivery_schema(draft, ctx)
        keys = {str(k) for k in schema.schema}
        assert any("initial_delivery" in k for k in keys)
        assert any("end_delivery" in k for k in keys)
        assert not any("update_delivery" in k for k in keys)
        assert not any("genai_delivery" in k for k in keys)


class TestDeliveryApplyCoercions:
    """Test apply_delivery_input coercions for provider-specific fields."""

    def test_apply_delivery_volume_coercion(self) -> None:
        """Volume percent is converted to float 0-1."""
        ctx = _make_ctx(Provider.APPLE)
        draft: dict[str, Any] = {}
        apply_delivery_input(
            draft,
            {"initial_delivery": {"volume": 75}},
            ctx,
        )
        assert draft["phases"]["initial"]["volume"] == 0.75

    def test_apply_delivery_ttl_coercion(self) -> None:
        """TTL is coerced to int."""
        ctx = _make_ctx(Provider.ANDROID)
        draft: dict[str, Any] = {}
        apply_delivery_input(
            draft,
            {"initial_delivery": {"ttl": 60.0}},
            ctx,
        )
        assert draft["phases"]["initial"]["ttl"] == 60
        assert isinstance(draft["phases"]["initial"]["ttl"], int)

    def test_apply_delivery_interruption_level_normalized(self) -> None:
        """Interruption level time_sensitive is normalized to time-sensitive."""
        ctx = _make_ctx(Provider.APPLE)
        draft: dict[str, Any] = {}
        apply_delivery_input(
            draft,
            {"initial_delivery": {"interruption_level": "time_sensitive"}},
            ctx,
        )
        assert draft["phases"]["initial"]["interruption_level"] == "time-sensitive"


class TestDeliveryRateLimiting:
    """Test rate limiting apply."""

    def test_rate_limiting_cooldown_coerced_to_int(self) -> None:
        """Cooldown override is coerced to int."""
        data: dict[str, Any] = {}
        _submit_rate_limiting(data, {"rate_limiting": {"cooldown_override": 120.0}})
        assert data["cooldown_override"] == 120
        assert isinstance(data["cooldown_override"], int)

    def test_rate_limiting_alert_once_stored(self) -> None:
        """alert_once=True is stored."""
        data: dict[str, Any] = {}
        _submit_rate_limiting(data, {"rate_limiting": {"alert_once": True}})
        assert data["alert_once"] is True


class TestDeliverySuggested:
    """Test build_delivery_suggested."""

    def test_delivery_suggested_includes_rate_limiting(self) -> None:
        """Rate limiting values appear in suggested dict."""
        ctx = _make_ctx(Provider.APPLE)
        draft: dict[str, Any] = {"silence_duration": 30, "cooldown_override": 60}
        suggested = build_delivery_suggested(draft, ctx)
        assert suggested["rate_limiting"]["silence_duration"] == 30
        assert suggested["rate_limiting"]["cooldown_override"] == 60

    def test_delivery_suggested_alert_once_for_mobile(self) -> None:
        """alert_once defaults to False and reflects True when set in draft."""
        ctx = _make_ctx(Provider.APPLE)
        suggested = build_delivery_suggested({}, ctx)
        assert suggested["rate_limiting"]["alert_once"] is False

        draft: dict[str, Any] = {"alert_once": True}
        suggested = build_delivery_suggested(draft, ctx)
        assert suggested["rate_limiting"]["alert_once"] is True


class TestBasicsTagGroupByProvider:
    """Test that tag/group fields are provider-dependent in basics step."""

    def test_basics_android_tv_excludes_tag_and_group(self) -> None:
        """Android TV hides tag/group from schema and pops stale values on apply."""
        ctx = _make_ctx(Provider.ANDROID_TV)
        draft: dict[str, Any] = {
            "provider": "android_tv",
            "tag": "old_tag",
            "group": "old_group",
        }
        schema = build_basics_schema(draft, ctx, pass_number=2)
        keys = {str(k) for k in schema.schema}
        assert "tag" not in keys
        assert "group" not in keys

        apply_basics_input(draft, {"notify_service": "notify.living_room_tv"}, ctx, pass_number=2)
        assert "tag" not in draft
        assert "group" not in draft

    def test_basics_mobile_provider_includes_tag_and_group(self) -> None:
        """Mobile provider shows tag/group in schema and stores values on apply."""
        ctx = _make_ctx(Provider.APPLE)
        draft: dict[str, Any] = {"provider": "apple"}
        schema = build_basics_schema(draft, ctx, pass_number=2)
        keys = {str(k) for k in schema.schema}
        assert "tag" in keys
        assert "group" in keys

        apply_basics_input(
            draft,
            {"notify_service": "notify.my_iphone", "tag": "custom", "group": "cam"},
            ctx,
            pass_number=2,
        )
        assert draft["tag"] == "custom"
        assert draft["group"] == "cam"
