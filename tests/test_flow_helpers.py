"""Tests for config flow helper and submission functions (pure, no HA fixtures)."""

from typing import Any


class TestHelpers:
    """Test config flow helper functions."""

    def test_humanized_options(self) -> None:
        """Test humanized_options builds SelectOptionDict list."""
        from custom_components.frigate_notifications.flows.helpers import humanized_options

        options = humanized_options(["front_yard", "back_patio"])
        assert len(options) == 2
        assert options[0]["value"] == "front_yard"
        assert options[0]["label"] == "Front Yard"

    def test_profile_title_single_camera(self) -> None:
        """Single-camera profile title includes camera name."""
        from custom_components.frigate_notifications.flows.helpers import profile_title

        assert profile_title(["driveway"], "My Profile") == "Driveway / My Profile"

    def test_profile_title_two_cameras(self) -> None:
        """Two-camera profile title lists both camera names."""
        from custom_components.frigate_notifications.flows.helpers import profile_title

        assert profile_title(["backyard", "driveway"], "Alerts") == "Backyard, Driveway / Alerts"

    def test_profile_title_three_plus_cameras(self) -> None:
        """Three+ camera profile title shows first camera + count."""
        from custom_components.frigate_notifications.flows.helpers import profile_title

        assert profile_title(["a", "b", "c"], "Motion Alerts") == "A +2 / Motion Alerts"

    def test_normalize_interruption_level(self) -> None:
        """Test interruption level normalization."""
        from custom_components.frigate_notifications.flows.helpers import (
            normalize_interruption_level,
        )

        assert normalize_interruption_level("time_sensitive") == "time-sensitive"
        assert normalize_interruption_level("active") == "active"

    def test_profile_placeholders(self) -> None:
        """Test profile_placeholders builds correct dict."""
        from custom_components.frigate_notifications.flows.helpers import (
            profile_placeholders,
        )

        ph = profile_placeholders({"cameras": ["front_door"], "name": "Test"})
        assert ph["camera_name"] == "Front Door"
        assert ph["profile_name"] == "Test"

    def test_profile_placeholders_multi_camera(self) -> None:
        """Multi-camera profile placeholders use compact format."""
        from custom_components.frigate_notifications.flows.helpers import (
            profile_placeholders,
        )

        ph = profile_placeholders({"cameras": ["a", "b", "c"], "name": "Alerts"})
        assert ph["camera_name"] == "A +2"
        assert ph["profile_name"] == "Alerts"

    def test_format_camera_text(self) -> None:
        """format_camera_text handles 1, 2, and 3+ cameras."""
        from custom_components.frigate_notifications.const import format_camera_text

        assert format_camera_text(["driveway"]) == "Driveway"
        assert format_camera_text(["backyard", "driveway"]) == "Backyard, Driveway"
        assert format_camera_text(["a", "b", "c"]) == "A +2"
        assert format_camera_text([]) == ""

    # Discovery helper tests moved to tests/test_helpers.py


class TestFilteringValidation:
    """Test filtering step validation."""

    def test_validate_all_custom_missing_fields_errors(self) -> None:
        """All filters set to custom with missing required fields produce all errors."""
        from custom_components.frigate_notifications.flows.profile.steps.filtering import (
            validate_filtering_input,
        )

        errors = validate_filtering_input(
            {},
            {
                "guard_config": {"guard_mode": "custom"},
                "time_filter_config": {
                    "time_filter_override": "custom",
                    "time_filter_mode": "notify_only_during",
                },
                "presence_config": {"presence_mode": "custom"},
                "state_filter_config": {"state_filter_mode": "custom"},
            },
            None,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        )
        assert errors["guard_entity"] == "guard_entity_required"
        assert "time_filter_start" in errors
        assert "time_filter_end" in errors
        assert errors["presence_entities"] == "presence_entities_required"
        assert errors["state_entity"] == "state_entity_required"

    def test_validate_all_inherit_or_disabled_no_errors(self) -> None:
        """All filters inherit or disabled produce no errors."""
        from custom_components.frigate_notifications.flows.profile.steps.filtering import (
            validate_filtering_input,
        )

        errors = validate_filtering_input(
            {},
            {
                "guard_config": {"guard_mode": "inherit"},
                "time_filter_config": {
                    "time_filter_override": "custom",
                    "time_filter_mode": "disabled",
                },
                "presence_config": {"presence_mode": "disabled"},
                "state_filter_config": {"state_filter_mode": "inherit"},
            },
            None,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        )
        assert errors == {}

    def test_validate_sub_label_overlap(self) -> None:
        """Test overlap between include and exclude sub-labels."""
        from custom_components.frigate_notifications.flows.profile.steps.filtering import (
            validate_filtering_input,
        )

        errors = validate_filtering_input(
            {},
            {
                "recognition_config": {
                    "include_sub_labels": ["Alice", "Bob"],
                    "exclude_sub_labels": ["Bob", "Charlie"],
                },
            },
            None,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        )
        assert errors["exclude_sub_labels"] == "sub_label_overlap"

    def test_validate_sub_label_no_overlap(self) -> None:
        """Test no error when include and exclude are disjoint."""
        from custom_components.frigate_notifications.flows.profile.steps.filtering import (
            validate_filtering_input,
        )

        errors = validate_filtering_input(
            {},
            {
                "recognition_config": {
                    "include_sub_labels": ["Alice"],
                    "exclude_sub_labels": ["Bob"],
                },
            },
            None,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        )
        assert "exclude_sub_labels" not in errors

    def test_submit_filtering_recognition_fields(self) -> None:
        """Test apply_filtering_input stores recognition fields."""
        from custom_components.frigate_notifications.flows.profile.steps.filtering import (
            apply_filtering_input,
        )

        data: dict[str, Any] = {}
        apply_filtering_input(
            data,
            {
                "severity": "alert",
                "recognition_config": {
                    "recognition_mode": "require_recognized",
                    "include_sub_labels": ["Alice"],
                    "exclude_sub_labels": [],
                },
            },
            None,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        )
        assert data["recognition_mode"] == "require_recognized"
        assert data["include_sub_labels"] == ["Alice"]
        assert data["exclude_sub_labels"] == []


