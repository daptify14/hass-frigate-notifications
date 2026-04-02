"""Tests for the enable/disable switch entity."""

from homeassistant.core import HomeAssistant, State
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_restore_cache

from custom_components.frigate_notifications.const import DOMAIN

from .conftest import get_profile_subentry_id, setup_integration

pytestmark = pytest.mark.usefixtures("mqtt_mock_no_linger")


class TestSwitch:
    """Tests for the profile enable/disable switch."""

    async def test_switch_default_on(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Switch defaults to ON (enabled) with CONFIG entity category."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_{sub_id}_enabled"

        from homeassistant.const import EntityCategory
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id("switch", DOMAIN, unique_id)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on"
        entity_entry = ent_reg.async_get(entity_id)
        assert entity_entry is not None
        assert entity_entry.entity_category == EntityCategory.CONFIG

    async def test_switch_turn_off(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Switch can be turned off."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_{sub_id}_enabled"

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id("switch", DOMAIN, unique_id)
        assert entity_id is not None

        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": entity_id}, blocking=True
        )
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "off"

    async def test_switch_restores_off_state(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Switch restores to OFF after restart if previously turned off."""
        mock_config_entry.add_to_hass(hass)
        sub_id = get_profile_subentry_id(mock_config_entry)
        unique_id = f"{mock_config_entry.entry_id}_{sub_id}_enabled"

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        ent_entry = ent_reg.async_get_or_create(
            "switch", DOMAIN, unique_id, config_entry=mock_config_entry
        )
        mock_restore_cache(hass, [State(ent_entry.entity_id, "off")])

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(ent_entry.entity_id)
        assert state is not None
        assert state.state == "off"
