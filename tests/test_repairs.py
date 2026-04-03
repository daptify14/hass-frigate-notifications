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
        """Creates a per-profile repair issue with placeholders for a missing camera."""
        entry = mock_entry_with_missing_camera
        entry.add_to_hass(hass)
        sub_id = next(
            s.subentry_id for s in entry.subentries.values() if s.subentry_type == "profile"
        )

        sync_broken_camera_issues(hass, entry)

        issue_reg = ir.async_get(hass)
        issues = [issue for iid, issue in issue_reg.issues.items() if iid[0] == DOMAIN]
        assert len(issues) == 1

        issue_ids = [iid[1] for iid in issue_reg.issues if iid[0] == DOMAIN]
        assert any(sub_id in iid and "broken_camera" in iid for iid in issue_ids)

        placeholders = issues[0].translation_placeholders
        assert placeholders is not None
        assert placeholders["profile_name"] == "Ghost Camera"
        assert placeholders["camera"] == "ghost_cam"

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
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """No repair issue created when all cameras are valid or Frigate unavailable."""
        mock_config_entry.add_to_hass(hass)
        sync_broken_camera_issues(hass, mock_config_entry)

        issue_reg = ir.async_get(hass)
        broken = [iid for iid in issue_reg.issues if iid[0] == DOMAIN and "broken_camera" in iid[1]]
        assert not broken

        # Also safe when Frigate config is unavailable — guard returns early.
        del mock_frigate_data[FRIGATE_ENTRY_ID]
        sync_broken_camera_issues(hass, mock_config_entry)
        assert not [
            iid for iid in issue_reg.issues if iid[0] == DOMAIN and "broken_camera" in iid[1]
        ]

    def test_resolves_issue_when_camera_returns(
        self,
        hass: HomeAssistant,
        mock_entry_with_missing_camera: MockConfigEntry,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Issue auto-resolves when the missing camera reappears in Frigate."""
        entry = mock_entry_with_missing_camera
        entry.add_to_hass(hass)

        sync_broken_camera_issues(hass, entry)
        issue_reg = ir.async_get(hass)
        assert any(iid[0] == DOMAIN and "broken_camera" in iid[1] for iid in issue_reg.issues)

        # Foreign-domain issue should survive the sweep.
        ir.async_create_issue(
            hass,
            "other",
            "unrelated",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="x",
        )

        mock_frigate_data[FRIGATE_ENTRY_ID]["config"]["cameras"]["ghost_cam"] = {
            "zones": {},
            "objects": {"track": ["person"]},
            "review": {"genai": {"enabled": False}},
        }
        sync_broken_camera_issues(hass, entry)

        broken = [iid for iid in issue_reg.issues if iid[0] == DOMAIN and "broken_camera" in iid[1]]
        assert not broken
        assert ("other", "unrelated") in issue_reg.issues


class TestStaleZoneIssues:
    """Tests for stale zone repair issues."""

    def test_creates_issue_for_stale_zone(
        self,
        hass: HomeAssistant,
        mock_entry_with_stale_zone: MockConfigEntry,
    ) -> None:
        """Creates a per-profile repair issue with placeholders for stale zones."""
        entry = mock_entry_with_stale_zone
        entry.add_to_hass(hass)
        sub_id = next(
            s.subentry_id for s in entry.subentries.values() if s.subentry_type == "profile"
        )

        sync_stale_zone_issues(hass, entry)

        issue_reg = ir.async_get(hass)
        issues = [issue for iid, issue in issue_reg.issues.items() if iid[0] == DOMAIN]
        assert len(issues) == 1

        issue_ids = [iid[1] for iid in issue_reg.issues if iid[0] == DOMAIN]
        assert any(sub_id in iid and "stale_zone" in iid for iid in issue_ids)

        placeholders = issues[0].translation_placeholders
        assert placeholders is not None
        assert placeholders["profile_name"] == "Stale Zone Profile"
        assert "nonexistent_zone" in placeholders["zones"]

    def test_no_issue_when_zones_valid(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """No repair issue when no stale zones exist or Frigate unavailable."""
        mock_config_entry.add_to_hass(hass)
        sync_stale_zone_issues(hass, mock_config_entry)

        issue_reg = ir.async_get(hass)
        stale = [iid for iid in issue_reg.issues if iid[0] == DOMAIN and "stale_zone" in iid[1]]
        assert not stale

        # Also safe when Frigate config is unavailable — guard returns early.
        del mock_frigate_data[FRIGATE_ENTRY_ID]
        sync_stale_zone_issues(hass, mock_config_entry)
        assert not [iid for iid in issue_reg.issues if iid[0] == DOMAIN and "stale_zone" in iid[1]]

    def test_resolves_issue_when_zone_returns(
        self,
        hass: HomeAssistant,
        mock_entry_with_stale_zone: MockConfigEntry,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Issue auto-resolves when the missing zone reappears in Frigate."""
        entry = mock_entry_with_stale_zone
        entry.add_to_hass(hass)

        sync_stale_zone_issues(hass, entry)
        issue_reg = ir.async_get(hass)
        assert any(iid[0] == DOMAIN and "stale_zone" in iid[1] for iid in issue_reg.issues)

        # Foreign-domain issue should survive the sweep.
        ir.async_create_issue(
            hass,
            "other",
            "unrelated",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="x",
        )

        mock_frigate_data[FRIGATE_ENTRY_ID]["config"]["cameras"]["driveway"]["zones"][
            "nonexistent_zone"
        ] = {}
        sync_stale_zone_issues(hass, entry)

        stale = [iid for iid in issue_reg.issues if iid[0] == DOMAIN and "stale_zone" in iid[1]]
        assert not stale
        assert ("other", "unrelated") in issue_reg.issues