class TestFilteringSubmission:
    """Test apply_filtering_input standalone function."""

    def test_apply_all_custom_stores_fields(self) -> None:
        """All filters set to custom store their respective fields."""
        from custom_components.frigate_notifications.flows.profile.steps.filtering import (
            apply_filtering_input,
        )

        data: dict[str, Any] = {}
        apply_filtering_input(
            data,
            {
                "objects": ["person", "car"],
                "severity": "alert",
                "guard_config": {
                    "guard_mode": "custom",
                    "guard_entity": "input_boolean.armed",
                },
                "time_filter_config": {
                    "time_filter_override": "custom",
                    "time_filter_mode": "notify_only_during",
                    "time_filter_start": "08:00",
                    "time_filter_end": "18:00",
                },
                "presence_config": {
                    "presence_mode": "custom",
                    "presence_entities": ["person.alice"],
                },
                "state_filter_config": {
                    "state_filter_mode": "custom",
                    "state_entity": "input_select.mode",
                    "state_filter_states": ["away"],
                },
            },
            None,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        )
        assert data["objects"] == ["person", "car"]
        assert data["guard_mode"] == "custom"
        assert data["guard_entity"] == "input_boolean.armed"
        assert data["time_filter_override"] == "custom"
        assert data["time_filter_mode"] == "notify_only_during"
        assert data["time_filter_start"] == "08:00"
        assert data["time_filter_end"] == "18:00"
        assert data["presence_mode"] == "custom"
        assert data["presence_entities"] == ["person.alice"]
        assert data["state_filter_mode"] == "custom"
        assert data["state_entity"] == "input_select.mode"
        assert data["state_filter_states"] == ["away"]

    def test_apply_all_inherit_clears_stale_fields(self) -> None:
        """All filters set to inherit/disabled clear stale stored fields."""
        from custom_components.frigate_notifications.flows.profile.steps.filtering import (
            apply_filtering_input,
        )

        data: dict[str, Any] = {
            "objects": ["person"],
            "guard_entity": "old",
            "time_filter_mode": "old",
            "time_filter_start": "old",
            "time_filter_end": "old",
            "presence_entities": ["person.old"],
            "state_entity": "old",
            "state_filter_states": ["old"],
        }
        apply_filtering_input(
            data,
            {
                "objects": [],
                "severity": "alert",
                "guard_config": {"guard_mode": "inherit"},
                "time_filter_config": {"time_filter_override": "inherit"},
                "presence_config": {"presence_mode": "inherit"},
                "state_filter_config": {"state_filter_mode": "disabled"},
            },
            None,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        )
        assert "objects" not in data
        assert "guard_entity" not in data
        assert "time_filter_mode" not in data
        assert "time_filter_start" not in data
        assert "time_filter_end" not in data
        assert data["presence_mode"] == "inherit"
        assert "presence_entities" not in data
        assert "state_entity" not in data
        assert "state_filter_states" not in data

    def test_suggested_filtering_includes_presence_entities(self) -> None:
        """Test suggested values include presence_entities when present in draft."""
        from unittest.mock import MagicMock

        from custom_components.frigate_notifications.flows.profile.steps.filtering import (
            build_filtering_suggested,
        )

        ctx = MagicMock()
        ctx.hass.data = {}
        ctx.frigate_entry_id = "test_id"
        draft = {
            "cameras": ["driveway"],
            "presence_mode": "custom",
            "presence_entities": ["person.alice"],
        }
        suggested = build_filtering_suggested(draft, ctx)
        assert suggested["presence_config"]["presence_entities"] == ["person.alice"]


class TestConfigHelperGuards:
    """Guard-clause coverage for Frigate config helper wrappers."""

    def _make_hass(self, cameras: dict | None = None) -> Any:
        from unittest.mock import MagicMock

        hass = MagicMock()
        if cameras is not None:
            hass.data = {"frigate": {"fid": {"config": {"cameras": cameras}}}}
        else:
            hass.data = {"frigate": {}}
        return hass

    def test_missing_config_returns_safe_defaults(self) -> None:
        """All helpers return safe defaults when Frigate config is unavailable."""
        from custom_components.frigate_notifications.flows.helpers import (
            camera_supports_genai,
            get_camera_zones,
            get_tracked_objects,
            supports_genai,
        )

        hass = self._make_hass()
        assert supports_genai(hass, "missing") is False
        assert camera_supports_genai(hass, "missing", "cam1") is False
        assert get_camera_zones(hass, "fid", "cam1") == []
        assert get_tracked_objects(hass, "fid", "cam1") == []

    def test_camera_supports_genai_unknown_camera(self) -> None:
        """Returns False when camera does not exist."""
        from custom_components.frigate_notifications.flows.helpers import (
            camera_supports_genai,
            get_camera_zones,
        )

        hass = self._make_hass({"cam1": {"review": {"genai": {"enabled": True}}}})
        assert camera_supports_genai(hass, "fid", "nope") is False
        assert get_camera_zones(hass, "fid", "") == []
