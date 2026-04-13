"""Tests for FlowContext construction and normalize stub."""

from unittest.mock import MagicMock, patch

from custom_components.frigate_notifications.enums import Provider
from custom_components.frigate_notifications.flows.profile.context import (
    _derive_enabled_phases,
    build_flow_context,
)
from custom_components.frigate_notifications.flows.profile.normalize import (
    normalize_profile_data,
)
from custom_components.frigate_notifications.providers.base import get_capabilities


class TestDeriveEnabledPhases:
    """Tests for _derive_enabled_phases."""

    def test_derive_enabled_phases_all_enabled_by_default(self) -> None:
        """All phases enabled when no phases dict present."""
        assert _derive_enabled_phases({}) == ("initial", "update", "end", "genai")

    def test_derive_enabled_phases_respects_disabled(self) -> None:
        """Disabled phases are excluded."""
        draft = {"phases": {"update": {"enabled": False}, "genai": {"enabled": False}}}
        assert _derive_enabled_phases(draft) == ("initial", "end")

    def test_derive_enabled_phases_all_disabled(self) -> None:
        """All phases disabled returns empty tuple."""
        draft = {
            "phases": {
                "initial": {"enabled": False},
                "update": {"enabled": False},
                "end": {"enabled": False},
                "genai": {"enabled": False},
            }
        }
        assert _derive_enabled_phases(draft) == ()


class TestBuildFlowContext:
    """Tests for build_flow_context."""

    @patch(
        "custom_components.frigate_notifications.flows.profile.context.supports_genai",
        return_value=False,
    )
    def test_build_flow_context_default_provider(self, mock_genai: MagicMock) -> None:
        """Default provider is apple when not in draft."""
        hass = MagicMock()
        hass.data = {}
        entry = MagicMock()
        entry.data = {"frigate_entry_id": "test_id"}

        ctx = build_flow_context(hass, entry, {}, is_reconfiguring=False)

        assert ctx.provider == Provider.APPLE
        assert ctx.capabilities == get_capabilities(Provider.APPLE)
        assert ctx.is_reconfiguring is False
        assert ctx.genai_available is False
        assert ctx.enabled_phases == ("initial", "update", "end")

    @patch(
        "custom_components.frigate_notifications.flows.profile.context.supports_genai",
        return_value=False,
    )
    def test_build_flow_context_android_provider(self, mock_genai: MagicMock) -> None:
        """Provider is read from draft."""
        hass = MagicMock()
        hass.data = {}
        entry = MagicMock()
        entry.data = {"frigate_entry_id": "test_id"}

        ctx = build_flow_context(hass, entry, {"provider": "android"}, is_reconfiguring=True)

        assert ctx.provider == Provider.ANDROID
        assert ctx.capabilities == get_capabilities(Provider.ANDROID)
        assert ctx.is_reconfiguring is True

    def test_build_flow_context_passes_cameras_and_genai(self) -> None:
        """available_cameras from config; genai_available reflects config state."""
        hass = MagicMock()
        hass.data = {
            "frigate": {
                "fid": {
                    "config": {
                        "cameras": {
                            "front": {"review": {"genai": {"enabled": True}}},
                            "back": {},
                        },
                    },
                },
            },
        }
        entry = MagicMock()
        entry.data = {"frigate_entry_id": "fid"}

        ctx = build_flow_context(hass, entry, {}, is_reconfiguring=False)

        assert sorted(ctx.available_cameras) == ["back", "front"]
        assert ctx.genai_available is True

    def test_build_flow_context_genai_scoped_to_draft_cameras(self) -> None:
        """GenAI check uses only draft cameras when present, not all cameras."""
        hass = MagicMock()
        hass.data = {
            "frigate": {
                "fid": {
                    "config": {
                        "cameras": {
                            "front": {"review": {"genai": {"enabled": False}}},
                            "back": {"review": {"genai": {"enabled": True}}},
                        },
                    },
                },
            },
        }
        entry = MagicMock()
        entry.data = {"frigate_entry_id": "fid"}

        ctx = build_flow_context(hass, entry, {"cameras": ["front"]}, is_reconfiguring=False)
        assert ctx.genai_available is False


