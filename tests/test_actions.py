"""Tests for notification action listener."""

import copy
import json
from unittest.mock import patch

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.frigate_notifications.actions import _infer_review_phase
from custom_components.frigate_notifications.const import DOMAIN, SILENCE_DATETIMES_KEY
from custom_components.frigate_notifications.enums import Lifecycle, Phase

from .conftest import (
    FRIGATE_ENTRY_ID,
    PROFILE_SUBENTRY_DATA,
    get_profile_subentry_id,
    setup_integration,
)
from .factories import make_genai, make_review
from .payloads import REVIEW_NEW_PAYLOAD

pytestmark = pytest.mark.usefixtures("mqtt_mock_no_linger")


def _make_button_action_entry() -> MockConfigEntry:
    """Create an entry with a profile-level custom button action."""
    profile_data = {
        **PROFILE_SUBENTRY_DATA,
        "on_button_action": [{"action": "test.event"}],
    }
    # Replace "cameras" key from PROFILE_SUBENTRY_DATA (list form for stored data)
    return MockConfigEntry(
        domain=DOMAIN,
        title="Notifications for Frigate",
        data={"frigate_entry_id": FRIGATE_ENTRY_ID},
        options={},
        subentries_data=[
            ConfigSubentryData(
                data=profile_data,
                subentry_type="profile",
                title="Test Profile",
                unique_id="test_profile_uid",
            ),
            ConfigSubentryData(
                data={},
                subentry_type="integration",
                title="Integration",
                unique_id="integration_uid",
            ),
        ],
    )


