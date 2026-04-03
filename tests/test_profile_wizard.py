"""Tests for profile wizard, conditional visibility, multi-camera, and title template."""

from typing import Any
from unittest.mock import patch

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.frigate_notifications.const import DOMAIN

from .conftest import FRIGATE_DOMAIN, FRIGATE_ENTRY_ID, PROFILE_SUBENTRY_DATA
from .flow_helpers import (
    _advance_to_content,
    _advance_tv_to_content,
    _make_profile_entry,
    _schema_section_keys,
)


async def _basics_to_menu(
    hass: HomeAssistant, flow_id: str, *, name: str, cameras: list[str], provider: str
) -> Any:
    """Drive basics two-pass and return the customize menu result."""
    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"name": name, "cameras": cameras, "provider": provider}
    )
    result = await hass.config_entries.subentries.async_configure(
        flow_id,
        {
            "name": name,
            "cameras": cameras,
            "provider": provider,
            "notify_service": "notify.test_phone",
        },
    )
    assert result["step_id"] == "customize"
    return result


async def _save_from_menu(hass: HomeAssistant, flow_id: str) -> Any:
    """Navigate to save from customize menu and return result."""
    result = await hass.config_entries.subentries.async_configure(flow_id, {"next_step_id": "save"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    return result


async def _complete_wizard_via_menu(
    hass: HomeAssistant,
    flow_id: str,
    *,
    filtering_input: dict[str, Any] | None = None,
    content_input: dict[str, Any] | None = None,
    media_input: dict[str, Any] | None = None,
    delivery_input: dict[str, Any] | None = None,
) -> Any:
    """From the customize menu, optionally visit sections then save."""
    if filtering_input is not None:
        await hass.config_entries.subentries.async_configure(flow_id, {"next_step_id": "filtering"})
        await hass.config_entries.subentries.async_configure(flow_id, filtering_input)
    if content_input is not None:
        await hass.config_entries.subentries.async_configure(flow_id, {"next_step_id": "content"})
        await hass.config_entries.subentries.async_configure(flow_id, content_input)
    if media_input is not None:
        await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "media_actions"}
        )
        await hass.config_entries.subentries.async_configure(flow_id, media_input)
    if delivery_input is not None:
        await hass.config_entries.subentries.async_configure(flow_id, {"next_step_id": "delivery"})
        await hass.config_entries.subentries.async_configure(flow_id, delivery_input)
    return await _save_from_menu(hass, flow_id)


