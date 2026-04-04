"""Save-time normalization for profile data."""

from typing import Any

from ...enums import GuardMode, PresenceMode, StateFilterMode, TimeFilterOverride


def normalize_profile_data(draft: dict[str, Any]) -> dict[str, Any]:
    """Normalize profile draft data for persistence.

    Called once at save time. Returns a new dict (does not mutate input).

    Responsibilities:
    - Prune empty optional string fields (top-level and per-phase)
    - Prune empty list/dict fields where empty means "no value"
    - Clean up conditional keys (guard_entity, state_entity, time filter fields)
    - Ensure phases dict exists
    """
    normalized = dict(draft)

    _prune_empty_strings(normalized)
    _prune_empty_lists(normalized)
    _clean_conditional_keys(normalized)
    _clean_phases(normalized)
    normalized.setdefault("phases", {})

    return normalized


_OPTIONAL_STRING_KEYS = ("title_template",)

_OPTIONAL_LIST_KEYS = (
    "objects",
    "required_zones",
    "include_sub_labels",
    "exclude_sub_labels",
)

_OPTIONAL_DICT_KEYS = ("zone_overrides",)

_OPTIONAL_COLLECTION_KEYS = ("action_config",)


def _prune_empty_strings(data: dict[str, Any]) -> None:
    """Remove optional string keys when blank."""
    for key in _OPTIONAL_STRING_KEYS:
        if key in data and not data[key]:
            del data[key]


def _prune_empty_lists(data: dict[str, Any]) -> None:
    """Remove optional list/dict/collection keys when empty."""
    for key in (*_OPTIONAL_LIST_KEYS, *_OPTIONAL_DICT_KEYS, *_OPTIONAL_COLLECTION_KEYS):
        if key in data and not data[key]:
            del data[key]


def _clean_conditional_keys(data: dict[str, Any]) -> None:
    """Ensure conditional keys only exist when their mode requires them."""
    if data.get("guard_mode") != GuardMode.CUSTOM:
        data.pop("guard_entity", None)

    if data.get("presence_mode") != PresenceMode.CUSTOM:
        data.pop("presence_entities", None)

    if data.get("state_filter_mode") != StateFilterMode.CUSTOM:
        data.pop("state_entity", None)
        data.pop("state_filter_states", None)

    if data.get("time_filter_override") != TimeFilterOverride.CUSTOM:
        data.pop("time_filter_mode", None)
        data.pop("time_filter_start", None)
        data.pop("time_filter_end", None)

    if not data.get("required_zones"):
        data.pop("zone_match_mode", None)


def _clean_phases(data: dict[str, Any]) -> None:
    """Prune blank optional fields within per-phase dicts."""
    phases = data.get("phases")
    if not isinstance(phases, dict):
        return
    for phase_data in phases.values():
        if not isinstance(phase_data, dict):
            continue
        if "subtitle_template" in phase_data and not phase_data["subtitle_template"]:
            del phase_data["subtitle_template"]
