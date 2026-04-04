"""Tests for the options flow."""

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.frigate_notifications.const import DOMAIN

from .conftest import FRIGATE_DOMAIN, FRIGATE_ENTRY_ID
from .flow_helpers import _schema_section_keys


async def _enter_menu_section(
    hass: HomeAssistant, entry: MockConfigEntry, section: str
) -> tuple[str, ConfigFlowResult]:
    """Init options flow, verify menu, and enter a section. Returns (flow_id, result)."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "menu"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": section}
    )
    return result["flow_id"], result


async def _save_from_menu(hass: HomeAssistant, flow_id: str) -> ConfigFlowResult:
    """Navigate to save from menu and return result."""
    result = await hass.config_entries.options.async_configure(flow_id, {"next_step_id": "save"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    return result


class TestOptionsFlowMenu:
    """Tests for the menu-based reconfigure mode."""

    @pytest.fixture
    def options_entry(self, hass: HomeAssistant, mock_frigate_data: dict) -> MockConfigEntry:
        """Create an entry with existing options (triggers menu mode)."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            options={"base_url": "http://ha.local:8123"},
            title="Notifications for Frigate",
        )
        entry.add_to_hass(hass)
        return entry

    async def test_init_shows_menu_when_configured(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """Init shows menu when base_url already exists."""
        result = await hass.config_entries.options.async_init(options_entry.entry_id)
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "menu"
        assert "delivery" in result["menu_options"]
        assert "appearance" in result["menu_options"]
        assert "zone_aliases" in result["menu_options"]
        assert "save" in result["menu_options"]

    async def test_menu_delivery_returns_to_menu(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """Delivery step returns to menu after submit."""
        flow_id, result = await _enter_menu_section(hass, options_entry, "delivery")
        assert result["step_id"] == "delivery"

        result = await hass.config_entries.options.async_configure(
            flow_id, {"base_url": "http://ha.local:8123"}
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "menu"

    async def test_menu_appearance_returns_to_menu(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """Appearance step returns to menu after submit."""
        flow_id, result = await _enter_menu_section(hass, options_entry, "appearance")
        assert result["step_id"] == "appearance"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            {
                "title_template": "{{ camera_name }}",
                "emoji_config": {"enable_emojis": True, "default_emoji": "\U0001f514"},
            },
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "menu"

    async def test_menu_zone_aliases_returns_to_menu(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """Zone aliases step returns to menu after submit."""
        flow_id, result = await _enter_menu_section(hass, options_entry, "zone_aliases")
        assert result["step_id"] == "zone_aliases"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            {"Driveway": {"driveway_approach": "Front Walk", "front_yard": "Front Yard"}},
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "menu"

    async def test_menu_save_creates_entry(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """Save from menu creates entry with existing data."""
        result = await hass.config_entries.options.async_init(options_entry.entry_id)
        assert result["type"] is FlowResultType.MENU

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "save"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["base_url"] == "http://ha.local:8123"

    async def test_delivery_with_guard_and_filters(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """Delivery step stores guard entity, time filter, presence, and state filter."""
        flow_id, result = await _enter_menu_section(hass, options_entry, "delivery")

        result = await hass.config_entries.options.async_configure(
            flow_id,
            {
                "base_url": "http://ha.local:8123",
                "guard": {"shared_guard_entity": "input_boolean.armed"},
                "time_filter": {
                    "shared_time_filter_mode": "notify_only_during",
                    "shared_time_filter_start": "08:00:00",
                    "shared_time_filter_end": "22:00:00",
                },
                "presence": {"shared_presence_entities": ["person.user"]},
                "state_filter": {
                    "shared_state_entity": "binary_sensor.test",
                    "shared_state_filter_states": ["on"],
                },
            },
        )
        assert result["type"] is FlowResultType.MENU

        result = await _save_from_menu(hass, flow_id)
        data = result["data"]
        assert data["shared_guard_entity"] == "input_boolean.armed"
        assert data["shared_time_filter_mode"] == "notify_only_during"
        assert data["shared_time_filter_start"] == "08:00:00"
        assert data["shared_presence_entities"] == ["person.user"]
        assert data["shared_state_entity"] == "binary_sensor.test"
        assert data["shared_state_filter_states"] == ["on"]

    async def test_delivery_clears_empty_guard(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Delivery step clears guard, time filter, presence, and state filter when empty."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            options={
                "base_url": "http://ha.local:8123",
                "shared_guard_entity": "input_boolean.old",
                "shared_time_filter_mode": "notify_only_during",
                "shared_time_filter_start": "08:00:00",
                "shared_time_filter_end": "22:00:00",
                "shared_presence_entities": ["person.user"],
                "shared_state_entity": "binary_sensor.test",
                "shared_state_filter_states": ["on"],
            },
            title="Notifications for Frigate",
        )
        entry.add_to_hass(hass)

        flow_id, result = await _enter_menu_section(hass, entry, "delivery")
        result = await hass.config_entries.options.async_configure(
            flow_id, {"base_url": "http://ha.local:8123"}
        )
        assert result["type"] is FlowResultType.MENU

        result = await _save_from_menu(hass, flow_id)
        data = result["data"]
        assert "shared_guard_entity" not in data
        assert "shared_time_filter_mode" not in data
        assert "shared_time_filter_start" not in data
        assert "shared_time_filter_end" not in data
        assert "shared_presence_entities" not in data
        assert "shared_state_entity" not in data
        assert "shared_state_filter_states" not in data

    async def test_appearance_includes_title_template(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """Appearance step includes title_template field and round-trips it."""
        flow_id, result = await _enter_menu_section(hass, options_entry, "appearance")
        assert result["step_id"] == "appearance"

        result = await hass.config_entries.options.async_configure(
            flow_id, {"title_template": "{{ camera_name }}"}
        )
        assert result["type"] is FlowResultType.MENU

        result = await _save_from_menu(hass, flow_id)
        assert result["data"]["title_template"] == "{{ camera_name }}"

    async def test_appearance_title_template_default(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """Submitting appearance with no title_template uses the default preset ID."""
        flow_id, result = await _enter_menu_section(hass, options_entry, "appearance")

        result = await hass.config_entries.options.async_configure(flow_id, {})
        assert result["type"] is FlowResultType.MENU

        result = await _save_from_menu(hass, flow_id)
        assert result["data"]["title_template"] == "camera_time"

    async def test_appearance_custom_emoji_and_overrides(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """Appearance step with custom emoji map stores deltas."""
        flow_id, result = await _enter_menu_section(hass, options_entry, "appearance")

        result = await hass.config_entries.options.async_configure(
            flow_id,
            {
                "emoji_config": {"enable_emojis": True, "default_emoji": "X"},
                "custom_emoji_config": {"emoji_map": {"person": "P", "car": "C"}},
            },
        )
        assert result["type"] is FlowResultType.MENU

        result = await _save_from_menu(hass, flow_id)
        data = result["data"]
        assert data["enable_emojis"] is True
        assert data["emoji_map"] == {"person": "P", "car": "C"}

    async def test_appearance_phase_emoji_overrides(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """Appearance step stores only non-default phase emoji overrides."""
        flow_id, result = await _enter_menu_section(hass, options_entry, "appearance")

        result = await hass.config_entries.options.async_configure(
            flow_id,
            {
                "phase_emoji_config": {
                    "phase_initial": "X",
                    "phase_update": "\U0001f504",
                    "phase_end": "\U0001f51a",
                    "phase_genai": "\u2728",
                },
            },
        )
        assert result["type"] is FlowResultType.MENU

        result = await _save_from_menu(hass, flow_id)
        assert result["data"]["phase_emoji_map"] == {"initial": "X"}

    async def test_appearance_phase_emoji_defaults_not_stored(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """Submitting all default phase emojis does not store phase_emoji_map."""
        flow_id, result = await _enter_menu_section(hass, options_entry, "appearance")

        result = await hass.config_entries.options.async_configure(
            flow_id,
            {
                "phase_emoji_config": {
                    "phase_initial": "\U0001f195",
                    "phase_update": "\U0001f504",
                    "phase_end": "\U0001f51a",
                    "phase_genai": "\u2728",
                },
            },
        )
        assert result["type"] is FlowResultType.MENU

        result = await _save_from_menu(hass, flow_id)
        assert "phase_emoji_map" not in result["data"]

    async def test_appearance_shows_genai_prefix_fields(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """Appearance step exposes GenAI prefix fields for levels 0, 1, and 2."""
        _, result = await _enter_menu_section(hass, options_entry, "appearance")
        assert result["step_id"] == "appearance"
        keys = _schema_section_keys(result)
        assert "genai_prefix_config" in keys

    async def test_appearance_level_0_prefix_roundtrip(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """A non-blank level 0 GenAI prefix is stored in global options."""
        flow_id, result = await _enter_menu_section(hass, options_entry, "appearance")
        result = await hass.config_entries.options.async_configure(
            flow_id,
            {"genai_prefix_config": {"title_genai_prefix_0": "INFO"}},
        )
        assert result["type"] is FlowResultType.MENU

        result = await _save_from_menu(hass, flow_id)
        assert result["data"]["title_genai_prefixes"] == {0: "INFO"}

    async def test_appearance_shows_face_plate_sections(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """Appearance step shows face/plate override sections from entity registry."""
        ent_reg = er.async_get(hass)
        for uid in (
            f"{FRIGATE_ENTRY_ID}:sensor_global_face:Alice",
            f"{FRIGATE_ENTRY_ID}:sensor_global_face:Bob",
            f"{FRIGATE_ENTRY_ID}:sensor_global_plate:Alice's Car",
        ):
            ent_reg.async_get_or_create(
                "sensor",
                FRIGATE_DOMAIN,
                uid,
                config_entry=hass.config_entries.async_get_entry(FRIGATE_ENTRY_ID),
            )

        flow_id, result = await _enter_menu_section(hass, options_entry, "appearance")
        keys = _schema_section_keys(result)
        assert "face_overrides" in keys
        assert "plate_overrides" in keys

        result = await hass.config_entries.options.async_configure(
            flow_id,
            {
                "face_overrides": {"Alice": "\u2705", "Bob": ""},
                "plate_overrides": {"Alice's Car": "\U0001f697"},
            },
        )
        assert result["type"] is FlowResultType.MENU

        result = await _save_from_menu(hass, flow_id)
        data = result["data"]
        assert data["sub_label_overrides"] == {"Alice": "\u2705", "Alice's Car": "\U0001f697"}
        assert "Bob" not in data["sub_label_overrides"]

    async def test_appearance_no_sections_without_identities(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """Appearance step omits face/plate sections when no identities discovered."""
        _, result = await _enter_menu_section(hass, options_entry, "appearance")
        keys = _schema_section_keys(result)
        assert "face_overrides" not in keys
        assert "plate_overrides" not in keys

    async def test_zone_aliases_single_step(
        self, hass: HomeAssistant, options_entry: MockConfigEntry
    ) -> None:
        """Zone aliases single step saves aliases for multiple cameras."""
        flow_id, result = await _enter_menu_section(hass, options_entry, "zone_aliases")
        assert result["step_id"] == "zone_aliases"

        # Both cameras have zones in MOCK_FRIGATE_CONFIG (humanized section names).
        keys = _schema_section_keys(result)
        assert "Driveway" in keys
        assert "Backyard" in keys

        result = await hass.config_entries.options.async_configure(
            flow_id,
            {
                "Driveway": {"driveway_approach": "Front Walk", "front_yard": ""},
                "Backyard": {"patio": "Back Patio"},
            },
        )
        assert result["type"] is FlowResultType.MENU

        result = await _save_from_menu(hass, flow_id)
        aliases = result["data"]["zone_aliases"]
        assert aliases["driveway"] == {"driveway_approach": "Front Walk"}
        assert aliases["backyard"] == {"patio": "Back Patio"}

    async def test_zone_aliases_empty_clears(
        self, hass: HomeAssistant, mock_frigate_data: dict
    ) -> None:
        """Submitting all empty zone aliases removes zone_aliases key."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            options={
                "base_url": "http://ha.local:8123",
                "zone_aliases": {"driveway": {"driveway_approach": "Old Alias"}},
            },
            title="Notifications for Frigate",
        )
        entry.add_to_hass(hass)

        flow_id, result = await _enter_menu_section(hass, entry, "zone_aliases")
        result = await hass.config_entries.options.async_configure(
            flow_id,
            {"Driveway": {"driveway_approach": "", "front_yard": ""}, "Backyard": {"patio": ""}},
        )
        assert result["type"] is FlowResultType.MENU

        result = await _save_from_menu(hass, flow_id)
        assert "zone_aliases" not in result["data"]


class TestOptionsFlowLinear:
    """Tests for the linear first-time setup mode."""

    @pytest.fixture
    def empty_options_entry(self, hass: HomeAssistant, mock_frigate_data: dict) -> MockConfigEntry:
        """Create an entry with empty options (triggers linear mode)."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            options={},
            title="Notifications for Frigate",
        )
        entry.add_to_hass(hass)
        return entry

    async def test_first_time_linear_flow(
        self, hass: HomeAssistant, empty_options_entry: MockConfigEntry
    ) -> None:
        """First-time options flow goes delivery -> appearance -> zone_aliases -> save."""
        result = await hass.config_entries.options.async_init(empty_options_entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "delivery"

        # Delivery.
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"base_url": "http://ha.local:8123"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "appearance"

        # Appearance.
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"title_template": "{{ camera_name }}"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "zone_aliases"

        # Zone aliases — submit empty to skip.
        result = await hass.config_entries.options.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["base_url"] == "http://ha.local:8123"
        assert result["data"]["title_template"] == "{{ camera_name }}"

    async def test_first_time_zone_aliases_saves(
        self, hass: HomeAssistant, empty_options_entry: MockConfigEntry
    ) -> None:
        """First-time flow saves zone aliases at the end."""
        result = await hass.config_entries.options.async_init(empty_options_entry.entry_id)

        # Delivery.
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"base_url": "http://ha.local:8123"}
        )
        # Appearance.
        result = await hass.config_entries.options.async_configure(result["flow_id"], {})
        assert result["step_id"] == "zone_aliases"

        # Set a zone alias.
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"Driveway": {"driveway_approach": "Front Walk"}},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["zone_aliases"]["driveway"]["driveway_approach"] == "Front Walk"
