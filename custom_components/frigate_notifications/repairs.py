"""Repair issue management for Notifications for Frigate."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers import issue_registry as ir
from homeassistant.util import slugify

from .const import DOMAIN, SUBENTRY_TYPE_PROFILE
from .data import get_available_frigate_cameras

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def sync_broken_camera_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create/resolve repair issues for profiles bound to missing Frigate cameras."""
    frigate_entry_id = entry.data["frigate_entry_id"]
    available = get_available_frigate_cameras(hass, frigate_entry_id)

    broken_cameras: set[str] = set()
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_PROFILE:
            continue
        for camera in subentry.data.get("cameras", []):
            if camera and camera not in available:
                broken_cameras.add(camera)

    for camera in broken_cameras:
        issue_id = f"broken_camera_binding_{entry.entry_id}_{slugify(camera)}"
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="broken_camera_binding",
            translation_placeholders={"camera": camera},
        )

    issue_reg = ir.async_get(hass)
    for issue_id, _issue in list(issue_reg.issues.items()):
        if issue_id[0] != DOMAIN:
            continue
        iid = issue_id[1]
        prefix = f"broken_camera_binding_{entry.entry_id}_"
        if iid.startswith(prefix):
            camera_slug = iid[len(prefix) :]
            if camera_slug not in {slugify(c) for c in broken_cameras}:
                ir.async_delete_issue(hass, DOMAIN, iid)


def sync_stale_zone_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create/resolve repair issues for zone configs referencing nonexistent zones."""
    frigate_entry_id = entry.data["frigate_entry_id"]

    stale_zones: set[str] = set()

    try:
        from .data import get_frigate_config

        frigate_config = get_frigate_config(hass, frigate_entry_id)
    except KeyError:
        return

    all_frigate_zones: set[str] = set()
    for cam_cfg in frigate_config["cameras"].values():
        all_frigate_zones.update(cam_cfg["zones"])

    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_PROFILE:
            continue
        required_zones = subentry.data.get("required_zones", [])
        for zone in required_zones:
            if zone not in all_frigate_zones:
                stale_zones.add(zone)

    issue_id = f"stale_zone_config_{entry.entry_id}"
    if stale_zones:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="stale_zone_config",
            translation_placeholders={"zones": ", ".join(sorted(stale_zones))},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)


def delete_all_issues_for_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete all repair issues associated with a config entry."""
    issue_reg = ir.async_get(hass)
    entry_suffix = entry.entry_id
    for issue_id, _issue in list(issue_reg.issues.items()):
        if issue_id[0] != DOMAIN:
            continue
        if entry_suffix in issue_id[1]:
            ir.async_delete_issue(hass, DOMAIN, issue_id[1])
