"""Tests for integration lifecycle (__init__.py)."""

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.frigate_notifications import async_remove_config_entry_device
from custom_components.frigate_notifications.const import (
    DOMAIN,
    FRIGATE_DOMAIN,
    SILENCE_DATETIMES_KEY,
    SUBENTRY_TYPE_INTEGRATION,
)
from custom_components.frigate_notifications.data import get_profile_device_identifiers

from .conftest import FRIGATE_ENTRY_ID, get_profile_subentry_id, setup_integration

pytestmark = pytest.mark.usefixtures("mqtt_mock_no_linger")


class TestAsyncSetupEntry:
    """Tests for async_setup_entry."""

    async def test_setup_entry_success(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Integration sets up successfully."""
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    async def test_setup_entry_frigate_not_ready(
        self, hass: HomeAssistant, mock_frigate_data: dict[str, Any]
    ) -> None:
        """ConfigEntryNotReady when Frigate is not available."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test",
            data={"frigate_entry_id": "nonexistent_frigate"},
            options={},
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_RETRY

    async def test_mqtt_topic_set(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """MQTT topic is derived from Frigate config."""
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.runtime_data.mqtt_topic == "frigate/reviews"

    async def test_integration_subentry_auto_created(
        self, hass: HomeAssistant, mock_frigate_data: dict[str, Any]
    ) -> None:
        """Integration subentry is auto-created when missing."""
        from homeassistant.config_entries import ConfigSubentryData

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test",
            data={"frigate_entry_id": "frigate_entry_01"},
            options={},
            subentries_data=[
                ConfigSubentryData(
                    data={"name": "P", "cameras": ["driveway"], "provider": "apple"},
                    subentry_type="profile",
                    title="P",
                    unique_id="p_uid",
                ),
            ],
        )
        await setup_integration(hass, entry)
        # After reload triggered by subentry creation, it should exist.
        await hass.async_block_till_done()

        integration_subentries = [
            s for s in entry.subentries.values() if s.subentry_type == SUBENTRY_TYPE_INTEGRATION
        ]
        assert len(integration_subentries) == 1

    async def test_profile_entities_use_dedicated_device_linked_via_frigate_camera(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        device_registry,
        entity_registry,
    ) -> None:
        """Profile entities use a dedicated SERVICE device linked to the Frigate camera."""
        frigate_entry = MockConfigEntry(
            domain=FRIGATE_DOMAIN,
            entry_id=FRIGATE_ENTRY_ID,
            title="Frigate",
        )
        frigate_entry.add_to_hass(hass)
        frigate_device = device_registry.async_get_or_create(
            config_entry_id=FRIGATE_ENTRY_ID,
            identifiers={(FRIGATE_DOMAIN, f"{FRIGATE_ENTRY_ID}:driveway")},
            name="Driveway",
        )

        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        entity_id = entity_registry.async_get_entity_id(
            "switch",
            DOMAIN,
            f"{mock_config_entry.entry_id}_{sub_id}_enabled",
        )
        assert entity_id is not None
        registry_entry = entity_registry.async_get(entity_id)
        assert registry_entry is not None
        assert registry_entry.config_subentry_id == sub_id

        # Profile entity should NOT be on the Frigate camera device directly.
        assert registry_entry.device_id != frigate_device.id

        # It should be on a dedicated profile device.
        assert registry_entry.device_id is not None
        profile_device = device_registry.async_get(registry_entry.device_id)
        assert profile_device is not None
        assert profile_device.entry_type == dr.DeviceEntryType.SERVICE
        assert profile_device.model == "Apple Mobile Profile"
        assert profile_device.manufacturer == "Notifications for Frigate"
        assert profile_device.name is not None
        assert profile_device.name == "Test Profile"

        # The profile device should link to the Frigate camera via via_device.
        assert profile_device.via_device_id == frigate_device.id

    async def test_multi_camera_profile_device_links_to_frigate_server(
        self,
        hass: HomeAssistant,
        mock_frigate_data: dict[str, Any],
        device_registry,
        entity_registry,
    ) -> None:
        """Multi-camera profile device links to Frigate server device, not a camera."""
        from homeassistant.config_entries import ConfigSubentryData

        frigate_entry = MockConfigEntry(
            domain=FRIGATE_DOMAIN,
            entry_id=FRIGATE_ENTRY_ID,
            title="Frigate",
        )
        frigate_entry.add_to_hass(hass)
        frigate_server = device_registry.async_get_or_create(
            config_entry_id=FRIGATE_ENTRY_ID,
            identifiers={(FRIGATE_DOMAIN, FRIGATE_ENTRY_ID)},
            name="Frigate Server",
        )

        multi_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Notifications for Frigate",
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            options={},
            subentries_data=[
                ConfigSubentryData(
                    data={
                        "name": "Multi Cam",
                        "cameras": ["backyard", "driveway"],
                        "provider": "apple",
                        "notify_service": "notify.mobile_app_test_phone",
                    },
                    subentry_type="profile",
                    title="Multi Cam",
                    unique_id="multi_cam_uid",
                ),
                ConfigSubentryData(
                    data={},
                    subentry_type="integration",
                    title="Integration",
                    unique_id="integration_uid",
                ),
            ],
        )
        await setup_integration(hass, multi_entry)
        sub_id = get_profile_subentry_id(multi_entry)

        entity_id = entity_registry.async_get_entity_id(
            "switch", DOMAIN, f"{multi_entry.entry_id}_{sub_id}_enabled"
        )
        assert entity_id is not None
        registry_entry = entity_registry.async_get(entity_id)
        assert registry_entry is not None
        assert registry_entry.device_id is not None

        profile_device = device_registry.async_get(registry_entry.device_id)
        assert profile_device is not None
        assert profile_device.name == "Multi Cam"
        assert profile_device.via_device_id == frigate_server.id

    async def test_integration_entities_are_registered_under_integration_subentry(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        device_registry,
        entity_registry,
    ) -> None:
        """Integration-level entities and device belong to the integration subentry."""
        await setup_integration(hass, mock_config_entry)
        integration_subentry_id = next(
            subentry.subentry_id
            for subentry in mock_config_entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_INTEGRATION
        )

        entity_id = entity_registry.async_get_entity_id(
            "binary_sensor",
            DOMAIN,
            f"{mock_config_entry.entry_id}_mqtt_connected",
        )
        assert entity_id is not None
        registry_entry = entity_registry.async_get(entity_id)
        assert registry_entry is not None
        assert registry_entry.config_subentry_id == integration_subentry_id

        integration_device = device_registry.async_get_device(
            identifiers={(DOMAIN, mock_config_entry.entry_id)}
        )
        assert integration_device is not None
        assert integration_device.config_entries_subentries[mock_config_entry.entry_id] == {
            integration_subentry_id
        }


