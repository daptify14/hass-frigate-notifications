"""Tests for diagnostics."""

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.frigate_notifications.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import setup_integration
from .payloads import REVIEW_NEW_PAYLOAD, REVIEW_UPDATE_VERIFIED_PAYLOAD

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

    async def test_diagnostics_summarizes_review_history_without_sub_labels(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Retained reviews are listed per step with sub-labels left out."""
        await setup_integration(hass, mock_config_entry)
        history = mock_config_entry.runtime_data.review_history
        assert history is not None
        history.record(REVIEW_NEW_PAYLOAD, 1.0)
        history.record(REVIEW_UPDATE_VERIFIED_PAYLOAD, 2.0)

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        (record,) = result["review_history"]
        assert record["review_id"] == REVIEW_NEW_PAYLOAD["after"]["id"]
        assert record["camera"] == "driveway"
        assert record["truncated"] is False
        assert [s["lifecycle"] for s in record["steps"]] == ["new", "update"]
        assert record["steps"][1]["objects"] == ["person-verified"]
        assert record["steps"][1]["detection_count"] == 1
        assert "sub_labels" not in record["steps"][1]

    async def test_diagnostics_history_null_when_disabled(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """History is reported as null when retention is off."""
        mock_config_entry.add_to_hass(hass)
        hass.config_entries.async_update_entry(
            mock_config_entry,
            options={**mock_config_entry.options, "keep_review_history": False},
        )
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)
        assert result["review_history"] is None
