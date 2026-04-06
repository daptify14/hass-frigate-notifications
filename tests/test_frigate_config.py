"""Tests for the Frigate config adapter normalization boundary."""

from typing import Any
from unittest.mock import MagicMock

from custom_components.frigate_notifications.frigate_config import (
    get_frigate_config_view,
)

ENTRY_ID = "frigate_test"


def _make_hass(frigate_data: dict[str, Any] | None = None) -> MagicMock:
    """Build a mock hass with optional Frigate data in hass.data."""
    hass = MagicMock()
    if frigate_data is not None:
        hass.data = {"frigate": {ENTRY_ID: frigate_data}}
    else:
        hass.data = {}
    return hass


class TestFrigateConfigAdapter:
    """Normalization tests for get_frigate_config_view."""

    def test_missing_entry_returns_none(self) -> None:
        """Returns None when Frigate entry is not in hass.data."""
        assert get_frigate_config_view(_make_hass(), ENTRY_ID) is None

        hass = MagicMock()
        hass.data = {"frigate": {}}
        assert get_frigate_config_view(hass, ENTRY_ID) is None

        hass.data = {"frigate": {ENTRY_ID: {}}}
        assert get_frigate_config_view(hass, ENTRY_ID) is None

    def test_malformed_nested_values_degrade_safely(self) -> None:
        """Truthy non-dict values at every nesting level produce safe defaults."""
        hass = _make_hass(
            {
                "config": {
                    "cameras": {
                        "cam1": {
                            "zones": "not_a_dict",
                            "objects": "not_a_dict",
                            "review": True,
                        },
                    },
                    "mqtt": "not_a_dict",
                },
            }
        )
        view = get_frigate_config_view(hass, ENTRY_ID)
        assert view is not None
        cam = view.get_camera("cam1")
        assert cam is not None
        assert cam.zones == ()
        assert cam.tracked_objects == ()
        assert cam.genai_enabled is False
        assert view.topic_prefix == "frigate"

        # Deeper malformed nesting: objects is dict but track is not a list.
        hass2 = _make_hass(
            {
                "config": {
                    "cameras": {
                        "cam2": {
                            "objects": {"track": "not_a_list"},
                            "review": {"genai": "not_a_dict"},
                        },
                    },
                },
            }
        )
        view2 = get_frigate_config_view(hass2, ENTRY_ID)
        assert view2 is not None
        cam2 = view2.get_camera("cam2")
        assert cam2 is not None
        assert cam2.tracked_objects == ()
        assert cam2.genai_enabled is False

    def test_full_config_round_trip(self) -> None:
        """Normal multi-camera config produces correct typed view."""
        hass = _make_hass(
            {
                "config": {
                    "cameras": {
                        "driveway": {
                            "zones": {"front_yard": {}, "street": {}},
                            "objects": {"track": ["person", "car"]},
                            "review": {"genai": {"enabled": True}},
                        },
                        "backyard": {
                            "zones": {"patio": {}},
                            "objects": {"track": ["dog"]},
                            "review": {"genai": {"enabled": False}},
                        },
                    },
                    "mqtt": {"topic_prefix": "custom_prefix"},
                },
            }
        )
        view = get_frigate_config_view(hass, ENTRY_ID)
        assert view is not None
        assert view.entry_id == ENTRY_ID
        assert view.topic_prefix == "custom_prefix"
        assert view.camera_names() == {"driveway", "backyard"}

        driveway = view.get_camera("driveway")
        assert driveway is not None
        assert set(driveway.zones) == {"front_yard", "street"}
        assert set(driveway.tracked_objects) == {"person", "car"}
        assert driveway.genai_enabled is True

        backyard = view.get_camera("backyard")
        assert backyard is not None
        assert backyard.zones == ("patio",)
        assert backyard.tracked_objects == ("dog",)
        assert backyard.genai_enabled is False

        assert view.get_camera("nonexistent") is None
        assert view.get_camera_zones("nonexistent") == ()
        assert view.get_tracked_objects("nonexistent") == ()
        assert view.camera_supports_genai("nonexistent") is False

    def test_non_dict_camera_preserves_presence(self) -> None:
        """Camera with non-dict value still appears in camera_names()."""
        hass = _make_hass(
            {
                "config": {
                    "cameras": {
                        "good_cam": {"zones": {"yard": {}}, "objects": {"track": ["person"]}},
                        "weird_cam": "not_a_dict",
                        "null_cam": None,
                    },
                },
            }
        )
        view = get_frigate_config_view(hass, ENTRY_ID)
        assert view is not None
        assert view.camera_names() == {"good_cam", "weird_cam", "null_cam"}

        weird = view.get_camera("weird_cam")
        assert weird is not None
        assert weird.zones == ()
        assert weird.tracked_objects == ()
        assert weird.genai_enabled is False

    def test_any_genai_enabled_mixed(self) -> None:
        """any_genai_enabled reflects whether at least one camera has genai."""
        hass_none = _make_hass(
            {
                "config": {
                    "cameras": {
                        "cam1": {"review": {"genai": {"enabled": False}}},
                        "cam2": {},
                    },
                },
            }
        )
        view_none = get_frigate_config_view(hass_none, ENTRY_ID)
        assert view_none is not None
        assert view_none.any_genai_enabled() is False

        hass_one = _make_hass(
            {
                "config": {
                    "cameras": {
                        "cam1": {"review": {"genai": {"enabled": True}}},
                        "cam2": {},
                    },
                },
            }
        )
        view_one = get_frigate_config_view(hass_one, ENTRY_ID)
        assert view_one is not None
        assert view_one.any_genai_enabled() is True