class TestAsyncUnloadEntry:
    """Tests for async_unload_entry."""

    async def test_unload_success(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Integration unloads successfully."""
        await setup_integration(hass, mock_config_entry)

        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
        assert result is True

    async def test_unload_cleans_hass_data(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Unload removes silence map from hass.data."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        # Verify silence map has entry.
        silence_map = hass.data.get(SILENCE_DATETIMES_KEY, {})
        assert sub_id in silence_map

        await hass.config_entries.async_unload(mock_config_entry.entry_id)

        silence_map = hass.data.get(SILENCE_DATETIMES_KEY, {})
        assert sub_id not in silence_map


class TestMqttCallback:
    """Tests for the MQTT message callback wiring."""

    async def test_mqtt_message_reaches_processor(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """MQTT message fires through callback to processor."""
        import json

        from pytest_homeassistant_custom_component.common import async_fire_mqtt_message

        from .payloads import REVIEW_NEW_PAYLOAD

        await setup_integration(hass, mock_config_entry)

        async_fire_mqtt_message(hass, "frigate/reviews", json.dumps(REVIEW_NEW_PAYLOAD))
        await hass.async_block_till_done()

        processor = mock_config_entry.runtime_data.processor
        review = processor.get_review(REVIEW_NEW_PAYLOAD["after"]["id"])
        assert review is not None
        assert review.camera == "driveway"


class TestNoProfiles:
    """Tests for entries with no profiles."""

    async def test_setup_with_no_profiles(
        self, hass: HomeAssistant, mock_config_entry_no_profiles: MockConfigEntry
    ) -> None:
        """Integration loads successfully with no profiles."""
        await setup_integration(hass, mock_config_entry_no_profiles)
        assert mock_config_entry_no_profiles.state is ConfigEntryState.LOADED


class TestAsyncRemoveConfigEntryDevice:
    """Tests for config-entry device removal hook."""

    async def test_profile_device_removal_removes_subentry(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry, device_registry
    ) -> None:
        """Profile-owned devices remove their matching subentry."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        profile_device = device_registry.async_get_device(
            identifiers=get_profile_device_identifiers(mock_config_entry.entry_id, sub_id)
        )
        assert profile_device is not None

        result = await async_remove_config_entry_device(hass, mock_config_entry, profile_device)
        assert result is True
        assert sub_id not in mock_config_entry.subentries

    async def test_integration_device_removal_is_rejected(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry, device_registry
    ) -> None:
        """Unmatched devices are not approved for removal."""
        await setup_integration(hass, mock_config_entry)

        integration_device = device_registry.async_get_device(
            identifiers={(DOMAIN, mock_config_entry.entry_id)}
        )
        assert integration_device is not None

        result = await async_remove_config_entry_device(hass, mock_config_entry, integration_device)
        assert result is False


