"""Shared fixtures for Notifications for Frigate tests."""

from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import Any

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.frigate_notifications.const import DOMAIN

pytest_plugins = ["pytest_homeassistant_custom_component"]

FRIGATE_ENTRY_ID = "frigate_entry_01"
MOCK_FRIGATE_CONFIG: dict[str, Any] = {
    "cameras": {
        "driveway": {
            "zones": {"driveway_approach": {}, "front_yard": {}},
            "objects": {"track": ["person", "car"]},
            "review": {"genai": {"enabled": True}},
        },
        "backyard": {
            "zones": {"patio": {}},
            "objects": {"track": ["person", "dog"]},
            "review": {"genai": {"enabled": True}},
        },
    },
    "mqtt": {"topic_prefix": "frigate"},
}

PROFILE_SUBENTRY_DATA: dict[str, Any] = {
    "name": "Test Profile",
    "cameras": ["driveway"],
    "provider": "apple",
    "notify_service": "notify.mobile_app_test_phone",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations in the test environment."""


@pytest.fixture
async def mqtt_mock_no_linger(mqtt_mock: Any) -> AsyncGenerator[Any]:
    """Wrap mqtt_mock to clean up lingering asyncio timers after tests.

    Opt-in only — add ``pytestmark = pytest.mark.usefixtures("mqtt_mock_no_linger")``
    at module level in files that need the full MQTT component.
    """
    yield mqtt_mock
    mock_socket = mqtt_mock._mqttc.socket()
    mock_socket.fileno.return_value = -1
    mqtt_mock._mqttc.on_socket_close(mqtt_mock._mqttc, None, mock_socket)


@pytest.fixture
def mock_frigate_data(hass: HomeAssistant, mock_frigate_entry: MockConfigEntry) -> dict[str, Any]:
    """Inject mock Frigate data into hass.data."""
    data: dict[str, Any] = {
        FRIGATE_ENTRY_ID: {"config": deepcopy(MOCK_FRIGATE_CONFIG)},
    }
    hass.data[FRIGATE_DOMAIN] = data
    return data


def _integration_subentry() -> ConfigSubentryData:
    """Create a fresh integration subentry."""
    return ConfigSubentryData(
        data={},
        subentry_type="integration",
        title="Integration",
        unique_id="integration_uid",
    )


@pytest.fixture
def mock_config_entry(mock_frigate_data: dict[str, Any]) -> MockConfigEntry:
    """Create a MockConfigEntry with profile + integration subentries.

    The integration subentry is pre-created so _ensure_integration_subentry is
    a no-op, avoiding a reload cycle during async_setup_entry.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        title="Notifications for Frigate",
        data={"frigate_entry_id": FRIGATE_ENTRY_ID},
        options={},
        subentries_data=[
            ConfigSubentryData(
                data=PROFILE_SUBENTRY_DATA,
                subentry_type="profile",
                title="Test Profile",
                unique_id="test_profile_uid",
            ),
            _integration_subentry(),
        ],
    )


@pytest.fixture
def mock_config_entry_no_profiles(mock_frigate_data: dict[str, Any]) -> MockConfigEntry:
    """Create a MockConfigEntry with integration subentry but no profiles."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Notifications for Frigate",
        data={"frigate_entry_id": FRIGATE_ENTRY_ID},
        options={},
        subentries_data=[_integration_subentry()],
    )


def get_profile_subentry_id(entry: MockConfigEntry) -> str:
    """Get the first profile subentry_id from an entry."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type == "profile":
            return subentry.subentry_id
    msg = "No profile subentry found"
    raise ValueError(msg)


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add entry to hass and set up."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def template_id_map():
    """Build the template ID map from built-in presets."""
    from custom_components.frigate_notifications.presets import (
        build_template_id_map,
        load_template_presets,
    )

    return build_template_id_map(load_template_presets())


FRIGATE_DOMAIN = "frigate"
FRIGATE_ENTRY_TITLE = "Frigate"
FRIGATE_ENTRY_DATA: dict[str, Any] = {"url": "http://frigate.local:5000"}


@pytest.fixture
def mock_frigate_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock Frigate config entry."""
    entry = MockConfigEntry(
        domain=FRIGATE_DOMAIN,
        title=FRIGATE_ENTRY_TITLE,
        entry_id=FRIGATE_ENTRY_ID,
        data=FRIGATE_ENTRY_DATA,
    )
    entry.add_to_hass(hass)
    return entry
