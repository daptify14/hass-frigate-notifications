"""Tests for entity-registry-based discovery helpers."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.frigate_notifications.const import DOMAIN, FRIGATE_DOMAIN
from custom_components.frigate_notifications.flows.helpers import (
    discover_all_sub_labels,
    discover_camera_sub_labels,
    discover_typed_sub_labels,
    get_camera_recognition,
)

from .conftest import FRIGATE_ENTRY_ID

_P = f"{FRIGATE_ENTRY_ID}:"


@pytest.fixture
def fce(hass: HomeAssistant) -> MockConfigEntry:
    """Create and add a mock Frigate config entry for entity registry."""
    entry = MockConfigEntry(
        domain=FRIGATE_DOMAIN,
        entry_id=FRIGATE_ENTRY_ID,
    )
    entry.add_to_hass(hass)
    return entry


def _reg(
    ent_reg: er.EntityRegistry,
    unique_id: str,
    entry: MockConfigEntry,
    *,
    disabled_by: er.RegistryEntryDisabler | None = None,
) -> None:
    """Register a mock Frigate sensor entity."""
    ent_reg.async_get_or_create(
        "sensor",
        FRIGATE_DOMAIN,
        unique_id,
        config_entry=entry,
        disabled_by=disabled_by,
    )


def _make_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={"frigate_entry_id": FRIGATE_ENTRY_ID},
    )


class TestGetCameraRecognition:
    """Tests for get_camera_recognition."""

    def test_both_types_present(self, hass: HomeAssistant, fce: MockConfigEntry) -> None:
        """Camera with both face rec and LPR sensors returns both True."""
        reg = er.async_get(hass)
        _reg(reg, f"{_P}sensor_recognized_face:driveway", fce)
        _reg(reg, f"{_P}sensor_recognized_plate:driveway", fce)

        result = get_camera_recognition(hass, FRIGATE_ENTRY_ID, "driveway")
        assert result == {"face": True, "lpr": True}

    def test_face_only(self, hass: HomeAssistant, fce: MockConfigEntry) -> None:
        """Camera with only face rec returns face=True, lpr=False."""
        reg = er.async_get(hass)
        _reg(reg, f"{_P}sensor_recognized_face:front_door", fce)

        result = get_camera_recognition(hass, FRIGATE_ENTRY_ID, "front_door")
        assert result == {"face": True, "lpr": False}

    def test_neither_type(self, hass: HomeAssistant) -> None:
        """Camera with no recognition sensors returns both False."""
        result = get_camera_recognition(hass, FRIGATE_ENTRY_ID, "backyard")
        assert result == {"face": False, "lpr": False}


class TestDiscoverTypedSubLabels:
    """Tests for discover_typed_sub_labels."""

    def test_global_returns_all_identities(self, hass: HomeAssistant, fce: MockConfigEntry) -> None:
        """Global discovery (camera=None) returns all face and plate names."""
        reg = er.async_get(hass)
        _reg(reg, f"{_P}sensor_global_face:Alice", fce)
        _reg(reg, f"{_P}sensor_global_face:Bob", fce)
        _reg(reg, f"{_P}sensor_global_plate:Alice's Car", fce)

        result = discover_typed_sub_labels(hass, FRIGATE_ENTRY_ID, camera=None)
        assert result == [
            ("face", "Alice"),
            ("face", "Bob"),
            ("lpr", "Alice's Car"),
        ]

    def test_camera_scoped_face_only(self, hass: HomeAssistant, fce: MockConfigEntry) -> None:
        """Camera with face rec but no LPR only returns face names."""
        reg = er.async_get(hass)
        _reg(reg, f"{_P}sensor_recognized_face:front_door", fce)
        _reg(reg, f"{_P}sensor_global_face:Alice", fce)
        _reg(reg, f"{_P}sensor_global_plate:Bob's Car", fce)

        result = discover_typed_sub_labels(hass, FRIGATE_ENTRY_ID, camera="front_door")
        assert result == [("face", "Alice")]

    def test_camera_with_neither_returns_empty(
        self, hass: HomeAssistant, fce: MockConfigEntry
    ) -> None:
        """Camera without recognition returns empty list."""
        reg = er.async_get(hass)
        _reg(reg, f"{_P}sensor_global_face:Alice", fce)

        result = discover_typed_sub_labels(hass, FRIGATE_ENTRY_ID, camera="backyard")
        assert result == []

    def test_names_with_special_characters(self, hass: HomeAssistant, fce: MockConfigEntry) -> None:
        """Names with spaces, apostrophes, and colons are preserved."""
        reg = er.async_get(hass)
        _reg(reg, f"{_P}sensor_global_face:Bob Jr.", fce)
        _reg(reg, f"{_P}sensor_global_plate:Bob's Car: Primary", fce)

        result = discover_typed_sub_labels(hass, FRIGATE_ENTRY_ID, camera=None)
        assert result == [
            ("face", "Bob Jr."),
            ("lpr", "Bob's Car: Primary"),
        ]

    def test_non_sensor_entities_ignored(self, hass: HomeAssistant, fce: MockConfigEntry) -> None:
        """Non-sensor entities with matching unique_id prefix are ignored."""
        reg = er.async_get(hass)
        reg.async_get_or_create(
            "binary_sensor",
            FRIGATE_DOMAIN,
            f"{_P}sensor_global_face:Alice",
            config_entry=fce,
        )

        result = discover_typed_sub_labels(hass, FRIGATE_ENTRY_ID, camera=None)
        assert result == []

    def test_sorted_output(self, hass: HomeAssistant, fce: MockConfigEntry) -> None:
        """Results are sorted by type then name."""
        reg = er.async_get(hass)
        _reg(reg, f"{_P}sensor_global_plate:Zebra Car", fce)
        _reg(reg, f"{_P}sensor_global_face:Charlie", fce)
        _reg(reg, f"{_P}sensor_global_face:Alice", fce)
        _reg(reg, f"{_P}sensor_global_plate:Alpha Car", fce)

        result = discover_typed_sub_labels(hass, FRIGATE_ENTRY_ID, camera=None)
        assert result == [
            ("face", "Alice"),
            ("face", "Charlie"),
            ("lpr", "Alpha Car"),
            ("lpr", "Zebra Car"),
        ]


class TestDiscoverWrappers:
    """Tests for discover_camera_sub_labels and discover_all_sub_labels."""

    def test_frigate_not_loaded_returns_empty(self, hass: HomeAssistant) -> None:
        """Guard returns empty when Frigate entry not in hass.data."""
        result = discover_all_sub_labels(hass, FRIGATE_ENTRY_ID)
        assert result == []

    def test_camera_frigate_not_loaded_returns_empty(self, hass: HomeAssistant) -> None:
        """Camera wrapper returns empty when Frigate not loaded."""
        result = discover_camera_sub_labels(hass, FRIGATE_ENTRY_ID, "driveway")
        assert result == []