class TestAsyncRemoveEntry:
    """Tests for async_remove_entry (full entry removal)."""

    async def test_remove_entry_deletes_repair_issues(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry, issue_registry
    ) -> None:
        """Removing the entry deletes all repair issues."""
        from homeassistant.helpers import issue_registry as ir

        await setup_integration(hass, mock_config_entry)

        # Create an issue so we can verify it gets cleaned up.
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"broken_camera_{mock_config_entry.entry_id}_test",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="broken_camera_binding",
        )
        pre_issues = [iid for iid in issue_registry.issues if iid[0] == DOMAIN]
        assert len(pre_issues) > 0

        await hass.config_entries.async_remove(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        post_issues = [iid for iid in issue_registry.issues if iid[0] == DOMAIN]
        assert len(post_issues) == 0


class TestAsyncUpdateListener:
    """Tests for _async_update_listener (options change triggers reload)."""

    async def test_options_change_triggers_reload(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Changing options triggers a config entry reload."""
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

        hass.config_entries.async_update_entry(
            mock_config_entry,
            options={**mock_config_entry.options, "cooldown_seconds": 99},
        )
        await hass.async_block_till_done()

        # After reload, entry should still be loaded.
        assert mock_config_entry.state is ConfigEntryState.LOADED


class TestFrigateDeviceRegistryListener:
    """Tests for the Frigate device-registry change listener."""

    async def test_frigate_device_removal_triggers_repair_sync(
        self,
        hass: HomeAssistant,
        mock_frigate_data: dict[str, Any],
        device_registry: dr.DeviceRegistry,
    ) -> None:
        """Removing a Frigate camera device creates broken-camera repair after debounce."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test",
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            subentries_data=[
                ConfigSubentryData(
                    data={
                        "name": "Driveway",
                        "cameras": ["driveway"],
                        "provider": "apple",
                        "notify_service": "notify.mobile_app_test_phone",
                    },
                    subentry_type="profile",
                    title="Driveway",
                    unique_id="drv_uid",
                ),
                ConfigSubentryData(
                    data={}, subentry_type="integration", title="Integration", unique_id="int_uid"
                ),
            ],
        )
        await setup_integration(hass, entry)

        # No broken camera issues initially.
        issue_reg = ir.async_get(hass)
        assert not [
            iid for iid in issue_reg.issues if iid[0] == DOMAIN and "broken_camera" in iid[1]
        ]

        # Remove driveway from Frigate config.
        del mock_frigate_data[FRIGATE_ENTRY_ID]["config"]["cameras"]["driveway"]

        # Fire a Frigate device removal event directly on the bus.
        hass.bus.async_fire(
            "device_registry_updated",
            {
                "action": "remove",
                "device_id": "fake_id",
                "device": {
                    "identifiers": [(FRIGATE_DOMAIN, f"{FRIGATE_ENTRY_ID}:driveway")],
                },
            },
        )
        await hass.async_block_till_done()

        # Advance time past debounce cooldown, then let the task execute.
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
        await hass.async_block_till_done()

        broken = [iid for iid in issue_reg.issues if iid[0] == DOMAIN and "broken_camera" in iid[1]]
        assert len(broken) == 1

    async def test_frigate_device_creation_resolves_repair(
        self,
        hass: HomeAssistant,
        mock_frigate_data: dict[str, Any],
        device_registry: dr.DeviceRegistry,
    ) -> None:
        """Creating a Frigate camera device resolves a broken-camera repair."""
        # Profile references a missing camera — issue created at setup.
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test",
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            subentries_data=[
                ConfigSubentryData(
                    data={
                        "name": "Porch",
                        "cameras": ["porch_cam"],
                        "provider": "apple",
                        "notify_service": "notify.mobile_app_test_phone",
                    },
                    subentry_type="profile",
                    title="Porch",
                    unique_id="porch_uid",
                ),
                ConfigSubentryData(
                    data={}, subentry_type="integration", title="Integration", unique_id="int_uid"
                ),
            ],
        )
        await setup_integration(hass, entry)

        issue_reg = ir.async_get(hass)
        assert [iid for iid in issue_reg.issues if iid[0] == DOMAIN and "broken_camera" in iid[1]]

        # Camera appears in Frigate config.
        mock_frigate_data[FRIGATE_ENTRY_ID]["config"]["cameras"]["porch_cam"] = {
            "zones": {},
            "objects": {"track": ["person"]},
            "review": {"genai": {"enabled": False}},
        }

        # Fire a Frigate device creation event.
        hass.bus.async_fire(
            "device_registry_updated",
            {"action": "create", "device_id": "fake_porch_id"},
        )
        await hass.async_block_till_done()

        # For "create" events, our handler looks up the device from the registry.
        # Register a Frigate device so the lookup succeeds.
        device_registry.async_get_or_create(
            config_entry_id=FRIGATE_ENTRY_ID,
            identifiers={(FRIGATE_DOMAIN, f"{FRIGATE_ENTRY_ID}:porch_cam")},
            name="Porch Cam",
        )

        # The create from async_get_or_create also fires an event — wait + advance.
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
        await hass.async_block_till_done()

        broken = [iid for iid in issue_reg.issues if iid[0] == DOMAIN and "broken_camera" in iid[1]]
        assert not broken

    async def test_unrelated_device_event_ignored(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Device events for non-Frigate devices do not trigger repair sync."""
        await setup_integration(hass, mock_config_entry)

        issue_reg = ir.async_get(hass)
        issues_before = len(list(issue_reg.issues))

        # Fire a create event for a non-Frigate device (filtered by event_filter).
        hass.bus.async_fire(
            "device_registry_updated",
            {"action": "create", "device_id": "unrelated_device"},
        )
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
        await hass.async_block_till_done()

        assert len(list(issue_reg.issues)) == issues_before

    async def test_no_false_repairs_when_frigate_unavailable(
        self,
        hass: HomeAssistant,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Events while Frigate config is unavailable do not create false repairs."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test",
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            subentries_data=[
                ConfigSubentryData(
                    data={
                        "name": "Driveway",
                        "cameras": ["driveway"],
                        "provider": "apple",
                        "notify_service": "notify.mobile_app_test_phone",
                    },
                    subentry_type="profile",
                    title="Driveway",
                    unique_id="drv_uid",
                ),
                ConfigSubentryData(
                    data={}, subentry_type="integration", title="Integration", unique_id="int_uid"
                ),
            ],
        )
        await setup_integration(hass, entry)

        # Simulate Frigate being temporarily unavailable.
        saved = mock_frigate_data.pop(FRIGATE_ENTRY_ID)

        hass.bus.async_fire(
            "device_registry_updated",
            {
                "action": "remove",
                "device_id": "fake_id",
                "device": {
                    "identifiers": [(FRIGATE_DOMAIN, f"{FRIGATE_ENTRY_ID}:driveway")],
                },
            },
        )
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
        await hass.async_block_till_done()

        issue_reg = ir.async_get(hass)
        broken = [iid for iid in issue_reg.issues if iid[0] == DOMAIN and "broken_camera" in iid[1]]
        assert not broken

        mock_frigate_data[FRIGATE_ENTRY_ID] = saved
