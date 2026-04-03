"""Tests for the main config flow."""

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.frigate_notifications.const import DOMAIN

from .conftest import FRIGATE_ENTRY_ID


class TestMainFlow:
    """Main config flow tests."""

    async def test_user_step_creates_entry(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Test happy path: select Frigate instance -> create entry."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"frigate_entry_id": FRIGATE_ENTRY_ID}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["frigate_entry_id"] == FRIGATE_ENTRY_ID
        assert "Notifications for Frigate" in result["title"]

    async def test_user_step_aborts_no_frigate(self, hass: HomeAssistant) -> None:
        """Test abort when no Frigate integration loaded."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "frigate_not_loaded"

    async def test_user_step_prevents_duplicate(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Test duplicate entry prevented by unique ID."""
        # Create first entry.
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"frigate_entry_id": FRIGATE_ENTRY_ID}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

        # Second attempt should abort.
        result2 = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result2 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"frigate_entry_id": FRIGATE_ENTRY_ID}
        )
        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "already_configured"