class TestNormalizeProfileData:
    """Tests for normalize_profile_data output contract."""

    def test_returns_new_dict_preserving_unrelated_keys(self) -> None:
        """Returns a new dict; unrelated keys pass through unchanged."""
        draft = {"name": "Test", "cameras": ["driveway"], "provider": "apple"}
        result = normalize_profile_data(draft)
        assert result is not draft
        assert result["name"] == "Test"
        assert result["cameras"] == ["driveway"]

    def test_prunes_and_keeps_optional_strings_and_collections(self) -> None:
        """Empty optional fields are pruned; non-empty ones are preserved."""
        draft = {
            # Strings: empty pruned, non-empty kept
            "title_template": "",
            # Lists: empty pruned
            "objects": [],
            "required_zones": [],
            "include_sub_labels": [],
            "exclude_sub_labels": [],
            # Dicts: empty pruned
            "zone_overrides": {},
            # Collections: empty pruned
            "action_config": [],
        }
        result = normalize_profile_data(draft)
        for key in (
            "title_template",
            "objects",
            "required_zones",
            "include_sub_labels",
            "exclude_sub_labels",
            "zone_overrides",
            "action_config",
        ):
            assert key not in result, f"{key} should have been pruned"

        # Non-empty values are preserved.
        kept = normalize_profile_data(
            {
                "title_template": "custom",
                "objects": ["person"],
                "required_zones": ["front"],
                "zone_overrides": {"front_yard": "at the front"},
                "action_config": [{"preset": "view_clip"}],
            }
        )
        assert kept["title_template"] == "custom"
        assert kept["objects"] == ["person"]
        assert kept["required_zones"] == ["front"]
        assert kept["zone_overrides"] == {"front_yard": "at the front"}
        assert kept["action_config"] == [{"preset": "view_clip"}]

    def test_cleans_conditional_keys_by_mode(self) -> None:
        """Conditional fields are removed when their mode doesn't require them."""
        draft = {
            # Guard: inherit -> guard_entity removed
            "guard_mode": "inherit",
            "guard_entity": "binary_sensor.alarm",
            # Presence: inherit -> presence_entities removed
            "presence_mode": "inherit",
            "presence_entities": ["person.alice"],
            # State: not custom -> state fields removed
            "state_filter_mode": "inherit",
            "state_entity": "sensor.x",
            "state_filter_states": ["on"],
            # Time: not custom -> time fields removed
            "time_filter_override": "inherit",
            "time_filter_mode": "notify_only_during",
            "time_filter_start": "08:00",
            "time_filter_end": "20:00",
            # Zones: empty required_zones -> zone_match_mode removed
            "required_zones": [],
            "zone_match_mode": "any",
        }
        result = normalize_profile_data(draft)
        assert "guard_entity" not in result
        assert "presence_entities" not in result
        assert "state_entity" not in result
        assert "state_filter_states" not in result
        assert "time_filter_mode" not in result
        assert "time_filter_start" not in result
        assert "time_filter_end" not in result
        assert "zone_match_mode" not in result

        # Guard kept when custom.
        custom = normalize_profile_data(
            {
                "guard_mode": "custom",
                "guard_entity": "binary_sensor.alarm",
                "presence_mode": "custom",
                "presence_entities": ["person.alice"],
            }
        )
        assert custom["guard_entity"] == "binary_sensor.alarm"
        assert custom["presence_entities"] == ["person.alice"]

    def test_cleans_phase_subtitle_templates(self) -> None:
        """Empty subtitle_template pruned from per-phase dicts; non-empty kept."""
        draft = {
            "phases": {
                "initial": {"message_template": "object_only", "subtitle_template": ""},
                "update": {"subtitle_template": "merged_subjects"},
            }
        }
        result = normalize_profile_data(draft)
        assert "subtitle_template" not in result["phases"]["initial"]
        assert result["phases"]["update"]["subtitle_template"] == "merged_subjects"

    def test_ensures_phases_dict(self) -> None:
        """Phases dict is created if missing."""
        result = normalize_profile_data({"name": "Test"})
        assert result["phases"] == {}

    def test_preserves_preset_tracking_keys(self) -> None:
        """_preset_id and _preset_version pass through unchanged."""
        draft = {"_preset_id": "simple", "_preset_version": 1}
        result = normalize_profile_data(draft)
        assert result["_preset_id"] == "simple"
        assert result["_preset_version"] == 1
