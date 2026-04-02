"""Shared helper functions for config flow tests."""

from typing import Any

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.frigate_notifications.const import DOMAIN

from .conftest import FRIGATE_ENTRY_ID


def _make_profile_entry(hass: HomeAssistant, mock_frigate_data: dict) -> MockConfigEntry:
    """Create a config entry for profile flow testing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"frigate_entry_id": FRIGATE_ENTRY_ID},
        options={},
        title="Notifications for Frigate",
    )
    entry.add_to_hass(hass)
    return entry


def _schema_section_keys(result: Any) -> set[str]:
    """Extract top-level section key names from a form result's data_schema."""
    schema = result["data_schema"].schema
    return {k.schema if hasattr(k, "schema") else str(k) for k in schema}


async def _advance_to_menu(hass: HomeAssistant, entry: MockConfigEntry) -> tuple[str, Any]:
    """Drive a new profile wizard through preset -> basics -> customize menu.

    Returns (flow_id, menu_result).
    """
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "profile"), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"preset": "custom"}
    )
    # Basics pass 1.
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Test", "cameras": ["driveway"], "provider": "apple"},
    )
    # Basics pass 2.
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Test",
            "cameras": ["driveway"],
            "provider": "apple",
            "notify_service": "notify.test_phone",
        },
    )
    assert result["step_id"] == "customize"
    return result["flow_id"], result


async def _advance_to_content(hass: HomeAssistant, entry: MockConfigEntry) -> tuple[str, Any]:
    """Drive a new profile wizard through preset -> basics -> menu -> content form.

    Returns (flow_id, content_form_result).
    """
    flow_id, result = await _advance_to_menu(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"next_step_id": "content"}
    )
    assert result["step_id"] == "content"
    return flow_id, result


async def _advance_tv_to_content(hass: HomeAssistant, entry: MockConfigEntry) -> tuple[str, Any]:
    """Drive a TV profile wizard through preset -> basics -> menu -> content form."""
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "profile"), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"preset": "custom"}
    )
    # Basics pass 1.
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "TV", "cameras": ["driveway"], "provider": "android_tv"},
    )
    # Basics pass 2.
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "TV",
            "cameras": ["driveway"],
            "provider": "android_tv",
            "notify_service": "notify.fire_tv",
        },
    )
    assert result["step_id"] == "customize"
    # Enter content from menu.
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "content"}
    )
    assert result["step_id"] == "content"
    return result["flow_id"], result