class TestActionListener:
    """Tests for the notification action listener."""

    async def test_silence_action_activates_datetime(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Silence action event activates the datetime entity."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        hass.bus.async_fire(
            "mobile_app_notification_action",
            {"action": f"silence-{DOMAIN}:profile:{sub_id}"},
        )
        await hass.async_block_till_done()

        silence_map = hass.data.get(SILENCE_DATETIMES_KEY, {})
        dt_entity = silence_map[sub_id]
        assert dt_entity.native_value is not None

    async def test_silence_action_unknown_profile(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Silence action for unknown profile logs warning but doesn't crash."""
        await setup_integration(hass, mock_config_entry)

        hass.bus.async_fire(
            "mobile_app_notification_action",
            {"action": f"silence-{DOMAIN}:profile:nonexistent_id"},
        )
        await hass.async_block_till_done()
        # Should not raise.

    async def test_custom_action_uses_cached_review_context(
        self, hass: HomeAssistant, mock_frigate_data: dict[str, object]
    ) -> None:
        """Custom action uses the cached review template context when available."""
        entry = _make_button_action_entry()
        await setup_integration(hass, entry)
        sub_id = get_profile_subentry_id(entry)
        review_payload = copy.deepcopy(REVIEW_NEW_PAYLOAD)
        review_id = review_payload["after"]["id"]

        await entry.runtime_data.processor.handle_review_message(json.dumps(review_payload))
        await hass.async_block_till_done()

        captured_run_variables: dict[str, object] = {}
        captured_profile_name = ""

        async def _capture(
            _hass: HomeAssistant,
            _actions: tuple[dict, ...],
            run_variables: dict[str, object],
            profile_name: str,
        ) -> None:
            nonlocal captured_profile_name, captured_run_variables
            captured_run_variables = dict(run_variables)
            captured_profile_name = profile_name

        with patch(
            "custom_components.frigate_notifications.dispatcher.execute_custom_actions",
            new=_capture,
        ):
            hass.bus.async_fire(
                "mobile_app_notification_action",
                {"action": f"custom-{DOMAIN}:profile:{sub_id}:review:{review_id}"},
            )
            await hass.async_block_till_done()

        assert captured_run_variables["camera"] == "driveway"
        assert captured_run_variables["object"] == "Person"
        assert captured_run_variables["zone"] == "driveway_approach"
        assert captured_run_variables["review_id"] == review_id
        assert captured_run_variables["profile_id"] == sub_id
        assert captured_run_variables["profile_name"] == "Test Profile"
        assert captured_run_variables["is_initial"] is True
        assert captured_profile_name == "Test Profile"

    async def test_malformed_custom_action_ignored(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Malformed custom action (missing :review: separator) is silently ignored."""
        await setup_integration(hass, mock_config_entry)

        hass.bus.async_fire(
            "mobile_app_notification_action",
            {"action": f"custom-{DOMAIN}:profile:some_id_no_review"},
        )
        await hass.async_block_till_done()
        assert "Malformed custom action" in caplog.text

    async def test_custom_action_no_button_actions_noop(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_frigate_data: dict
    ) -> None:
        """Custom action with no on_button_action configured does nothing."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        with patch(
            "custom_components.frigate_notifications.dispatcher.execute_custom_actions",
        ) as mock_exec:
            hass.bus.async_fire(
                "mobile_app_notification_action",
                {"action": f"custom-{DOMAIN}:profile:{sub_id}:review:some_review"},
            )
            await hass.async_block_till_done()
            mock_exec.assert_not_called()

    async def test_custom_action_expired_review_uses_minimal_context(
        self, hass: HomeAssistant, mock_frigate_data: dict[str, object]
    ) -> None:
        """Custom action falls back to minimal context when the review is gone."""
        entry = _make_button_action_entry()
        await setup_integration(hass, entry)
        sub_id = get_profile_subentry_id(entry)

        captured_run_variables: dict[str, object] = {}
        captured_profile_name = ""

        async def _capture(
            _hass: HomeAssistant,
            _actions: tuple[dict, ...],
            run_variables: dict[str, object],
            profile_name: str,
        ) -> None:
            nonlocal captured_profile_name, captured_run_variables
            captured_run_variables = dict(run_variables)
            captured_profile_name = profile_name

        with patch(
            "custom_components.frigate_notifications.dispatcher.execute_custom_actions",
            new=_capture,
        ):
            hass.bus.async_fire(
                "mobile_app_notification_action",
                {"action": f"custom-{DOMAIN}:profile:{sub_id}:review:expired_review"},
            )
            await hass.async_block_till_done()

        assert captured_run_variables == {
            "camera": "driveway",
            "profile_id": sub_id,
            "profile_name": "Test Profile",
        }
        assert captured_profile_name == "Test Profile"

    async def test_custom_action_expired_review_multi_camera_empty_camera(
        self, hass: HomeAssistant, mock_frigate_data: dict[str, object]
    ) -> None:
        """Multi-camera profile with expired review returns camera=''."""
        profile_data = {
            **PROFILE_SUBENTRY_DATA,
            "cameras": ["driveway", "backyard"],
            "on_button_action": [{"action": "test.event"}],
        }
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Notifications for Frigate",
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            options={},
            subentries_data=[
                ConfigSubentryData(
                    data=profile_data,
                    subentry_type="profile",
                    title="Multi Cam",
                    unique_id="multi_cam_uid",
                ),
                ConfigSubentryData(
                    data={},
                    subentry_type="integration",
                    title="Integration",
                    unique_id="integration_uid",
                ),
            ],
        )
        await setup_integration(hass, entry)
        sub_id = get_profile_subentry_id(entry)

        captured: dict[str, object] = {}

        async def _capture(_hass, _actions, run_variables, _name):
            captured.update(run_variables)

        with patch(
            "custom_components.frigate_notifications.dispatcher.execute_custom_actions",
            new=_capture,
        ):
            hass.bus.async_fire(
                "mobile_app_notification_action",
                {"action": f"custom-{DOMAIN}:profile:{sub_id}:review:expired_review"},
            )
            await hass.async_block_till_done()

        assert captured["camera"] == ""


class TestInferReviewPhase:
    """Tests for _infer_review_phase."""

    @pytest.mark.parametrize(
        ("review_kwargs", "expected_phase", "expected_lifecycle"),
        [
            ({"genai": make_genai()}, Phase.GENAI, Lifecycle.GENAI),
            ({"end_time": 100.0}, Phase.END, Lifecycle.END),
            ({"before_objects": ["person"]}, Phase.UPDATE, Lifecycle.UPDATE),
            ({}, Phase.INITIAL, Lifecycle.NEW),
        ],
        ids=["genai", "end", "update", "initial"],
    )
    def test_infer_review_phase(
        self,
        review_kwargs: dict,
        expected_phase: Phase,
        expected_lifecycle: Lifecycle,
    ) -> None:
        review = make_review(**review_kwargs)
        phase, lifecycle = _infer_review_phase(review)
        assert phase == expected_phase
        assert lifecycle == expected_lifecycle
