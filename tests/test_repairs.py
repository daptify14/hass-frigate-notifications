"""Tests for repair issue management."""

from typing import Any

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.frigate_notifications.const import DOMAIN
from custom_components.frigate_notifications.repairs import (
    sync_broken_camera_issues,
    sync_stale_zone_issues,
)

from .conftest import FRIGATE_ENTRY_ID


@pytest.fixture
def mock_entry_with_missing_camera(
    hass: HomeAssistant,
    mock_frigate_data: dict[str, Any],
) -> MockConfigEntry:
    """Config entry with a profile referencing a nonexistent camera."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        data={"frigate_entry_id": FRIGATE_ENTRY_ID},
        subentries_data=[
            ConfigSubentryData(
                data={"name": "Ghost Camera", "cameras": ["ghost_cam"]},
                subentry_type="profile",
                title="Ghost Camera Profile",
                unique_id="ghost_uid",
            ),
        ],
    )


@pytest.fixture
def mock_entry_with_stale_zone(
    hass: HomeAssistant,
    mock_frigate_data: dict[str, Any],
) -> MockConfigEntry:
    """Config entry with a profile referencing nonexistent zones."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        data={"frigate_entry_id": FRIGATE_ENTRY_ID},
        subentries_data=[
            ConfigSubentryData(
                data={
                    "name": "Stale Zone Profile",
                    "cameras": ["driveway"],
                    "required_zones": ["nonexistent_zone"],
                },
                subentry_type="profile",
                title="Stale Zone Profile",
                unique_id="stale_zone_uid",
            ),
        ],
    )


class TestBrokenCameraIssues:
    """Tests for broken camera repair issues."""

    def test_creates_issue_for_missing_camera(
        self,
        hass: HomeAssistant,
        mock_entry_with_missing_camera: MockConfigEntry,
    ) -> None:
        """Creates a repair issue when a profile references a missing camera."""
        entry = mock_entry_with_missing_camera
        entry.add_to_hass(hass)

        sync_broken_camera_issues(hass, entry)

        issue_reg = ir.async_get(hass)
        issues = {iid[1]: issue for iid, issue in issue_reg.issues.items() if iid[0] == DOMAIN}
        assert any("broken_camera" in iid for iid in issues)

    def test_creates_issue_for_secondary_missing_camera(
        self,
        hass: HomeAssistant,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Creates a repair issue when a secondary camera in a multi-camera profile is missing."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test",
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            subentries_data=[
                ConfigSubentryData(
                    data={"name": "Multi Cam", "cameras": ["driveway", "ghost_cam"]},
                    subentry_type="profile",
                    title="Multi Cam Profile",
                    unique_id="multi_uid",
                ),
            ],
        )
        entry.add_to_hass(hass)
        sync_broken_camera_issues(hass, entry)

        issue_reg = ir.async_get(hass)
        issues = {iid[1]: issue for iid, issue in issue_reg.issues.items() if iid[0] == DOMAIN}
        assert any("ghost_cam" in iid for iid in issues)

    def test_no_issue_for_valid_cameras(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """No repair issue created when all cameras are valid."""
        mock_config_entry.add_to_hass(hass)
        sync_broken_camera_issues(hass, mock_config_entry)

        issue_reg = ir.async_get(hass)
        broken = [iid for iid in issue_reg.issues if iid[0] == DOMAIN and "broken_camera" in iid[1]]
        assert not broken


class TestStaleZoneIssues:
    """Tests for stale zone repair issues."""

    def test_creates_issue_for_stale_zone(
        self,
        hass: HomeAssistant,
        mock_entry_with_stale_zone: MockConfigEntry,
    ) -> None:
        """Creates a repair issue when zones reference nonexistent Frigate zones."""
        entry = mock_entry_with_stale_zone
        entry.add_to_hass(hass)

        sync_stale_zone_issues(hass, entry)

        issue_reg = ir.async_get(hass)
        issues = {iid[1]: issue for iid, issue in issue_reg.issues.items() if iid[0] == DOMAIN}
        assert any("stale_zone" in iid for iid in issues)

    def test_no_issue_when_zones_valid(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """No repair issue when no stale zones exist."""
        mock_config_entry.add_to_hass(hass)
        sync_stale_zone_issues(hass, mock_config_entry)

        issue_reg = ir.async_get(hass)
        stale = [iid for iid in issue_reg.issues if iid[0] == DOMAIN and "stale_zone" in iid[1]]
        assert not stale