class TestProfileWizard:
    """Profile wizard tests — preset -> basics -> customize menu -> save."""

    async def test_builtin_preset_survives_empty_wizard_steps(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Selecting a built-in preset seeds phase data; empty submits preserve it."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"), context={"source": "user"}
        )

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"preset": "simple"}
        )
        flow_id = result["flow_id"]
        result = await _basics_to_menu(
            hass, flow_id, name="Preset Test", cameras=["driveway"], provider="apple"
        )

        # Visit all optional sections with empty input, then save.
        result = await _complete_wizard_via_menu(
            hass,
            flow_id,
            filtering_input={"severity": "alert"},
            content_input={},
            media_input={},
            delivery_input={},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        phases = result["data"]["phases"]
        assert phases["initial"]["message_template"] == "object_only"
        assert phases["update"]["message_template"] == "object_only"
        assert phases["end"]["message_template"] == "object_only"
        assert phases["initial"]["subtitle_template"] == "merged_subjects"
        assert phases["genai"]["message_template"] == "genai_summary"
        assert phases["genai"]["interruption_level"] == "passive"
        assert result["data"]["_preset_id"] == "simple"
        assert result["data"]["_preset_version"] == 1

    @patch(
        "custom_components.frigate_notifications.flows.profile.context.supports_genai",
        return_value=False,
    )
    async def test_rich_alerts_preset_seeds_non_genai_when_capability_absent(
        self, mock_genai: Any, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Rich-alert preset applies genai_disabled_overrides when capability is absent."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"), context={"source": "user"}
        )

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"preset": "detailed"}
        )
        flow_id = result["flow_id"]
        result = await _basics_to_menu(
            hass, flow_id, name="Rich Preset", cameras=["driveway"], provider="apple"
        )

        result = await _complete_wizard_via_menu(
            hass,
            flow_id,
            filtering_input={"severity": "alert"},
            content_input={},
            media_input={},
            delivery_input={},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        phases = result["data"]["phases"]
        assert phases["initial"]["message_template"] == "phase_icon_context"
        assert phases["update"]["message_template"] == "rich_update"
        assert phases["end"]["message_template"] == "phase_icon_context"
        assert phases["genai"]["enabled"] is False
        assert result["data"]["_preset_id"] == "detailed"
        assert result["data"]["_preset_version"] == 3

    async def test_content_selector_filters_by_phase(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Phase-restricted presets only appear in their intended phase selectors."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        _, result = await _advance_to_content(hass, entry)

        schema = result["data_schema"].schema

        def _message_options(section_key: str) -> set[str]:
            for k, v in schema.items():
                key_name = k.schema if hasattr(k, "schema") else str(k)
                if key_name == section_key:
                    inner = v.schema.schema
                    for ik, iv in inner.items():
                        ik_name = ik.schema if hasattr(ik, "schema") else str(ik)
                        if ik_name == "message_template":
                            return {o["value"] for o in iv.config["options"]}
            return set()

        initial_opts = _message_options("initial_content")
        genai_opts = _message_options("genai_content")

        # genai_summary is genai-only — must not appear in initial.
        assert "genai_summary" in genai_opts
        assert "genai_summary" not in initial_opts
        # genai_pending is end-only — must not appear in genai.
        assert "genai_pending" not in genai_opts
        # Universal presets appear in both.
        assert "object_action_zone" in initial_opts
        assert "object_action_zone" in genai_opts

    async def test_basics_two_pass(self, hass: HomeAssistant, mock_frigate_data: dict) -> None:
        """Test basics step uses two-pass pattern (identity then target)."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"), context={"source": "user"}
        )
        # Step 1: Preset.
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"preset": "custom"}
        )
        assert result["step_id"] == "basics"

        # Pass 1: identity.
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {"name": "My Profile", "cameras": ["driveway"], "provider": "apple"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "basics"  # Re-shows for pass 2.

        # Pass 2: target (must re-include required identity fields).
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                "name": "My Profile",
                "cameras": ["driveway"],
                "provider": "apple",
                "notify_service": "notify.my_phone",
            },
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "customize"

    async def test_fast_path_save_after_basics(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """User can save immediately from the customize menu with preset defaults."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"preset": "simple"}
        )
        flow_id = result["flow_id"]
        await _basics_to_menu(hass, flow_id, name="Quick", cameras=["driveway"], provider="apple")

        # Save directly — skip all optional sections.
        result = await _save_from_menu(hass, flow_id)
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["name"] == "Quick"
        assert result["data"]["cameras"] == ["driveway"]
        # Preset defaults should be present.
        assert "phases" in result["data"]
        assert result["data"]["phases"]["initial"]["message_template"] == "object_only"

    async def test_basics_aborts_no_frigate(
        self, hass: HomeAssistant, mock_frigate_entry: MockConfigEntry
    ) -> None:
        """Test basics aborts when Frigate data not in hass.data."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            title="Test",
        )
        entry.add_to_hass(hass)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"), context={"source": "user"}
        )
        # Preset.
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"preset": "custom"}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "frigate_not_loaded"

    async def test_basics_notify_target_required(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Test error when no notify target is provided."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"preset": "custom"}
        )
        # Pass 1.
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {"name": "Test", "cameras": ["driveway"], "provider": "apple"},
        )
        # Pass 2 - no target (must re-include required identity fields).
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {"name": "Test", "cameras": ["driveway"], "provider": "apple"},
        )
        assert result["type"] is FlowResultType.FORM
        errors = result["errors"]
        assert errors is not None
        assert "notify_device" in errors

        # Pass 2 again - both device and service filled (mutual exclusion).
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                "name": "Test",
                "cameras": ["driveway"],
                "provider": "apple",
                "notify_device": "fake_device_id",
                "notify_service": "notify.mobile_app_test",
            },
        )
        assert result["type"] is FlowResultType.FORM
        errors = result["errors"]
        assert errors is not None
        assert errors["notify_service"] == "notify_target_exclusive"

    async def test_tv_provider_rejects_mobile_app(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Test android_tv rejects mobile_app services."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"preset": "custom"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {"name": "TV", "cameras": ["driveway"], "provider": "android_tv"},
        )
        # Pass 2 (must re-include required identity fields).
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                "name": "TV",
                "cameras": ["driveway"],
                "provider": "android_tv",
                "notify_service": "notify.mobile_app_tv",
            },
        )
        assert result["type"] is FlowResultType.FORM
        errors = result["errors"]
        assert errors is not None
        assert errors["notify_service"] == "tv_notify_service_invalid"

    async def test_filtering_shows_recognition_with_identities(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Recognition section appears when camera has discovered sub-label identities."""
        ent_reg = er.async_get(hass)
        frigate_entry = hass.config_entries.async_get_entry(FRIGATE_ENTRY_ID)
        # Camera needs both capability + identity sensors.
        ent_reg.async_get_or_create(
            "sensor",
            FRIGATE_DOMAIN,
            f"{FRIGATE_ENTRY_ID}:sensor_recognized_face:driveway",
            config_entry=frigate_entry,
        )
        ent_reg.async_get_or_create(
            "sensor",
            FRIGATE_DOMAIN,
            f"{FRIGATE_ENTRY_ID}:sensor_global_face:Alice",
            config_entry=frigate_entry,
        )

        entry = _make_profile_entry(hass, mock_frigate_data)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"preset": "custom"}
        )
        flow_id = result["flow_id"]
        await _basics_to_menu(hass, flow_id, name="Test", cameras=["driveway"], provider="apple")

        # Enter filtering from menu.
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "filtering"}
        )
        assert result["step_id"] == "filtering"
        keys = _schema_section_keys(result)
        assert "recognition_config" in keys

    async def test_filtering_hides_recognition_without_identities(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Recognition section hidden when camera has no discovered sub-label identities."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"preset": "custom"}
        )
        flow_id = result["flow_id"]
        await _basics_to_menu(hass, flow_id, name="Test", cameras=["driveway"], provider="apple")

        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "filtering"}
        )
        assert result["step_id"] == "filtering"
        keys = _schema_section_keys(result)
        assert "recognition_config" not in keys


