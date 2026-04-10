"""Tests for silence datetime, silenced binary sensor, and silence/clear buttons."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache,
)

from custom_components.frigate_notifications.const import DOMAIN

from .conftest import get_profile_subentry_id, setup_integration

pytestmark = pytest.mark.usefixtures("mqtt_mock_no_linger")


class TestSilenceDateTime:
    """Tests for the silence datetime entity."""

    async def test_silence_datetime_initial_state_none(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Silence datetime starts with no value."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_{sub_id}_silenced_until"

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id("datetime", DOMAIN, unique_id)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "unknown"

    async def test_silence_activate_sets_value(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """activate() sets the datetime to now + duration."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]

        now = dt_util.utcnow()
        with patch(
            "custom_components.frigate_notifications.datetime.dt_util.utcnow",
            return_value=now,
        ):
            dt_entity.activate(duration_minutes=15)
            await hass.async_block_till_done()

        assert dt_entity.native_value is not None
        # Should be approximately 15 minutes from now.
        diff = (dt_entity.native_value - now).total_seconds()
        assert 890 < diff < 910  # ~15 min +/- small tolerance.

    async def test_silence_clear_resets_value(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """clear() resets the datetime to None."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]

        dt_entity.activate(duration_minutes=10)
        await hass.async_block_till_done()
        assert dt_entity.native_value is not None

        dt_entity.clear()
        assert dt_entity.native_value is None

    async def test_silence_auto_clear_on_expiry(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Silence auto-clears when the timer expires."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]

        dt_entity.activate(duration_minutes=1)
        await hass.async_block_till_done()
        assert dt_entity.native_value is not None

        # Fast-forward past expiry.
        future = dt_util.utcnow() + timedelta(minutes=2)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        assert dt_entity.native_value is None

    async def test_silence_reactivation_cancels_previous_timer(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Re-activating silence cancels the first timer."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]

        dt_entity.activate(duration_minutes=1)
        await hass.async_block_till_done()
        first_value = dt_entity.native_value

        dt_entity.activate(duration_minutes=60)
        await hass.async_block_till_done()
        second_value = dt_entity.native_value
        assert second_value is not None
        assert second_value != first_value

        # Fast-forward past first timer but not second — should still be silenced.
        future = dt_util.utcnow() + timedelta(minutes=2)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert dt_entity.native_value is not None

    async def test_silence_async_set_value(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """async_set_value sets datetime and schedules expiry."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]

        target = dt_util.utcnow() + timedelta(minutes=10)
        await dt_entity.async_set_value(target)
        await hass.async_block_till_done()
        assert dt_entity.native_value == target

        # Fast-forward past the set time — should auto-clear.
        future = dt_util.utcnow() + timedelta(minutes=11)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert dt_entity.native_value is None

    async def test_silence_default_duration_attribute(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Silence datetime exposes default_duration_minutes attribute."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_{sub_id}_silenced_until"

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id("datetime", DOMAIN, unique_id)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes.get("default_duration_minutes") == 30

    async def test_restore_future_datetime_resumes_silence(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Restoring a future datetime resumes silence with timer."""
        # Manual setup: must pre-register entity and mock restore cache before async_setup.
        mock_config_entry.add_to_hass(hass)
        # Pre-register the entity so we know the entity_id for restore cache.
        from homeassistant.helpers import entity_registry as er

        sub_id = get_profile_subentry_id(mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_{sub_id}_silenced_until"
        ent_reg = er.async_get(hass)
        ent_entry = ent_reg.async_get_or_create(
            "datetime",
            DOMAIN,
            unique_id,
            config_entry=mock_config_entry,
        )
        future = (dt_util.utcnow() + timedelta(hours=1)).isoformat()
        mock_restore_cache(hass, [State(ent_entry.entity_id, future)])

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]
        assert dt_entity.native_value is not None

    async def test_restore_past_datetime_clears(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Restoring a past datetime clears to None."""
        # Manual setup: must pre-register entity and mock restore cache before async_setup.
        mock_config_entry.add_to_hass(hass)
        from homeassistant.helpers import entity_registry as er

        sub_id = get_profile_subentry_id(mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_{sub_id}_silenced_until"
        ent_reg = er.async_get(hass)
        ent_entry = ent_reg.async_get_or_create(
            "datetime",
            DOMAIN,
            unique_id,
            config_entry=mock_config_entry,
        )
        past = (dt_util.utcnow() - timedelta(hours=1)).isoformat()
        mock_restore_cache(hass, [State(ent_entry.entity_id, past)])

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]
        assert dt_entity.native_value is None

    async def test_restore_malformed_state_warns(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Restoring a malformed datetime logs a warning and clears to None."""
        mock_config_entry.add_to_hass(hass)
        from homeassistant.helpers import entity_registry as er

        sub_id = get_profile_subentry_id(mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_{sub_id}_silenced_until"
        ent_reg = er.async_get(hass)
        ent_entry = ent_reg.async_get_or_create(
            "datetime",
            DOMAIN,
            unique_id,
            config_entry=mock_config_entry,
        )
        mock_restore_cache(hass, [State(ent_entry.entity_id, "garbage-value")])

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]
        assert dt_entity.native_value is None
        assert "Could not restore silence state 'garbage-value'" in caplog.text


class TestSilenceButtons:
    """Tests for silence and clear silence buttons."""

    async def test_silence_button_activates_datetime(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Pressing silence button activates the datetime entity."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_{sub_id}_silence"

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id("button", DOMAIN, unique_id)
        assert entity_id is not None

        await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
        await hass.async_block_till_done()

        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]
        assert dt_entity.native_value is not None

    async def test_clear_silence_button_clears_datetime(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Pressing clear button clears the datetime entity."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        # First silence.
        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]
        dt_entity.activate()
        await hass.async_block_till_done()
        assert dt_entity.native_value is not None

        # Press clear button.
        unique_id = f"{mock_config_entry.entry_id}_{sub_id}_clear_silence"
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id("button", DOMAIN, unique_id)
        await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
        await hass.async_block_till_done()

        assert dt_entity.native_value is None


class TestMqttConnectedBinarySensor:
    """Tests for the MQTT connectivity binary sensor."""

    async def test_mqtt_connected_binary_sensor_tracks_connection_status(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Binary sensor updates when MQTT connects and disconnects."""
        from homeassistant.components.mqtt.const import MQTT_CONNECTION_STATE
        from homeassistant.helpers import entity_registry as er
        from homeassistant.helpers.dispatcher import async_dispatcher_send

        await setup_integration(hass, mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_mqtt_connected"

        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
        assert entity_id is not None

        # Plugin mqtt_mock starts connected, so binary sensor should be on.
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on"

        async_dispatcher_send(hass, MQTT_CONNECTION_STATE, False)
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "off"

        async_dispatcher_send(hass, MQTT_CONNECTION_STATE, True)
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on"


class TestSilencedBinarySensor:
    """Tests for the silenced binary sensor."""

    async def test_silenced_binary_sensor_on_when_silenced(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Binary sensor turns on when profile is silenced via activate().

        The binary sensor subscribes to the SIGNAL_SILENCE_STATE dispatcher
        signal (not entity registry state tracking), so it receives updates
        regardless of platform startup order.
        """
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        bs_unique_id = f"{mock_config_entry.entry_id}_{sub_id}_silenced"
        bs_entity_id = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, bs_unique_id)
        assert bs_entity_id is not None

        # Activate silence — datetime broadcasts SIGNAL_SILENCE_STATE,
        # binary sensor picks it up via async_dispatcher_connect.
        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]
        dt_entity.activate(duration_minutes=30)
        await hass.async_block_till_done()

        state = hass.states.get(bs_entity_id)
        assert state is not None
        assert state.state == "on"

        # Clear silence — binary sensor should go back to off.
        dt_entity.clear()
        await hass.async_block_till_done()

        state = hass.states.get(bs_entity_id)
        assert state is not None
        assert state.state == "off"

    async def test_silenced_binary_sensor_off_after_expiry(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Binary sensor turns off automatically when silence expires."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        bs_unique_id = f"{mock_config_entry.entry_id}_{sub_id}_silenced"
        bs_entity_id = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, bs_unique_id)
        assert bs_entity_id is not None

        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]
        dt_entity.activate(duration_minutes=1)
        await hass.async_block_till_done()

        state = hass.states.get(bs_entity_id)
        assert state is not None
        assert state.state == "on"

        # Fast-forward past expiry — both datetime and binary sensor should clear.
        future = dt_util.utcnow() + timedelta(minutes=2)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get(bs_entity_id)
        assert state is not None
        assert state.state == "off"
