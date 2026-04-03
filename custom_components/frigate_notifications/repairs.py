"""Repair issue management for Notifications for Frigate."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers import issue_registry as ir
from homeassistant.util import slugify

from .const import DOMAIN, SUBENTRY_TYPE_PROFILE
from .data import get_available_frigate_cameras, get_frigate_config

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def sync_broken_camera_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create/resolve repair issues for profiles bound to missing Frigate cameras."""
    frigate_entry_id = entry.data["frigate_entry_id"]
    try:
        get_frigate_config(hass, frigate_entry_id)
    except KeyError:
        return
    available = get_available_frigate_cameras(hass, frigate_entry_id)

    active_issue_keys: set[tuple[str, str]] = set()

    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_PROFILE:
            continue
        profile_name = subentry.data.get("name", subentry.title)
        for camera in subentry.data.get("cameras", []):
            if camera and camera not in available:
                active_issue_keys.add((subentry.subentry_id, camera))
                issue_id = (
                    f"broken_camera_{entry.entry_id}_{subentry.subentry_id}_{slugify(camera)}"
                )
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=False,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="broken_camera_binding",
                    translation_placeholders={
                        "profile_name": profile_name,
                        "camera": camera,
                    },
                )

    active_slugs = {f"{sub_id}_{slugify(cam)}" for sub_id, cam in active_issue_keys}
    prefix = f"broken_camera_{entry.entry_id}_"

    issue_reg = ir.async_get(hass)
    for issue_id, _issue in list(issue_reg.issues.items()):
        if issue_id[0] != DOMAIN:
            continue
        iid = issue_id[1]
        if iid.startswith(prefix):
            suffix = iid[len(prefix) :]
            if suffix not in active_slugs:
                ir.async_delete_issue(hass, DOMAIN, iid)


def sync_stale_zone_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create/resolve repair issues for zone configs referencing nonexistent zones."""
    frigate_entry_id = entry.data["frigate_entry_id"]

    try:
        frigate_config = get_frigate_config(hass, frigate_entry_id)
    except KeyError:
        return

    all_frigate_zones: set[str] = set()
    for cam_cfg in frigate_config["cameras"].values():
        all_frigate_zones.update(cam_cfg["zones"])

    active_subentry_ids: set[str] = set()

    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_PROFILE:
            continue
        required_zones = subentry.data.get("required_zones", [])
        stale = [z for z in required_zones if z not in all_frigate_zones]
        if stale:
            active_subentry_ids.add(subentry.subentry_id)
            profile_name = subentry.data.get("name", subentry.title)
            issue_id = f"stale_zone_{entry.entry_id}_{subentry.subentry_id}"
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="stale_zone_config",
                translation_placeholders={
                    "profile_name": profile_name,
                    "zones": ", ".join(sorted(stale)),
                },
            )

    prefix = f"stale_zone_{entry.entry_id}_"
    issue_reg = ir.async_get(hass)
    for issue_id, _issue in list(issue_reg.issues.items()):
        if issue_id[0] != DOMAIN:
            continue
        iid = issue_id[1]
        if iid.startswith(prefix):
            sub_id = iid[len(prefix) :]
            if sub_id not in active_subentry_ids:
                ir.async_delete_issue(hass, DOMAIN, iid)


def delete_all_issues_for_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete all repair issues associated with a config entry."""
    issue_reg = ir.async_get(hass)
    entry_suffix = entry.entry_id
    for issue_id, _issue in list(issue_reg.issues.items()):
        if issue_id[0] != DOMAIN:
            continue
        if entry_suffix in issue_id[1]:
            ir.async_delete_issue(hass, DOMAIN, issue_id[1])