class TestConditionalVisibility:
    """Tests for conditional phase/provider visibility in the profile flow."""

    async def test_media_actions_disabled_phase_omits_section(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Disabled phase sections are omitted from media_actions schema."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        flow_id, _ = await _advance_to_content(hass, entry)

        # Disable the "update" phase in content step.
        content_input: dict[str, Any] = {
            "update_content": {"enabled": False},
        }
        result = await hass.config_entries.subentries.async_configure(flow_id, content_input)
        assert result["step_id"] == "customize"

        # Enter media_actions from menu.
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "media_actions"}
        )
        assert result["step_id"] == "media_actions"

        keys = _schema_section_keys(result)
        assert "initial_media" in keys
        assert "end_media" in keys
        assert "genai_media" in keys
        assert "update_media" not in keys

    async def test_media_actions_tv_profile_omits_custom_actions(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """TV profiles do not show the custom_actions section in media_actions."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        flow_id, _ = await _advance_tv_to_content(hass, entry)

        # Submit content to return to menu.
        result = await hass.config_entries.subentries.async_configure(flow_id, {})
        assert result["step_id"] == "customize"

        # Enter media_actions from menu.
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "media_actions"}
        )
        assert result["step_id"] == "media_actions"

        keys = _schema_section_keys(result)
        assert "custom_actions" not in keys

    async def test_media_actions_non_tv_shows_custom_actions(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Non-TV profiles show the custom_actions section in media_actions."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        flow_id, _ = await _advance_to_content(hass, entry)

        # Submit content to return to menu.
        result = await hass.config_entries.subentries.async_configure(flow_id, {})
        assert result["step_id"] == "customize"

        # Enter media_actions from menu.
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "media_actions"}
        )
        assert result["step_id"] == "media_actions"

        keys = _schema_section_keys(result)
        assert "custom_actions" in keys

    async def test_media_actions_custom_actions_filters_disabled_phases(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Custom actions section only contains fields for enabled phases."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        flow_id, _ = await _advance_to_content(hass, entry)

        # Disable "update" and "end" phases.
        content_input: dict[str, Any] = {
            "update_content": {"enabled": False},
            "end_content": {"enabled": False},
        }
        result = await hass.config_entries.subentries.async_configure(flow_id, content_input)
        assert result["step_id"] == "customize"

        # Enter media_actions from menu.
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "media_actions"}
        )
        assert result["step_id"] == "media_actions"

        # Find the custom_actions section and inspect its inner schema keys.
        schema = result["data_schema"].schema  # ty: ignore[unresolved-attribute]
        custom_section = None
        for k, v in schema.items():
            key_name = k.schema if hasattr(k, "schema") else str(k)
            if key_name == "custom_actions":
                custom_section = v
                break
        assert custom_section is not None
        inner_keys = {
            k.schema if hasattr(k, "schema") else str(k) for k in custom_section.schema.schema
        }
        assert "initial_custom_actions" in inner_keys
        assert "genai_custom_actions" in inner_keys
        assert "update_custom_actions" not in inner_keys
        assert "end_custom_actions" not in inner_keys

    async def test_reconfigure_reenable_phase_restores_media_section(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Re-enabling a phase in content makes its media section reappear."""
        initial_data: dict[str, Any] = {
            **PROFILE_SUBENTRY_DATA,
            "phases": {
                "initial": {"enabled": True, "message_template": "test"},
                "update": {
                    "enabled": False,
                    "message_template": "update msg",
                    "attachment": "review_gif",
                },
                "end": {"enabled": True, "message_template": "end"},
                "genai": {"enabled": True, "message_template": "{{ genai_summary }}"},
            },
        }
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            options={},
            title="Test",
            subentries_data=[
                ConfigSubentryData(
                    data=initial_data,
                    subentry_type="profile",
                    title="Test",
                    unique_id="reenable_test",
                ),
            ],
        )
        entry.add_to_hass(hass)

        subentry_id = next(
            s.subentry_id for s in entry.subentries.values() if s.subentry_type == "profile"
        )
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"),
            context={"source": "reconfigure", "subentry_id": subentry_id},
        )
        flow_id = result["flow_id"]

        # Visit media_actions — update should be hidden.
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "media_actions"}
        )
        keys = _schema_section_keys(result)
        assert "update_media" not in keys

        # Submit media_actions (empty) to return to menu.
        result = await hass.config_entries.subentries.async_configure(flow_id, {})
        assert result["type"] is FlowResultType.MENU

        # Re-enable "update" via content step.
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "content"}
        )
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"update_content": {"enabled": True}}
        )
        assert result["type"] is FlowResultType.MENU

        # Visit media_actions again — update should now be visible.
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "media_actions"}
        )
        keys = _schema_section_keys(result)
        assert "update_media" in keys


