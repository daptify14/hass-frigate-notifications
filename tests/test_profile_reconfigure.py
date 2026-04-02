"""Tests for profile reconfigure flow."""

from typing import Any

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.frigate_notifications.const import DOMAIN

from .conftest import FRIGATE_ENTRY_ID, PROFILE_SUBENTRY_DATA
from .flow_helpers import _schema_section_keys


async def _start_profile_reconfigure(
    hass: HomeAssistant, entry: MockConfigEntry, subentry_id: str
) -> Any:
    """Start a profile subentry reconfigure flow."""
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, "profile"),
        context={"source": "reconfigure", "subentry_id": subentry_id},
    )


# =========================================================================
# Profile reconfigure
# =========================================================================
class TestProfileReconfigure:
    """Profile reconfigure tests."""

    async def test_reconfigure_shows_menu(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Test reconfigure flow shows the section menu."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            options={},
            title="Test",
            subentries_data=[
                ConfigSubentryData(
                    data=PROFILE_SUBENTRY_DATA,
                    subentry_type="profile",
                    title="Test Profile",
                    unique_id="test_profile_reconf",
                ),
            ],
        )
        entry.add_to_hass(hass)

        subentry_id = next(
            s.subentry_id for s in entry.subentries.values() if s.subentry_type == "profile"
        )
        result = await _start_profile_reconfigure(hass, entry, subentry_id)
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "menu"
        assert "save" in result["menu_options"]
        assert "content" in result["menu_options"]
        assert "media_actions" in result["menu_options"]

    async def test_reconfigure_deep_copies_data(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Reconfigure deep-copies subentry data — flow mutations don't leak back."""
        original_phases = {"initial": {"enabled": True, "message_template": "test"}}
        original_data = {
            **PROFILE_SUBENTRY_DATA,
            "phases": original_phases,
        }
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            options={},
            title="Test",
            subentries_data=[
                ConfigSubentryData(
                    data=original_data,
                    subentry_type="profile",
                    title="Test",
                    unique_id="deep_copy_test",
                ),
            ],
        )
        entry.add_to_hass(hass)

        subentry_id = next(
            s.subentry_id for s in entry.subentries.values() if s.subentry_type == "profile"
        )
        result = await _start_profile_reconfigure(hass, entry, subentry_id)
        assert result["type"] is FlowResultType.MENU
        # Original subentry data must not have been mutated by the flow init.
        subentry = next(s for s in entry.subentries.values() if s.subentry_type == "profile")
        assert subentry.data["phases"] == original_phases
        assert subentry.data["phases"]["initial"] is original_phases["initial"]

    async def test_reconfigure_roundtrip_preserves_all_values(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Reconfigure round-trip: all customized values survive each step submission."""
        # Add tracked objects to the mock Frigate config for the objects selector.
        frigate_config = mock_frigate_data[FRIGATE_ENTRY_ID]["config"]
        frigate_config["cameras"]["driveway"]["objects"] = {"track": ["person", "car", "dog"]}

        full_data: dict[str, Any] = {
            "name": "Full Test",
            "cameras": ["driveway"],
            "provider": "apple",
            "notify_service": "notify.mobile_app_test_phone",
            "tag": "custom-tag-{{ review_id }}",
            "group": "custom-group",
            # Filtering.
            "objects": ["person", "car"],
            "severity": "detection",
            "required_zones": ["driveway_approach"],
            "zone_match_mode": "all",
            "guard_mode": "custom",
            "guard_entity": "input_boolean.armed",
            "time_filter_override": "custom",
            "time_filter_mode": "notify_only_during",
            "time_filter_start": "08:00:00",
            "time_filter_end": "22:00:00",
            "presence_mode": "disabled",
            "state_filter_mode": "custom",
            "state_entity": "binary_sensor.home",
            "state_filter_states": ["on"],
            # Content: title override and zone overrides.
            "title_template": "Custom: {{ camera_name }}",
            "zone_overrides": {"driveway_approach": "arrived at"},
            # Media/Actions: custom actions, tap action, button presets.
            "on_button_action": [
                {"action": "light.turn_on", "target": {"entity_id": "light.porch"}},
            ],
            "tap_action": {"preset": "view_snapshot"},
            "action_config": [{"preset": "view_clip"}, {"preset": "silence"}],
            # Delivery: rate limiting.
            "silence_duration": 45.0,
            "cooldown_override": 120,
            "alert_once": True,
            # Phase configs (all 4 phases with non-default values).
            "phases": {
                "initial": {
                    "enabled": True,
                    "message_template": "Custom initial {{ object }}",
                    "subtitle_template": "sub initial",
                    "emoji_message": False,
                    "emoji_subtitle": True,
                    "attachment": "snapshot",
                    "video": "clip_mp4",
                    "use_latest_detection": False,
                    "custom_actions": [{"action": "notify.log", "data": {"message": "init"}}],
                    "sound": "chime",
                    "volume": 0.75,
                    "interruption_level": "time-sensitive",
                    "critical": True,
                    "delay": 2.0,
                },
                "update": {
                    "enabled": False,
                    "message_template": "Custom update {{ object }}",
                    "subtitle_template": "sub update",
                    "emoji_message": True,
                    "emoji_subtitle": False,
                    "attachment": "review_gif",
                    "video": "none",
                    "use_latest_detection": True,
                    "sound": "none",
                    "volume": 0.0,
                    "interruption_level": "passive",
                    "critical": False,
                    "delay": 3.0,
                },
                "end": {
                    "enabled": True,
                    "message_template": "Custom end {{ object }}",
                    "subtitle_template": "sub end",
                    "emoji_message": True,
                    "emoji_subtitle": True,
                    "attachment": "review_gif",
                    "video": "clip_mp4",
                    "use_latest_detection": True,
                    "sound": "alert",
                    "volume": 0.5,
                    "interruption_level": "active",
                    "critical": False,
                    "delay": 10.0,
                },
                "genai": {
                    "enabled": True,
                    "message_template": "AI says: {{ genai_summary }}",
                    "subtitle_template": "sub genai",
                    "emoji_message": False,
                    "emoji_subtitle": True,
                    "title_prefix_enabled": False,
                    "attachment": "snapshot_cropped",
                    "video": "none",
                    "use_latest_detection": True,
                    "custom_actions": [{"action": "notify.phone", "data": {"message": "genai"}}],
                    "sound": "default",
                    "volume": 1.0,
                    "interruption_level": "passive",
                    "critical": False,
                    "delay": 0.0,
                },
            },
        }
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            options={},
            title="Test",
            subentries_data=[
                ConfigSubentryData(
                    data=full_data,
                    subentry_type="profile",
                    title="Driveway / Full Test",
                    unique_id="roundtrip_test",
                ),
            ],
        )
        entry.add_to_hass(hass)

        subentry_id = next(
            s.subentry_id for s in entry.subentries.values() if s.subentry_type == "profile"
        )
        result = await _start_profile_reconfigure(hass, entry, subentry_id)
        assert result["type"] is FlowResultType.MENU
        flow_id = result["flow_id"]

        # -- Basics step (reconfigure shows identity read-only + target fields) --
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "basics"}
        )
        # Omit read-only identity fields (name, cameras, provider) — the HA frontend
        # does not submit values for read-only selectors; voluptuous defaults fill them.
        result = await hass.config_entries.subentries.async_configure(
            flow_id,
            {
                "notify_service": "notify.mobile_app_test_phone",
                "tag": "custom-tag-{{ review_id }}",
                "group": "custom-group",
            },
        )
        assert result["type"] is FlowResultType.MENU

        # -- Filtering step --
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "filtering"}
        )
        result = await hass.config_entries.subentries.async_configure(
            flow_id,
            {
                "objects": ["person", "car"],
                "severity": "detection",
                "required_zones": ["driveway_approach"],
                "zone_match_mode": "all",
                "guard_config": {
                    "guard_mode": "custom",
                    "guard_entity": "input_boolean.armed",
                },
                "time_filter_config": {
                    "time_filter_override": "custom",
                    "time_filter_mode": "notify_only_during",
                    "time_filter_start": "08:00:00",
                    "time_filter_end": "22:00:00",
                },
                "presence_config": {"presence_mode": "disabled"},
                "state_filter_config": {
                    "state_filter_mode": "custom",
                    "state_entity": "binary_sensor.home",
                    "state_filter_states": ["on"],
                },
            },
        )
        assert result["type"] is FlowResultType.MENU

        # -- Content step --
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "content"}
        )
        content_input: dict[str, Any] = {
            "title_template": full_data["title_template"],
            "zone_overrides": {"driveway_approach": "arrived at"},
        }
        for phase_name in ("initial", "update", "end", "genai"):
            p = full_data["phases"][phase_name]
            sec: dict[str, Any] = {
                "enabled": p["enabled"],
                "message_template": p["message_template"],
                "subtitle_template": p["subtitle_template"],
                "emoji_message": p["emoji_message"],
                "emoji_subtitle": p["emoji_subtitle"],
            }
            if phase_name == "genai":
                sec["title_prefix_enabled"] = p["title_prefix_enabled"]
            content_input[f"{phase_name}_content"] = sec
        result = await hass.config_entries.subentries.async_configure(flow_id, content_input)
        assert result["type"] is FlowResultType.MENU

        # -- Media & Actions step --
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "media_actions"}
        )
        media_input: dict[str, Any] = {
            "custom_actions": {
                "initial_custom_actions": full_data["phases"]["initial"]["custom_actions"],
                "genai_custom_actions": full_data["phases"]["genai"]["custom_actions"],
            },
            "tap_action": {"tap_preset": "view_snapshot"},
            "actions_config": {
                "action_1": "view_clip",
                "action_2": "silence",
                "action_3": "none",
            },
            "on_button_action_section": {
                "on_button_action": full_data["on_button_action"],
            },
        }
        # "update" is disabled so its media section is omitted from the schema.
        for phase_name in ("initial", "end", "genai"):
            p = full_data["phases"][phase_name]
            media_sec: dict[str, Any] = {"attachment": p["attachment"]}
            media_sec["video"] = p["video"]
            if phase_name != "initial":
                media_sec["use_latest_detection"] = p["use_latest_detection"]
            media_input[f"{phase_name}_media"] = media_sec
        result = await hass.config_entries.subentries.async_configure(flow_id, media_input)
        assert result["type"] is FlowResultType.MENU

        # -- Delivery step --
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "delivery"}
        )
        delivery_input: dict[str, Any] = {
            "rate_limiting": {
                "silence_duration": 45.0,
                "cooldown_override": 120,
                "alert_once": True,
            },
        }
        # "update" is disabled so its delivery section is omitted from the schema.
        phase_volumes = {"initial": 75, "end": 50, "genai": 100}
        for phase_name in ("initial", "end", "genai"):
            p = full_data["phases"][phase_name]
            delivery_input[f"{phase_name}_delivery"] = {
                "sound": p["sound"],
                "volume": phase_volumes[phase_name],
                "interruption_level": p["interruption_level"],
                "delay": p["delay"],
                "critical": p["critical"],
            }
        result = await hass.config_entries.subentries.async_configure(flow_id, delivery_input)
        assert result["type"] is FlowResultType.MENU

        # -- Save --
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "save"}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        # Retrieve saved data.
        subentry = entry.subentries[subentry_id]
        saved = dict(subentry.data)

        # -- Assert basics --
        assert saved["name"] == "Full Test"
        assert saved["cameras"] == ["driveway"]
        assert saved["provider"] == "apple"
        assert saved["notify_service"] == "notify.mobile_app_test_phone"
        assert saved["tag"] == "custom-tag-{{ review_id }}"
        assert saved["group"] == "custom-group"

        # -- Assert filtering --
        assert saved["objects"] == ["person", "car"]
        assert saved["severity"] == "detection"
        assert saved["required_zones"] == ["driveway_approach"]
        assert saved["zone_match_mode"] == "all"
        assert saved["guard_mode"] == "custom"
        assert saved["guard_entity"] == "input_boolean.armed"
        assert saved["time_filter_override"] == "custom"
        assert saved["time_filter_mode"] == "notify_only_during"
        assert saved["time_filter_start"] == "08:00:00"
        assert saved["time_filter_end"] == "22:00:00"
        assert saved["presence_mode"] == "disabled"
        assert saved["state_filter_mode"] == "custom"
        assert saved["state_entity"] == "binary_sensor.home"
        assert saved["state_filter_states"] == ["on"]

        # -- Assert content --
        assert saved["title_template"] == "Custom: {{ camera_name }}"
        assert saved["zone_overrides"] == {"driveway_approach": "arrived at"}
        # Profile-level prefix text is removed; global-only.
        assert "title_genai_prefixes" not in saved

        # -- Assert media/actions --
        assert saved["tap_action"] == {"preset": "view_snapshot"}
        assert saved["action_config"] == [{"preset": "view_clip"}, {"preset": "silence"}]
        assert saved["on_button_action"] == full_data["on_button_action"]

        # -- Assert rate limiting --
        assert saved["silence_duration"] == 45.0
        assert saved["cooldown_override"] == 120
        assert saved["alert_once"] is True

        # -- Assert all 4 phases --
        for phase_name in ("initial", "update", "end", "genai"):
            expected = full_data["phases"][phase_name]
            actual = saved["phases"][phase_name]
            assert actual["enabled"] == expected["enabled"], f"{phase_name}.enabled"
            assert actual["message_template"] == expected["message_template"], (
                f"{phase_name}.message_template"
            )
            assert actual["subtitle_template"] == expected["subtitle_template"], (
                f"{phase_name}.subtitle_template"
            )
            assert actual["emoji_message"] == expected["emoji_message"], (
                f"{phase_name}.emoji_message"
            )
            assert actual["emoji_subtitle"] == expected["emoji_subtitle"], (
                f"{phase_name}.emoji_subtitle"
            )
            assert actual["attachment"] == expected["attachment"], f"{phase_name}.attachment"
            assert actual["video"] == expected["video"], f"{phase_name}.video"
            assert actual["sound"] == expected["sound"], f"{phase_name}.sound"
            assert actual["volume"] == expected["volume"], f"{phase_name}.volume"
            assert actual["interruption_level"] == expected["interruption_level"], (
                f"{phase_name}.interruption_level"
            )
            assert actual["critical"] == expected["critical"], f"{phase_name}.critical"
            assert actual["delay"] == expected["delay"], f"{phase_name}.delay"

        # GenAI-specific: title_prefix_enabled toggle.
        assert saved["phases"]["genai"]["title_prefix_enabled"] is False

        # Custom actions: only initial and genai had them.
        assert (
            saved["phases"]["initial"]["custom_actions"]
            == (full_data["phases"]["initial"]["custom_actions"])
        )
        assert (
            saved["phases"]["genai"]["custom_actions"]
            == (full_data["phases"]["genai"]["custom_actions"])
        )
        assert "custom_actions" not in saved["phases"]["update"]
        assert "custom_actions" not in saved["phases"]["end"]

    async def test_reconfigure_basics_shows_identity_fields_readonly(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Reconfigure basics step shows identity fields as read-only."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            options={},
            title="Test",
            subentries_data=[
                ConfigSubentryData(
                    data=PROFILE_SUBENTRY_DATA,
                    subentry_type="profile",
                    title="Test Profile",
                    unique_id="test_identity_lock",
                ),
            ],
        )
        entry.add_to_hass(hass)
        subentry_id = next(
            s.subentry_id for s in entry.subentries.values() if s.subentry_type == "profile"
        )
        result = await _start_profile_reconfigure(hass, entry, subentry_id)
        flow_id = result["flow_id"]
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"next_step_id": "basics"}
        )
        assert result["step_id"] == "basics"
        keys = _schema_section_keys(result)
        # Identity fields are present but read-only.
        assert "name" in keys
        assert "cameras" in keys
        assert "provider" in keys
        # Editable target fields are also present.
        assert "notify_service" in keys
