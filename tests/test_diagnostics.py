"""Tests for diagnostics."""

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.frigate_notifications.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import setup_integration

pytestmark = pytest.mark.usefixtures("mqtt_mock_no_linger")


class TestDiagnostics:
    """Tests for diagnostic data export."""

    async def test_diagnostics_content(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Diagnostics returns expected structure, cameras, MQTT topic, and entry info."""
        await setup_integration(hass, mock_config_entry)

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        # Top-level keys
        assert "entry" in result
        assert "options" in result
        assert "cameras" in result
        assert "profiles" in result
        assert "mqtt" in result

        # Cameras
        assert "driveway" in result["cameras"]
        assert "backyard" in result["cameras"]

        # MQTT topic
        assert result["mqtt"]["topic"] == "frigate/reviews"

        # Entry metadata
        assert result["entry"]["entry_id"] == mock_config_entry.entry_id
        assert result["entry"]["title"] == "Notifications for Frigate"

    async def test_diagnostics_redacts_sensitive_data(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Diagnostics redacts sensitive fields."""
        await setup_integration(hass, mock_config_entry)

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        # Profile data should have name redacted.
        for profile in result["profiles"]:
            assert profile.get("name") == "**REDACTED**"
            if "notify_service" in profile:
                assert profile["notify_service"] == "**REDACTED**"