class TestMultiCameraConfigFlow:
    """Tests for multi-camera profile config flow behavior."""

    async def test_filtering_step_hides_zones_for_multi_camera(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Zone fields are absent from filtering schema for multi-camera profiles."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"preset": "custom"}
        )
        flow_id = result["flow_id"]
        await _basics_to_menu(
            hass, flow_id, name="Multi", cameras=["driveway", "backyard"], provider="apple"
        )

        # Enter filtering from menu.
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "filtering"}
        )
        assert result["step_id"] == "filtering"
        keys = _schema_section_keys(result)
        assert "required_zones" not in keys
        assert "zone_match_mode" not in keys
        assert "objects" in keys
        assert "severity" in keys

    async def test_filtering_step_shows_zones_for_single_camera(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Zone fields are present in filtering schema for single-camera profiles."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"preset": "custom"}
        )
        flow_id = result["flow_id"]
        await _basics_to_menu(hass, flow_id, name="Single", cameras=["driveway"], provider="apple")

        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "filtering"}
        )
        assert result["step_id"] == "filtering"
        keys = _schema_section_keys(result)
        assert "required_zones" in keys
        assert "zone_match_mode" in keys

    async def test_filtering_step_merges_objects_across_cameras(
        self, hass: HomeAssistant, mock_frigate_entry: MockConfigEntry
    ) -> None:
        """Object options are the union of tracked objects across selected cameras."""
        config_with_objects: dict[str, Any] = {
            "cameras": {
                "driveway": {
                    "zones": {},
                    "objects": {"track": ["person", "car"]},
                    "review": {"genai": {"enabled": False}},
                },
                "backyard": {
                    "zones": {},
                    "objects": {"track": ["person", "dog"]},
                    "review": {"genai": {"enabled": False}},
                },
            },
        }
        hass.data[FRIGATE_DOMAIN] = {
            FRIGATE_ENTRY_ID: {"config": config_with_objects},
        }
        entry = _make_profile_entry(hass, hass.data[FRIGATE_DOMAIN])
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"preset": "custom"}
        )
        flow_id = result["flow_id"]
        await _basics_to_menu(
            hass, flow_id, name="Multi", cameras=["driveway", "backyard"], provider="apple"
        )

        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "filtering"}
        )
        assert result["step_id"] == "filtering"
        # Extract object options from schema.
        assert result["data_schema"] is not None
        schema = result["data_schema"].schema
        for key in schema:
            key_name = key.schema if hasattr(key, "schema") else str(key)
            if key_name == "objects":
                selector = schema[key]
                option_values = [o["value"] for o in selector.config["options"]]
                assert sorted(option_values) == ["car", "dog", "person"]
                break
        else:
            pytest.fail("objects field not found in filtering schema")

    async def test_duplicate_name_rejected(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Profile with identical title to existing profile is rejected."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        # Create a first profile via fast path.
        r = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"), context={"source": "user"}
        )
        r = await hass.config_entries.subentries.async_configure(r["flow_id"], {"preset": "custom"})
        flow_id = r["flow_id"]
        await _basics_to_menu(hass, flow_id, name="Test", cameras=["driveway"], provider="apple")
        r = await _save_from_menu(hass, flow_id)
        assert r["type"] is FlowResultType.CREATE_ENTRY

        # Attempt second profile with same name + cameras.
        r2 = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"), context={"source": "user"}
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r2["flow_id"], {"preset": "custom"}
        )
        r2 = await hass.config_entries.subentries.async_configure(
            r2["flow_id"],
            {"name": "Test", "cameras": ["driveway"], "provider": "android"},
        )
        # Should stay on basics with error — different provider doesn't matter.
        assert r2["type"] is FlowResultType.FORM
        assert r2["step_id"] == "basics"
        assert r2["errors"] is not None
        assert r2["errors"]["name"] == "profile_name_duplicate"

    async def test_cameras_stored_in_sorted_order(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Cameras are canonicalized to alphabetical order on storage."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        r = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "profile"), context={"source": "user"}
        )
        r = await hass.config_entries.subentries.async_configure(r["flow_id"], {"preset": "custom"})
        flow_id = r["flow_id"]
        # Submit cameras in reverse alphabetical order.
        await _basics_to_menu(
            hass, flow_id, name="Multi", cameras=["driveway", "backyard"], provider="apple"
        )

        r = await _complete_wizard_via_menu(
            hass,
            flow_id,
            filtering_input={"severity": "alert"},
            content_input={},
            media_input={},
            delivery_input={},
        )
        assert r["type"] is FlowResultType.CREATE_ENTRY
        assert r["data"]["cameras"] == ["backyard", "driveway"]


class TestProfileTitleTemplate:
    """Tests for per-profile title_template override in the content step."""

    async def test_content_title_template_override_stored(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Non-empty title_template in content step is stored in profile data."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        flow_id, _ = await _advance_to_content(hass, entry)

        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"title_template": "Override: {{ camera_name }}"}
        )
        assert result["step_id"] == "customize"

        result = await _save_from_menu(hass, flow_id)
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["title_template"] == "Override: {{ camera_name }}"

    async def test_content_title_template_blank_not_stored(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Blank title_template is not stored, allowing global fallback."""
        entry = _make_profile_entry(hass, mock_frigate_data)
        flow_id, _ = await _advance_to_content(hass, entry)

        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"title_template": ""}
        )
        assert result["step_id"] == "customize"

        result = await _save_from_menu(hass, flow_id)
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert "title_template" not in result["data"]
