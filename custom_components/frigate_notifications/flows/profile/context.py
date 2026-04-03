"""FlowContext — derived context passed to profile step modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ...enums import Provider
from ...providers.base import ProviderFamilyCapabilities, get_capabilities
from ..helpers import camera_supports_genai, get_available_cameras, supports_genai

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_PHASE_ORDER = ("initial", "update", "end", "genai")


@dataclass(frozen=True)
class FlowContext:
    """Derived context passed to step modules."""

    provider: Provider
    capabilities: ProviderFamilyCapabilities
    enabled_phases: tuple[str, ...]
    is_reconfiguring: bool
    available_cameras: list[str]
    genai_available: bool
    hass: HomeAssistant
    entry: ConfigEntry
    frigate_entry_id: str


def _derive_enabled_phases(
    draft: dict[str, Any], *, genai_available: bool = True
) -> tuple[str, ...]:
    """Return phase names that are currently enabled in the draft."""
    phases = draft.get("phases", {})
    return tuple(
        p
        for p in _PHASE_ORDER
        if (p != "genai" or genai_available) and phases.get(p, {}).get("enabled", True)
    )


def build_flow_context(
    hass: HomeAssistant,
    entry: ConfigEntry,
    draft: dict[str, Any],
    *,
    is_reconfiguring: bool,
) -> FlowContext:
    """Construct a FlowContext from current handler state."""
    provider = Provider(draft.get("provider", "apple"))
    frigate_entry_id = entry.data["frigate_entry_id"]
    selected_cameras = draft.get("cameras", [])
    genai = (
        any(camera_supports_genai(hass, frigate_entry_id, cam) for cam in selected_cameras)
        if selected_cameras
        else supports_genai(hass, frigate_entry_id)
    )
    return FlowContext(
        provider=provider,
        capabilities=get_capabilities(provider),
        enabled_phases=_derive_enabled_phases(draft, genai_available=genai),
        is_reconfiguring=is_reconfiguring,
        available_cameras=get_available_cameras(hass, frigate_entry_id),
        genai_available=genai,
        hass=hass,
        entry=entry,
        frigate_entry_id=frigate_entry_id,
    )
