"""Repair issue management for Notifications for Frigate."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir

from .const import DOMAIN, SUBENTRY_TYPE_PROFILE
from .frigate_config import get_frigate_config_view

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry
    from homeassistant.core import HomeAssistant


_LOGGER = logging.getLogger(__name__)

FRIGATE_TERMINAL_FAILURE = {
    ConfigEntryState.SETUP_ERROR,
    ConfigEntryState.MIGRATION_ERROR,
}


class FrigateEntryStatus(StrEnum):
    """Availability state for the linked Frigate config entry."""

    AVAILABLE = "available"
    TRANSIENT = "transient"
    ACTION_REQUIRED = "action_required"


@dataclass(frozen=True)
class IssueSpec:
    """Specification for a repair issue to create or keep."""

    translation_key: str
    translation_placeholders: dict[str, str] = field(default_factory=dict)
    severity: ir.IssueSeverity = ir.IssueSeverity.WARNING


def sync_repair_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Validate all profiles and global config, sync repair issues."""
    found: dict[str, IssueSpec] = {}
    frigate_entry_id = entry.data["frigate_entry_id"]

    status = _check_frigate_entry(hass, entry, found)
    if status is FrigateEntryStatus.ACTION_REQUIRED:
        _reconcile(hass, entry.entry_id, found)
        return
    if status is FrigateEntryStatus.TRANSIENT:
        return

    config_view = get_frigate_config_view(hass, frigate_entry_id)
    if config_view is None:
        return

    available_cameras = config_view.camera_names()
    all_zones = {zone for camera in config_view.cameras.values() for zone in camera.zones}

    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_PROFILE:
            continue
        _check_cameras(entry, subentry, available_cameras, found)
        _check_zones(entry, subentry, all_zones, found)
        _check_notify_target(hass, entry, subentry, found)
        _check_entity_references(hass, entry, subentry, found)

    _reconcile(hass, entry.entry_id, found)


def delete_all_issues_for_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete all repair issues associated with a config entry."""
    prefix = f"fn_{entry.entry_id}_"
    issue_reg = ir.async_get(hass)
    for domain, iid in list(issue_reg.issues):
        if domain == DOMAIN and iid.startswith(prefix):
            ir.async_delete_issue(hass, DOMAIN, iid)


def _check_frigate_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    found: dict[str, IssueSpec],
) -> FrigateEntryStatus:
    """Classify whether the linked Frigate entry can be used for validation."""
    frigate_entry_id = entry.data["frigate_entry_id"]
    frigate_entry = hass.config_entries.async_get_entry(frigate_entry_id)

    if frigate_entry is None or frigate_entry.state in FRIGATE_TERMINAL_FAILURE:
        issue_id = f"fn_{entry.entry_id}_linked_frigate_unavailable"
        found[issue_id] = IssueSpec(
            translation_key="linked_frigate_unavailable",
            severity=ir.IssueSeverity.ERROR,
        )
        return FrigateEntryStatus.ACTION_REQUIRED

    if frigate_entry.state is not ConfigEntryState.LOADED:
        return FrigateEntryStatus.TRANSIENT

    return FrigateEntryStatus.AVAILABLE


def _check_cameras(
    entry: ConfigEntry,
    subentry: ConfigSubentry,
    available: set[str],
    found: dict[str, IssueSpec],
) -> None:
    """Produce an IssueSpec if the profile references missing cameras."""
    broken = [cam for cam in subentry.data.get("cameras", []) if cam and cam not in available]
    if not broken:
        return
    issue_id = f"fn_{entry.entry_id}_{subentry.subentry_id}_broken_cameras"
    found[issue_id] = IssueSpec(
        translation_key="broken_camera_binding",
        translation_placeholders={
            "profile_name": subentry.data.get("name", subentry.title),
            "cameras": ", ".join(sorted(broken)),
        },
    )


def _check_zones(
    entry: ConfigEntry,
    subentry: ConfigSubentry,
    all_zones: set[str],
    found: dict[str, IssueSpec],
) -> None:
    """Produce an IssueSpec if the profile references nonexistent zones."""
    required_zones = subentry.data.get("required_zones", [])
    stale = [z for z in required_zones if z not in all_zones]
    if not stale:
        return
    issue_id = f"fn_{entry.entry_id}_{subentry.subentry_id}_stale_zones"
    found[issue_id] = IssueSpec(
        translation_key="stale_zone_config",
        translation_placeholders={
            "profile_name": subentry.data.get("name", subentry.title),
            "zones": ", ".join(sorted(stale)),
        },
    )


def _check_notify_target(
    hass: HomeAssistant,
    entry: ConfigEntry,
    subentry: ConfigSubentry,
    found: dict[str, IssueSpec],
) -> None:
    """Produce an IssueSpec if the profile's notify device no longer exists."""
    device_id = subentry.data.get("notify_device", "")
    if not device_id:
        return

    dev_reg = dr.async_get(hass)
    if dev_reg.async_get(device_id) is not None:
        return

    issue_id = f"fn_{entry.entry_id}_{subentry.subentry_id}_stale_notify_target"
    _add_stale_reference_issue(
        found,
        issue_id,
        reference=f"notification device {device_id}",
        profiles=subentry.data.get("name", subentry.title),
        location="profile settings",
    )


