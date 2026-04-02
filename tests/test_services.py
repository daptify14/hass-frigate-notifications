"""Tests for service registration and handlers."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.frigate_notifications.const import DOMAIN, SILENCE_DATETIMES_KEY

from .conftest import get_profile_subentry_id, setup_integration

pytestmark = pytest.mark.usefixtures("mqtt_mock_no_linger")


class TestServiceRegistration:
    """Tests for service registration."""

    async def test_services_idempotent(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Registering services twice does not raise."""
        await setup_integration(hass, mock_config_entry)
        from custom_components.frigate_notifications.services import register_services

        # Should not raise.
        register_services(hass)
        assert hass.services.has_service(DOMAIN, "silence_profile")


class TestSilenceProfileService:
    """Tests for the silence_profile service."""

    async def test_silence_profile_valid(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Silencing a valid profile activates the datetime entity."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        await hass.services.async_call(
            DOMAIN,
            "silence_profile",
            {"profile_id": sub_id, "duration": 15},
            blocking=True,
        )
        await hass.async_block_till_done()

        silence_map = hass.data.get(SILENCE_DATETIMES_KEY, {})
        dt_entity = silence_map[sub_id]
        assert dt_entity.native_value is not None

        # Default duration also activates successfully.
        dt_entity.clear()
        await hass.services.async_call(
            DOMAIN,
            "silence_profile",
            {"profile_id": sub_id},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert dt_entity.native_value is not None

    async def test_silence_profile_invalid_raises(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Silencing an invalid profile_id raises ServiceValidationError."""
        await setup_integration(hass, mock_config_entry)

        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN,
                "silence_profile",
                {"profile_id": "nonexistent_profile"},
                blocking=True,
            )

    async def test_silence_entity_error_raises_ha_error(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Exception in entity.activate() is wrapped in HomeAssistantError."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        silence_map = hass.data.get(SILENCE_DATETIMES_KEY, {})
        dt_entity = silence_map[sub_id]
        with (
            patch.object(dt_entity, "activate", side_effect=RuntimeError("boom")),
            pytest.raises(HomeAssistantError, match="Failed to silence"),
        ):
            await hass.services.async_call(
                DOMAIN,
                "silence_profile",
                {"profile_id": sub_id, "duration": 15},
                blocking=True,
            )


class TestClearSilenceService:
    """Tests for the clear_silence service."""

    async def test_clear_silence_valid(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Clearing silence for a valid profile works."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        # First silence.
        silence_map = hass.data.get(SILENCE_DATETIMES_KEY, {})
        dt_entity = silence_map[sub_id]
        dt_entity.activate()
        await hass.async_block_till_done()

        await hass.services.async_call(
            DOMAIN,
            "clear_silence",
            {"profile_id": sub_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert dt_entity.native_value is None

    async def test_clear_entity_error_raises_ha_error(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Exception in entity.clear() is wrapped in HomeAssistantError."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        silence_map = hass.data.get(SILENCE_DATETIMES_KEY, {})
        dt_entity = silence_map[sub_id]
        with (
            patch.object(dt_entity, "clear", side_effect=RuntimeError("boom")),
            pytest.raises(HomeAssistantError, match="Failed to clear"),
        ):
            await hass.services.async_call(
                DOMAIN,
                "clear_silence",
                {"profile_id": sub_id},
                blocking=True,
            )

    async def test_clear_silence_invalid_raises(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Clearing silence for invalid profile_id raises."""
        await setup_integration(hass, mock_config_entry)

        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN,
                "clear_silence",
                {"profile_id": "bad_id"},
                blocking=True,
            )
