"""Tests for repair issue management."""

from typing import Any

from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.frigate_notifications.const import DOMAIN
from custom_components.frigate_notifications.repairs import (
    delete_all_issues_for_entry,
    sync_repair_issues,
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


class TestRootCauseFrigateEntry:
    """Tests for root-cause Frigate entry check and suppression."""

    def test_missing_entry_creates_root_cause_and_suppresses_downstream(
        self,
        hass: HomeAssistant,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Missing/failed Frigate entry creates one ERROR issue; transient state is a no-op."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test",
            data={"frigate_entry_id": "nonexistent_frigate"},
            subentries_data=[
                ConfigSubentryData(
                    data={"name": "Ghost", "cameras": ["ghost_cam"]},
                    subentry_type="profile",
                    title="Ghost",
                    unique_id="ghost_uid",
                ),
            ],
        )
        entry.add_to_hass(hass)

        # Missing entry → root-cause issue only, no broken_cameras.
        sync_repair_issues(hass, entry)
        issue_reg = ir.async_get(hass)
        domain_issues = {iid[1]: iss for iid, iss in issue_reg.issues.items() if iid[0] == DOMAIN}
        assert len(domain_issues) == 1
        root_id = f"fn_{entry.entry_id}_linked_frigate_unavailable"
        assert root_id in domain_issues
        assert domain_issues[root_id].severity == ir.IssueSeverity.ERROR

        # Simulate Frigate entry appearing but still retrying (transient).
        frigate_entry = MockConfigEntry(
            domain="frigate",
            title="Frigate",
            entry_id="nonexistent_frigate",
        )
        frigate_entry.add_to_hass(hass)
        # MockConfigEntry defaults to NOT_LOADED — transient, should no-op.
        sync_repair_issues(hass, entry)
        # Root-cause issue from previous sync should still be there (no-op doesn't clear).
        assert root_id in {iid[1] for iid in issue_reg.issues if iid[0] == DOMAIN}

        # Frigate loads successfully — inject config data and mark LOADED.
        frigate_entry.mock_state(hass, ConfigEntryState.LOADED)
        mock_frigate_data["nonexistent_frigate"] = mock_frigate_data[FRIGATE_ENTRY_ID]
        sync_repair_issues(hass, entry)
        remaining = {iid[1] for iid in issue_reg.issues if iid[0] == DOMAIN}
        assert root_id not in remaining
        # broken_cameras should now appear since ghost_cam doesn't exist in Frigate.
        assert any("broken_cameras" in iid for iid in remaining)


class TestBrokenCameraIssues:
    """Tests for broken camera repair issues via sync_repair_issues."""

    def test_creates_consolidated_issue_for_missing_cameras(
        self,
        hass: HomeAssistant,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """One issue per profile lists all broken cameras; multi-camera consolidation works."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test",
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            subentries_data=[
                ConfigSubentryData(
                    data={"name": "Multi Cam", "cameras": ["driveway", "ghost_cam", "phantom"]},
                    subentry_type="profile",
                    title="Multi Cam Profile",
                    unique_id="multi_uid",
                ),
            ],
        )
        entry.add_to_hass(hass)
        sub_id = next(
            s.subentry_id for s in entry.subentries.values() if s.subentry_type == "profile"
        )

        sync_repair_issues(hass, entry)

        issue_reg = ir.async_get(hass)
        issues = [issue for iid, issue in issue_reg.issues.items() if iid[0] == DOMAIN]
        assert len(issues) == 1

        expected_id = f"fn_{entry.entry_id}_{sub_id}_broken_cameras"
        assert (DOMAIN, expected_id) in issue_reg.issues

        placeholders = issues[0].translation_placeholders
        assert placeholders is not None
        assert placeholders["profile_name"] == "Multi Cam"
        assert "ghost_cam" in placeholders["cameras"]
        assert "phantom" in placeholders["cameras"]
        assert issues[0].severity == ir.IssueSeverity.WARNING

    def test_no_issue_for_valid_cameras(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """No repair issue created when all cameras are valid or Frigate unavailable."""
        mock_config_entry.add_to_hass(hass)
        sync_repair_issues(hass, mock_config_entry)

        issue_reg = ir.async_get(hass)
        assert not [iid for iid in issue_reg.issues if iid[0] == DOMAIN]

        # Also safe when Frigate config is unavailable — guard returns early.
        del mock_frigate_data[FRIGATE_ENTRY_ID]
        sync_repair_issues(hass, mock_config_entry)
        assert not [iid for iid in issue_reg.issues if iid[0] == DOMAIN]

    def test_resolves_issue_when_camera_returns(
        self,
        hass: HomeAssistant,
        mock_entry_with_missing_camera: MockConfigEntry,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Issue auto-resolves when the missing camera reappears; foreign-domain issues survive."""
        entry = mock_entry_with_missing_camera
        entry.add_to_hass(hass)

        sync_repair_issues(hass, entry)
        issue_reg = ir.async_get(hass)
        assert any(iid[0] == DOMAIN for iid in issue_reg.issues)

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
        sync_repair_issues(hass, entry)

        domain_issues = [iid for iid in issue_reg.issues if iid[0] == DOMAIN]
        assert not domain_issues
        assert ("other", "unrelated") in issue_reg.issues


class TestStaleZoneIssues:
    """Tests for stale zone repair issues via sync_repair_issues."""

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

        sync_repair_issues(hass, entry)

        issue_reg = ir.async_get(hass)
        issues = [issue for iid, issue in issue_reg.issues.items() if iid[0] == DOMAIN]
        assert len(issues) == 1

        expected_id = f"fn_{entry.entry_id}_{sub_id}_stale_zones"
        assert (DOMAIN, expected_id) in issue_reg.issues

        placeholders = issues[0].translation_placeholders
        assert placeholders is not None
        assert placeholders["profile_name"] == "Stale Zone Profile"
        assert "nonexistent_zone" in placeholders["zones"]
        assert issues[0].severity == ir.IssueSeverity.WARNING

    def test_no_issue_when_zones_valid(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """No repair issue when no stale zones exist or Frigate unavailable."""
        mock_config_entry.add_to_hass(hass)
        sync_repair_issues(hass, mock_config_entry)

        issue_reg = ir.async_get(hass)
        assert not [iid for iid in issue_reg.issues if iid[0] == DOMAIN]

        del mock_frigate_data[FRIGATE_ENTRY_ID]
        sync_repair_issues(hass, mock_config_entry)
        assert not [iid for iid in issue_reg.issues if iid[0] == DOMAIN]

    def test_resolves_issue_when_zone_returns(
        self,
        hass: HomeAssistant,
        mock_entry_with_stale_zone: MockConfigEntry,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Issue auto-resolves when the missing zone reappears; foreign-domain issues survive."""
        entry = mock_entry_with_stale_zone
        entry.add_to_hass(hass)

        sync_repair_issues(hass, entry)
        issue_reg = ir.async_get(hass)
        assert any(iid[0] == DOMAIN for iid in issue_reg.issues)

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
        sync_repair_issues(hass, entry)

        domain_issues = [iid for iid in issue_reg.issues if iid[0] == DOMAIN]
        assert not domain_issues
        assert ("other", "unrelated") in issue_reg.issues


class TestDeleteAllIssues:
    """Tests for prefix-based cleanup of all entry issues."""

    def test_deletes_all_entry_issues_by_prefix(
        self,
        hass: HomeAssistant,
        mock_entry_with_missing_camera: MockConfigEntry,
        mock_entry_with_stale_zone: MockConfigEntry,
    ) -> None:
        """Prefix-based sweep removes all fn_{entry_id}_ issues for the entry."""
        entry = mock_entry_with_missing_camera
        entry.add_to_hass(hass)
        sync_repair_issues(hass, entry)

        stale_entry = mock_entry_with_stale_zone
        stale_entry.add_to_hass(hass)
        sync_repair_issues(hass, stale_entry)

        # Foreign-domain issue should survive.
        ir.async_create_issue(
            hass,
            "other",
            "unrelated",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="x",
        )

        issue_reg = ir.async_get(hass)
        assert len([iid for iid in issue_reg.issues if iid[0] == DOMAIN]) == 2

        delete_all_issues_for_entry(hass, entry)

        remaining = [iid for iid in issue_reg.issues if iid[0] == DOMAIN]
        assert len(remaining) == 1
        assert all(entry.entry_id not in iid[1] for iid in remaining)
        assert ("other", "unrelated") in issue_reg.issues