def _check_entity_references(
    hass: HomeAssistant,
    entry: ConfigEntry,
    subentry: ConfigSubentry,
    found: dict[str, IssueSpec],
) -> None:
    """Check guard, state filter, and presence entity references for staleness."""
    _check_single_entity(
        hass,
        entry,
        subentry,
        mode_key="guard_mode",
        entity_key="guard_entity",
        global_entity_key="shared_guard_entity",
        check_type="stale_guard_entity",
        reference_type="guard entity",
        found=found,
    )
    _check_single_entity(
        hass,
        entry,
        subentry,
        mode_key="state_filter_mode",
        entity_key="state_entity",
        global_entity_key="shared_state_entity",
        check_type="stale_state_entity",
        reference_type="state filter entity",
        found=found,
        states_key="state_filter_states",
        global_states_key="shared_state_filter_states",
    )
    _check_presence_entities(hass, entry, subentry, found)


def _check_single_entity(
    hass: HomeAssistant,
    entry: ConfigEntry,
    subentry: ConfigSubentry,
    *,
    mode_key: str,
    entity_key: str,
    global_entity_key: str,
    check_type: str,
    reference_type: str,
    found: dict[str, IssueSpec],
    states_key: str | None = None,
    global_states_key: str | None = None,
) -> None:
    """Check a single entity reference (guard or state filter) for staleness."""
    mode = subentry.data.get(mode_key, "inherit")

    if mode == "disabled":
        return

    if mode == "custom":
        if states_key is not None and not subentry.data.get(states_key, []):
            return
        entity_id = subentry.data.get(entity_key, "")
        if not entity_id:
            return
        if _entity_reference_exists(hass, entity_id):
            return
        issue_id = f"fn_{entry.entry_id}_{subentry.subentry_id}_{check_type}"
        _add_stale_reference_issue(
            found,
            issue_id,
            reference=f"{reference_type} {entity_id}",
            profiles=subentry.data.get("name", subentry.title),
            location="profile settings",
        )
        return

    # inherit — check global entity, issue against entry (not profile).
    if global_states_key is not None and not entry.options.get(global_states_key, []):
        return
    entity_id = entry.options.get(global_entity_key, "")
    if not entity_id:
        return
    if _entity_reference_exists(hass, entity_id):
        return
    issue_id = f"fn_{entry.entry_id}_{check_type}_global"
    _add_stale_reference_issue(
        found,
        issue_id,
        reference=f"{reference_type} {entity_id}",
        profiles=_affected_inheriting_profiles(entry, mode_key),
        location="global options",
    )


def _check_presence_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    subentry: ConfigSubentry,
    found: dict[str, IssueSpec],
) -> None:
    """Check presence entity references for staleness."""
    mode = subentry.data.get("presence_mode", "inherit")

    if mode == "disabled":
        return

    if mode == "custom":
        entities = subentry.data.get("presence_entities", [])
        scope_id: str | None = subentry.subentry_id
        profile_name = subentry.data.get("name", subentry.title)
    else:
        entities = entry.options.get("shared_presence_entities", [])
        scope_id = None
        profile_name = _affected_inheriting_profiles(entry, "presence_mode")

    missing = [eid for eid in entities if eid and not _entity_reference_exists(hass, eid)]
    if not missing:
        return

    if scope_id is None:
        issue_id = f"fn_{entry.entry_id}_stale_presence_entities_global"
    else:
        issue_id = f"fn_{entry.entry_id}_{scope_id}_stale_presence_entities"
    missing_refs = ", ".join(sorted(missing))
    _add_stale_reference_issue(
        found,
        issue_id,
        reference=f"presence entities {missing_refs}",
        profiles=profile_name,
        location="profile settings" if scope_id is not None else "global options",
    )


def _affected_inheriting_profiles(entry: ConfigEntry, mode_key: str) -> str:
    """Return comma-separated display names of profiles that inherit the given mode."""
    names: list[str] = []
    for sub in entry.subentries.values():
        if sub.subentry_type != SUBENTRY_TYPE_PROFILE:
            continue
        if sub.data.get(mode_key, "inherit") == "inherit":
            names.append(sub.data.get("name", sub.title))
    return ", ".join(sorted(names))


def _entity_reference_exists(hass: HomeAssistant, entity_id: str) -> bool:
    """Return whether an entity reference still exists in HA."""
    ent_reg = er.async_get(hass)
    return ent_reg.async_get(entity_id) is not None or hass.states.get(entity_id) is not None


def _add_stale_reference_issue(
    found: dict[str, IssueSpec],
    issue_id: str,
    *,
    reference: str,
    profiles: str,
    location: str,
) -> None:
    """Add a generic stale Home Assistant reference repair issue."""
    found[issue_id] = IssueSpec(
        translation_key="stale_reference",
        translation_placeholders={
            "reference": reference,
            "profiles": profiles,
            "location": location,
        },
    )


def _reconcile(
    hass: HomeAssistant,
    entry_id: str,
    found: dict[str, IssueSpec],
) -> None:
    """Single-pass reconciliation against the issue registry."""
    prefix = f"fn_{entry_id}_"
    issue_reg = ir.async_get(hass)

    for issue_id, spec in found.items():
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=spec.severity,
            translation_key=spec.translation_key,
            translation_placeholders=spec.translation_placeholders,
        )

    for domain, iid in list(issue_reg.issues):
        if domain == DOMAIN and iid.startswith(prefix) and iid not in found:
            ir.async_delete_issue(hass, DOMAIN, iid)
