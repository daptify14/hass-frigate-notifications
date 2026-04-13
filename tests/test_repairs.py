"""Tests for repair issue management."""

from typing import Any

from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.frigate_notifications.const import DOMAIN
from custom_components.frigate_notifications.repairs import sync_repair_issues

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


def _make_profile_entry(
    profile_data: dict[str, Any],
    *,
    options: dict[str, Any] | None = None,
    name: str = "Test Profile",
    unique_id: str = "test_uid",
) -> MockConfigEntry:
    """Create an entry with one profile subentry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        data={"frigate_entry_id": FRIGATE_ENTRY_ID},
        options=options or {},
        subentries_data=[
            ConfigSubentryData(
                data={"name": name, "cameras": ["driveway"], **profile_data},
                subentry_type="profile",
                title=name,
                unique_id=unique_id,
            ),
        ],
    )


def _profile_subentry_id(entry: MockConfigEntry) -> str:
    return next(s.subentry_id for s in entry.subentries.values() if s.subentry_type == "profile")


def _domain_issues(hass: HomeAssistant) -> dict[str, ir.IssueEntry]:
    issue_reg = ir.async_get(hass)
    return {iid[1]: issue for iid, issue in issue_reg.issues.items() if iid[0] == DOMAIN}


def _sync_domain_issues(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, ir.IssueEntry]:
    sync_repair_issues(hass, entry)
    return _domain_issues(hass)


def _add_entry_and_sync(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, ir.IssueEntry]:
    entry.add_to_hass(hass)
    return _sync_domain_issues(hass, entry)


def _create_foreign_issue(hass: HomeAssistant) -> None:
    ir.async_create_issue(
        hass,
        "other",
        "unrelated",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="x",
    )


def _assert_stale_reference_issue(
    issue: ir.IssueEntry,
    *,
    profiles: str,
    location: str,
    reference_contains: str | tuple[str, ...] = (),
) -> None:
    assert issue.translation_key == "stale_reference"
    placeholders = issue.translation_placeholders
    assert placeholders is not None
    assert placeholders["profiles"] == profiles
    assert placeholders["location"] == location
    if isinstance(reference_contains, str):
        reference_contains = (reference_contains,)
    for value in reference_contains:
        assert value in placeholders["reference"]


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

        # Missing entry creates a root-cause issue only, no broken_cameras.
        domain_issues = _sync_domain_issues(hass, entry)
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
        # MockConfigEntry defaults to NOT_LOADED, so transient should no-op.
        sync_repair_issues(hass, entry)
        # Root-cause issue from previous sync should still be there (no-op doesn't clear).
        assert root_id in _domain_issues(hass)

        # Terminal failure state creates the same root-cause issue.
        ir.async_delete_issue(hass, DOMAIN, root_id)
        frigate_entry.mock_state(hass, ConfigEntryState.SETUP_ERROR)
        terminal_issues = _sync_domain_issues(hass, entry)
        assert root_id in terminal_issues
        assert terminal_issues[root_id].severity == ir.IssueSeverity.ERROR
        assert not any("broken_cameras" in iid for iid in terminal_issues)

        # Frigate loads successfully, so inject config data and mark LOADED.
        frigate_entry.mock_state(hass, ConfigEntryState.LOADED)
        mock_frigate_data["nonexistent_frigate"] = mock_frigate_data[FRIGATE_ENTRY_ID]
        remaining = _sync_domain_issues(hass, entry)
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
        entry = _make_profile_entry(
            {"cameras": ["driveway", "ghost_cam", "phantom"]},
            name="Multi Cam",
            unique_id="multi_uid",
        )
        entry.add_to_hass(hass)
        sub_id = _profile_subentry_id(entry)

        issues = _sync_domain_issues(hass, entry)
        assert len(issues) == 1

        expected_id = f"fn_{entry.entry_id}_{sub_id}_broken_cameras"
        issue = issues[expected_id]

        placeholders = issue.translation_placeholders
        assert placeholders is not None
        assert placeholders["profile_name"] == "Multi Cam"
        assert "ghost_cam" in placeholders["cameras"]
        assert "phantom" in placeholders["cameras"]
        assert issue.severity == ir.IssueSeverity.WARNING

    def test_valid_entry_and_missing_config_view_produce_no_issues(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """No repair issues are created for valid config or missing cached Frigate config."""
        mock_config_entry.add_to_hass(hass)
        assert not _sync_domain_issues(hass, mock_config_entry)

        del mock_frigate_data[FRIGATE_ENTRY_ID]
        assert not _sync_domain_issues(hass, mock_config_entry)

    def test_resolves_issue_when_camera_returns(
        self,
        hass: HomeAssistant,
        mock_entry_with_missing_camera: MockConfigEntry,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Issue auto-resolves when the missing camera reappears; foreign-domain issues survive."""
        entry = mock_entry_with_missing_camera
        entry.add_to_hass(hass)

        assert _sync_domain_issues(hass, entry)

        _create_foreign_issue(hass)

        mock_frigate_data[FRIGATE_ENTRY_ID]["config"]["cameras"]["ghost_cam"] = {
            "zones": {},
            "objects": {"track": ["person"]},
            "review": {"genai": {"enabled": False}},
        }
        assert not _sync_domain_issues(hass, entry)

        issue_reg = ir.async_get(hass)
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
        sub_id = _profile_subentry_id(entry)

        issues = _sync_domain_issues(hass, entry)
        assert len(issues) == 1

        expected_id = f"fn_{entry.entry_id}_{sub_id}_stale_zones"
        issue = issues[expected_id]

        placeholders = issue.translation_placeholders
        assert placeholders is not None
        assert placeholders["profile_name"] == "Stale Zone Profile"
        assert "nonexistent_zone" in placeholders["zones"]
        assert issue.severity == ir.IssueSeverity.WARNING

    def test_resolves_issue_when_zone_returns(
        self,
        hass: HomeAssistant,
        mock_entry_with_stale_zone: MockConfigEntry,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Issue auto-resolves when the missing zone reappears; foreign-domain issues survive."""
        entry = mock_entry_with_stale_zone
        entry.add_to_hass(hass)

        assert _sync_domain_issues(hass, entry)

        _create_foreign_issue(hass)

        mock_frigate_data[FRIGATE_ENTRY_ID]["config"]["cameras"]["driveway"]["zones"][
            "nonexistent_zone"
        ] = {}
        assert not _sync_domain_issues(hass, entry)

        issue_reg = ir.async_get(hass)
        assert ("other", "unrelated") in issue_reg.issues


class TestNotifyTarget:
    """Tests for stale notify target detection."""

    def test_notify_device_checks(
        self,
        hass: HomeAssistant,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Missing device creates issue; direct service and valid device produce nothing."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test",
            data={"frigate_entry_id": FRIGATE_ENTRY_ID},
            options={},
            subentries_data=[
                ConfigSubentryData(
                    data={
                        "name": "Device Profile",
                        "cameras": ["driveway"],
                        "notify_device": "nonexistent_device_id",
                    },
                    subentry_type="profile",
                    title="Device Profile",
                    unique_id="dev_uid",
                ),
                ConfigSubentryData(
                    data={
                        "name": "Service Profile",
                        "cameras": ["driveway"],
                        "notify_service": "notify.my_phone",
                    },
                    subentry_type="profile",
                    title="Service Profile",
                    unique_id="svc_uid",
                ),
            ],
        )
        entry.add_to_hass(hass)

        domain_issues = _sync_domain_issues(hass, entry)

        # Only the device profile should have a stale_notify_target issue.
        notify_issues = {k: v for k, v in domain_issues.items() if "stale_notify_target" in k}
        assert len(notify_issues) == 1
        issue = next(iter(notify_issues.values()))
        _assert_stale_reference_issue(
            issue,
            profiles="Device Profile",
            location="profile settings",
            reference_contains="nonexistent_device_id",
        )


class TestEntityReferences:
    """Tests for guard, state filter, and presence entity reference checks."""

    def test_custom_guard_missing(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Custom guard issue only appears once the entity is absent from registry and state."""
        registry_entry = entity_registry.async_get_or_create(
            "input_boolean",
            "test",
            "guard_uid",
            suggested_object_id="gone",
        )
        entry = _make_profile_entry(
            {"guard_mode": "custom", "guard_entity": registry_entry.entity_id},
        )
        entry.add_to_hass(hass)
        issues = _sync_domain_issues(hass, entry)
        assert not any("guard" in k for k in issues)

        entity_registry.async_remove(registry_entry.entity_id)
        issues = _sync_domain_issues(hass, entry)
        sub_id = _profile_subentry_id(entry)
        issue_id = f"fn_{entry.entry_id}_{sub_id}_stale_guard_entity"
        assert issue_id in issues
        _assert_stale_reference_issue(
            issues[issue_id],
            profiles="Test Profile",
            location="profile settings",
            reference_contains=registry_entry.entity_id,
        )

    def test_disabled_guard_skipped(
        self,
        hass: HomeAssistant,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Disabled guard mode produces no issue even if entity would be missing."""
        entry = _make_profile_entry({"guard_mode": "disabled"})
        issues = _add_entry_and_sync(hass, entry)
        assert not any("guard" in k for k in issues)

    def test_custom_state_filter_empty_states_skipped(
        self,
        hass: HomeAssistant,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Custom state filter with no allowed states configured produces no issue."""
        entry = _make_profile_entry(
            {
                "state_filter_mode": "custom",
                "state_entity": "input_boolean.gone",
                "state_filter_states": [],
            }
        )
        issues = _add_entry_and_sync(hass, entry)
        assert not any("state_entity" in k for k in issues)

    def test_custom_state_filter_with_states_missing(
        self,
        hass: HomeAssistant,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Custom state filter with allowed states and missing entity produces an issue."""
        entry = _make_profile_entry(
            {
                "state_filter_mode": "custom",
                "state_entity": "input_boolean.gone",
                "state_filter_states": ["on"],
            }
        )
        issues = _add_entry_and_sync(hass, entry)

        sub_id = _profile_subentry_id(entry)
        issue_id = f"fn_{entry.entry_id}_{sub_id}_stale_state_entity"
        assert issue_id in issues
        assert issues[issue_id].translation_key == "stale_reference"

    def test_inherited_guard_missing_creates_global_issue(
        self,
        hass: HomeAssistant,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Inherited guard with missing global entity produces a global issue naming the profile."""
        entry = _make_profile_entry(
            {"guard_mode": "inherit"},
            options={"shared_guard_entity": "input_boolean.gone"},
        )
        issues = _add_entry_and_sync(hass, entry)

        global_id = f"fn_{entry.entry_id}_stale_guard_entity_global"
        assert global_id in issues
        _assert_stale_reference_issue(
            issues[global_id],
            profiles="Test Profile",
            location="global options",
        )

    def test_custom_presence_missing(
        self,
        hass: HomeAssistant,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Custom presence with missing entities produces one issue listing all missing."""
        entry = _make_profile_entry(
            {
                "presence_mode": "custom",
                "presence_entities": ["person.gone_a", "person.gone_b"],
            }
        )
        issues = _add_entry_and_sync(hass, entry)

        sub_id = _profile_subentry_id(entry)
        issue_id = f"fn_{entry.entry_id}_{sub_id}_stale_presence_entities"
        assert issue_id in issues
        _assert_stale_reference_issue(
            issues[issue_id],
            profiles="Test Profile",
            location="profile settings",
            reference_contains=("person.gone_a", "person.gone_b"),
        )

    def test_inherited_presence_missing_creates_global_issue(
        self,
        hass: HomeAssistant,
        mock_frigate_data: dict[str, Any],
    ) -> None:
        """Inherited presence with missing global entities produces a global issue."""
        entry = _make_profile_entry(
            {"presence_mode": "inherit"},
            options={"shared_presence_entities": ["person.gone"]},
        )
        issues = _add_entry_and_sync(hass, entry)

        global_id = f"fn_{entry.entry_id}_stale_presence_entities_global"
        assert global_id in issues
        _assert_stale_reference_issue(
            issues[global_id],
            profiles="Test Profile",
            location="global options",
        )
