"""Repair issue management for Notifications for Frigate."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING

from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, SUBENTRY_TYPE_PROFILE
from .frigate_config import get_frigate_config_view

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry
    from homeassistant.core import HomeAssistant

    from .frigate_config import FrigateConfigView

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class IssueSpec:
    """Specification for a repair issue to create or keep."""

    translation_key: str
    translation_placeholders: dict[str, str] = field(default_factory=dict)
    severity: ir.IssueSeverity = ir.IssueSeverity.WARNING


def sync_repair_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Validate all profiles and global config, sync repair issues."""
    frigate_entry_id = entry.data["frigate_entry_id"]
    config_view = get_frigate_config_view(hass, frigate_entry_id)
    if config_view is None:
        return

    found: dict[str, IssueSpec] = {}

    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_PROFILE:
            continue
        _check_cameras(entry, subentry, config_view, found)
        _check_zones(entry, subentry, config_view, found)

    _reconcile(hass, entry.entry_id, found)


def delete_all_issues_for_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete all repair issues associated with a config entry."""
    prefix = f"fn_{entry.entry_id}_"
    issue_reg = ir.async_get(hass)
    for domain, iid in list(issue_reg.issues):
        if domain == DOMAIN and iid.startswith(prefix):
            ir.async_delete_issue(hass, DOMAIN, iid)


def _check_cameras(
    entry: ConfigEntry,
    subentry: ConfigSubentry,
    config_view: FrigateConfigView,
    found: dict[str, IssueSpec],
) -> None:
    """Produce an IssueSpec if the profile references missing cameras."""
    available = config_view.camera_names()
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
    config_view: FrigateConfigView,
    found: dict[str, IssueSpec],
) -> None:
    """Produce an IssueSpec if the profile references nonexistent zones."""
    all_zones: set[str] = set()
    for camera in config_view.cameras.values():
        all_zones.update(camera.zones)

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
