"""Tests for sensor entities."""

from typing import Any

from homeassistant.components.sensor import SensorExtraStoredData
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)

from custom_components.frigate_notifications.const import (
    DOMAIN,
    SIGNAL_DISPATCH_PROBLEM,
    SIGNAL_LAST_SENT,
    SIGNAL_STATS,
)

from .conftest import FRIGATE_DOMAIN, FRIGATE_ENTRY_ID, get_profile_subentry_id, setup_integration

pytestmark = pytest.mark.usefixtures("mqtt_mock_no_linger")


class TestReviewDebugSensor:
    """Tests for the review debug sensor."""

    async def test_debug_sensor_disabled_by_default(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Debug sensor is disabled by default and not registered in runtime_data."""
        await setup_integration(hass, mock_config_entry)
        # Disabled entities don't run async_added_to_hass, so no runtime_data ref.
        assert mock_config_entry.runtime_data.debug_sensor is None

    async def test_debug_sensor_enabled_receives_updates(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Debug sensor receives updates when enabled."""
        await setup_integration(hass, mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_review_debug"

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None

        # Enable the disabled-by-default entity.
        ent_reg.async_update_entity(entity_id, disabled_by=None)
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # After reload, the sensor should be registered in runtime_data.
        sensor = mock_config_entry.runtime_data.debug_sensor
        assert sensor is not None

        payload: dict[str, Any] = {
            "after": {
                "id": "review_123",
                "camera": "driveway",
                "severity": "alert",
                "data": {
                    "objects": ["person"],
                    "zones": ["front_yard"],
                    "detections": ["det1", "det2"],
                },
            }
        }
        sensor.update_from_review("new", payload)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "review_123"
        assert state.attributes["camera"] == "driveway"
        assert state.attributes["detection_count"] == 2
        assert state.attributes["message_type"] == "new"


class TestCameraDiagnosticBinarySensor:
    """Tests for per-camera diagnostic binary sensors."""

    async def test_camera_diagnostic_sensor_disabled_by_default(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Camera diagnostic entities are disabled by default."""
        await setup_integration(hass, mock_config_entry)
        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id(
            "binary_sensor",
            DOMAIN,
            f"{mock_config_entry.entry_id}_camera_driveway",
        )
        assert entity_id is not None
        entry = ent_reg.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is not None

    async def test_camera_diagnostic_sensor_reports_genai_from_config(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Camera diagnostic attributes reflect Frigate config genai.enabled."""
        # Override backyard GenAI to disabled in the already-injected config.
        hass.data[FRIGATE_DOMAIN][FRIGATE_ENTRY_ID]["config"]["cameras"]["backyard"]["review"][
            "genai"
        ]["enabled"] = False

        await setup_integration(hass, mock_config_entry)

        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id(
            "binary_sensor",
            DOMAIN,
            f"{mock_config_entry.entry_id}_camera_backyard",
        )
        assert entity_id is not None
        ent_reg.async_update_entity(entity_id, disabled_by=None)
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on"
        assert state.attributes["camera"] == "backyard"
        assert state.attributes["genai"] is False


class TestStatsSensor:
    """Tests for the stats sensor."""

    async def test_stats_sensor_increments_on_signal(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Stats sensor increments when dispatcher sends signal."""
        await setup_integration(hass, mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_stats"

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None

        signal = f"{SIGNAL_STATS}_{mock_config_entry.entry_id}"
        async_dispatcher_send(hass, signal, "driveway", "Test Profile")
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "1"
        assert state.attributes["by_camera"]["driveway"] == 1
        assert state.attributes["by_profile"]["Test Profile"] == 1

        # Send additional signals to verify accumulation.
        async_dispatcher_send(hass, signal, "driveway", "Test Profile")
        async_dispatcher_send(hass, signal, "backyard", "Profile B")
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "3"
        assert state.attributes["by_camera"]["driveway"] == 2
        assert state.attributes["by_camera"]["backyard"] == 1

    async def test_stats_sensor_restores_state(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Stats sensor restores native_value and per-camera/profile attributes."""
        mock_config_entry.add_to_hass(hass)
        unique_id = f"{mock_config_entry.entry_id}_stats"

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        ent_entry = ent_reg.async_get_or_create(
            "sensor", DOMAIN, unique_id, config_entry=mock_config_entry
        )
        mock_restore_cache_with_extra_data(
            hass,
            [
                (
                    State(
                        ent_entry.entity_id,
                        "5",
                        {"by_camera": {"driveway": 3}, "by_profile": {"Alerts": 5}},
                    ),
                    SensorExtraStoredData(
                        native_value=5, native_unit_of_measurement=None
                    ).as_dict(),
                )
            ],
        )

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(ent_entry.entity_id)
        assert state is not None
        assert state.state == "5"
        assert state.attributes["by_camera"]["driveway"] == 3
        assert state.attributes["by_profile"]["Alerts"] == 5

    async def test_stats_sensor_restores_invalid_value_as_zero(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Stats sensor falls back to 0 when restored value is not numeric."""
        mock_config_entry.add_to_hass(hass)
        unique_id = f"{mock_config_entry.entry_id}_stats"

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        ent_entry = ent_reg.async_get_or_create(
            "sensor", DOMAIN, unique_id, config_entry=mock_config_entry
        )
        mock_restore_cache_with_extra_data(
            hass,
            [
                (
                    State(ent_entry.entity_id, "not_a_number"),
                    SensorExtraStoredData(
                        native_value="not_a_number", native_unit_of_measurement=None
                    ).as_dict(),
                )
            ],
        )

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(ent_entry.entity_id)
        assert state is not None
        assert state.state == "0"

    async def test_reset_stats_button_zeroes_counters(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Reset stats button zeros the counter and breakdowns."""
        await setup_integration(hass, mock_config_entry)
        stats_unique_id = f"{mock_config_entry.entry_id}_stats"

        ent_reg = er.async_get(hass)
        stats_entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, stats_unique_id)
        assert stats_entity_id is not None

        # Increment a few times.
        signal = f"{SIGNAL_STATS}_{mock_config_entry.entry_id}"
        async_dispatcher_send(hass, signal, "driveway", "Test Profile")
        async_dispatcher_send(hass, signal, "backyard", "Profile B")
        await hass.async_block_till_done()

        state = hass.states.get(stats_entity_id)
        assert state is not None
        assert state.state == "2"

        # Press the reset button.
        button_unique_id = f"{mock_config_entry.entry_id}_reset_stats"
        button_entity_id = ent_reg.async_get_entity_id("button", DOMAIN, button_unique_id)
        assert button_entity_id is not None

        await hass.services.async_call("button", "press", {"entity_id": button_entity_id})
        await hass.async_block_till_done()

        state = hass.states.get(stats_entity_id)
        assert state is not None
        assert state.state == "0"
        assert state.attributes["by_camera"] == {}
        assert state.attributes["by_profile"] == {}

    async def test_stats_sensor_registered_in_runtime_data(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Stats sensor is registered in runtime_data after setup."""
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.runtime_data.stats_sensor is not None


class TestLastSentSensor:
    """Tests for the last sent sensor."""

    async def test_last_sent_sensor_updates_on_signal(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Last sent sensor updates when dispatcher sends signal."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_{sub_id}_last_sent"

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None

        # Enable the disabled-by-default entity.
        ent_reg.async_update_entity(entity_id, disabled_by=None)
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        signal = f"{SIGNAL_LAST_SENT}_{mock_config_entry.entry_id}_{sub_id}"
        async_dispatcher_send(
            hass, signal, "review_abc", "initial", "Motion Detected", "Person in yard"
        )
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "review_abc"
        assert state.attributes["phase"] == "initial"
        assert state.attributes["title"] == "Motion Detected"
        assert state.attributes["message"] == "Person in yard"

    async def test_last_sent_sensor_restores_state(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Last sent sensor restores review_id and attributes from previous state."""
        mock_config_entry.add_to_hass(hass)
        sub_id = get_profile_subentry_id(mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_{sub_id}_last_sent"

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        ent_entry = ent_reg.async_get_or_create(
            "sensor", DOMAIN, unique_id, config_entry=mock_config_entry
        )
        # Enable it (disabled by default).
        ent_reg.async_update_entity(ent_entry.entity_id, disabled_by=None)

        mock_restore_cache(
            hass,
            [State(ent_entry.entity_id, "review_xyz", {"phase": "end", "title": "Done"})],
        )

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(ent_entry.entity_id)
        assert state is not None
        assert state.state == "review_xyz"
        assert state.attributes["phase"] == "end"


class TestDispatchProblemBinarySensor:
    """Tests for the dispatch problem binary sensor."""

    async def test_dispatch_problem_sensor_off_by_default(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Dispatch problem sensor starts as off."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_{sub_id}_dispatch_problem"

        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
        assert entity_id is not None

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "off"

    async def test_dispatch_problem_sensor_turns_on_on_failure(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Dispatch problem sensor turns on when error signal received."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_{sub_id}_dispatch_problem"

        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
        assert entity_id is not None

        signal = f"{SIGNAL_DISPATCH_PROBLEM}_{mock_config_entry.entry_id}_{sub_id}"
        async_dispatcher_send(hass, signal, "Service not found")
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on"
        assert state.attributes["last_error"] == "Service not found"

    async def test_dispatch_problem_sensor_clears_on_success(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Dispatch problem sensor clears when None signal received."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_{sub_id}_dispatch_problem"

        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
        assert entity_id is not None

        signal = f"{SIGNAL_DISPATCH_PROBLEM}_{mock_config_entry.entry_id}_{sub_id}"

        # First: set problem state.
        async_dispatcher_send(hass, signal, "Connection refused")
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on"

        # Then: clear it.
        async_dispatcher_send(hass, signal, None)
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "off"
        assert "last_error" not in state.attributes
