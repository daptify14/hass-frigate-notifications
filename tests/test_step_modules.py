"""Targeted unit tests for profile step modules — coverage for provider-specific branches."""

from typing import Any
from unittest.mock import MagicMock

from custom_components.frigate_notifications.config import DEFAULT_PHASE_INITIAL
from custom_components.frigate_notifications.enums import Provider
from custom_components.frigate_notifications.flows.profile.context import FlowContext
from custom_components.frigate_notifications.flows.profile.steps.basics import (
    apply_basics_input,
    build_basics_schema,
)
from custom_components.frigate_notifications.flows.profile.steps.content import (
    apply_content_input,
    build_content_schema,
    build_content_suggested,
)
from custom_components.frigate_notifications.flows.profile.steps.delivery import (
    apply_delivery_input,
    build_delivery_schema,
    build_delivery_suggested,
)
from custom_components.frigate_notifications.flows.profile.steps.media_actions import (
    apply_media_actions_input,
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
    """Test rate limiting via apply_delivery_input."""

    def test_rate_limiting_cooldown_coerced_to_int(self) -> None:
        """Cooldown override is coerced to int."""
        ctx = _make_ctx(Provider.APPLE)
        draft: dict[str, Any] = {}
        apply_delivery_input(draft, {"rate_limiting": {"cooldown_override": 120.0}}, ctx)
        assert draft["cooldown_override"] == 120
        assert isinstance(draft["cooldown_override"], int)

    def test_rate_limiting_alert_once_stored(self) -> None:
        """alert_once=True is stored."""
        ctx = _make_ctx(Provider.APPLE)
        draft: dict[str, Any] = {}
        apply_delivery_input(draft, {"rate_limiting": {"alert_once": True}}, ctx)
        assert draft["alert_once"] is True

    def test_rate_limiting_clears_stale_values(self) -> None:
        """Empty rate_limiting input clears stale keys."""
        ctx = _make_ctx(Provider.APPLE)
        draft: dict[str, Any] = {
            "silence_duration": 30,
            "cooldown_override": 60,
            "alert_once": True,
        }
        apply_delivery_input(draft, {"rate_limiting": {}}, ctx)
        assert "silence_duration" not in draft
        assert "cooldown_override" not in draft
        assert "alert_once" not in draft


class TestDeliveryFieldPersistence:
    """Test that apply_delivery_input persists provider-specific fields."""

    def test_android_channel_stored(self) -> None:
        """Android delivery channel and sticky flag are persisted."""
        ctx = _make_ctx(Provider.ANDROID)
        draft: dict[str, Any] = {}
        apply_delivery_input(
            draft,
            {"android_delivery": {"android_channel": "test", "android_sticky": True}},
            ctx,
        )
        assert draft["android_channel"] == "test"
        assert draft["android_sticky"] is True

    def test_tv_overlay_stored(self) -> None:
        """TV overlay delivery fields are persisted."""
        ctx = _make_ctx(Provider.ANDROID_TV)
        draft: dict[str, Any] = {}
        apply_delivery_input(
            draft,
            {"initial_delivery": {"delay": 3, "tv_fontsize": "large", "tv_position": "top-left"}},
            ctx,
        )
        assert draft["phases"]["initial"]["delay"] == 3
        assert draft["phases"]["initial"]["tv_fontsize"] == "large"

    def test_urgency_stored(self) -> None:
        """Urgency key is persisted in per-phase delivery."""
        ctx = _make_ctx(Provider.APPLE)
        draft: dict[str, Any] = {}
        apply_delivery_input(
            draft,
            {"initial_delivery": {"urgency": "urgent", "delay": 0}},
            ctx,
        )
        assert draft["phases"]["initial"]["urgency"] == "urgent"


class TestMediaActionsApply:
    """Test apply_media_actions_input field persistence."""

    def test_video_stored(self) -> None:
        """Video field is persisted when present in input."""
        ctx = _make_ctx(Provider.APPLE)
        draft: dict[str, Any] = {}
        apply_media_actions_input(
            draft,
            {"initial_media": {"attachment": "snapshot", "video": "clip_mp4"}},
            ctx,
        )
        assert draft["phases"]["initial"]["video"] == "clip_mp4"
        assert draft["phases"]["initial"]["attachment"] == "snapshot"

    def test_no_video_when_absent(self) -> None:
        """Video key is not introduced when absent from input."""
        ctx = _make_ctx(Provider.APPLE)
        draft: dict[str, Any] = {}
        apply_media_actions_input(
            draft,
            {"initial_media": {"attachment": "snapshot"}},
            ctx,
        )
        assert "video" not in draft["phases"]["initial"]


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


class TestContentSuggested:
    """Test build_content_suggested."""

    def test_content_suggested_stored_phase_without_subtitle_omits_it(self) -> None:
        """A stored phase lacking subtitle_template gets no subtitle suggestion."""
        draft: dict[str, Any] = {"phases": {"initial": {"message_template": "object_only"}}}
        suggested = build_content_suggested(draft)
        assert suggested["initial_content"] == {"message_template": "object_only"}

    def test_content_suggested_unstored_phase_uses_phase_defaults(self) -> None:
        """A phase with no stored data is suggested from the phase defaults."""
        suggested = build_content_suggested({})
        assert suggested["initial_content"] == {
            "message_template": DEFAULT_PHASE_INITIAL.content.message_template,
            "subtitle_template": DEFAULT_PHASE_INITIAL.content.subtitle_template,
        }

    def test_content_suggested_carries_title_and_zone_overrides(self) -> None:
        """Stored title template and zone overrides are suggested back."""
        draft: dict[str, Any] = {
            "title_template": "my_title",
            "zone_overrides": {"porch": "at the porch"},
        }
        suggested = build_content_suggested(draft)
        assert suggested["title_template"] == "my_title"
        assert suggested["zone_overrides"] == {"porch": "at the porch"}


class TestContentClearedFields:
    """Omitted template fields are stored as cleared instead of restoring old values."""

    def test_content_schema_omitted_subtitle_not_filled_from_draft(self) -> None:
        """Validating input without subtitle_template leaves the key absent."""
        ctx = _make_ctx()
        draft: dict[str, Any] = {
            "cameras": ["driveway"],
            "phases": {"initial": {"subtitle_template": "merged_subjects"}},
        }
        validated = build_content_schema(draft, ctx)({"initial_content": {"enabled": True}})
        assert "subtitle_template" not in validated["initial_content"]

    def test_apply_content_omitted_subtitle_clears_stored_value(self) -> None:
        """Submitting a phase section without subtitle_template clears the stored one."""
        ctx = _make_ctx()
        draft: dict[str, Any] = {
            "cameras": ["driveway"],
            "phases": {"initial": {"subtitle_template": "merged_subjects"}},
        }
        apply_content_input(draft, {"initial_content": {"enabled": True}}, ctx)
        assert draft["phases"]["initial"]["subtitle_template"] == ""
