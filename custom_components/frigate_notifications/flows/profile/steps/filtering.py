"""Filtering step — schema, validation, and apply for profile filters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TimeSelector,
)
import voluptuous as vol

from ....enums import (
    GuardMode,
    PresenceMode,
    RecognitionMode,
    Severity,
    StateFilterMode,
    TimeFilterMode,
    ZoneMatchMode,
)
from ...helpers import (
    GUARD_ENTITY_SELECTOR,
    discover_camera_sub_labels,
    get_camera_zones,
    get_tracked_objects,
    humanized_options,
)

if TYPE_CHECKING:
    from ..context import FlowContext


def build_filtering_schema(draft: dict[str, Any], ctx: FlowContext) -> vol.Schema:
    """Build the filtering step form schema.

    Includes objects, severity, zones (single-camera only), guard, time filter,
    presence, state filter, and recognition config sections.
    """
    cameras = draft["cameras"]
    is_multi = len(cameras) > 1

    fid = ctx.frigate_entry_id
    all_objects = sorted(
        {obj for cam in cameras for obj in get_tracked_objects(ctx.hass, fid, cam)}
    )

    schema_fields: dict[Any, Any] = {
        vol.Optional("objects"): SelectSelector(
            SelectSelectorConfig(
                options=humanized_options(all_objects),
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required("severity", default=Severity.ALERT): SelectSelector(
            SelectSelectorConfig(
                options=[Severity.ALERT, Severity.DETECTION, Severity.ANY],
                translation_key="severity",
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    }

    if not is_multi:
        camera_zones = get_camera_zones(ctx.hass, fid, cameras[0])
        schema_fields[vol.Optional("required_zones")] = SelectSelector(
            SelectSelectorConfig(
                options=humanized_options(camera_zones),
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
        schema_fields[vol.Optional("zone_match_mode", default=ZoneMatchMode.ANY)] = SelectSelector(
            SelectSelectorConfig(
                options=[ZoneMatchMode.ANY, ZoneMatchMode.ALL, ZoneMatchMode.ORDERED],
                translation_key="zone_match_mode",
                mode=SelectSelectorMode.DROPDOWN,
            )
        )

    schema_fields.update(
        {
            vol.Optional("guard_config"): section(
                vol.Schema(
                    {
                        vol.Required("guard_mode", default=GuardMode.INHERIT): SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    GuardMode.INHERIT,
                                    GuardMode.CUSTOM,
                                    GuardMode.DISABLED,
                                ],
                                translation_key="guard_mode",
                                mode=SelectSelectorMode.DROPDOWN,
                            )
                        ),
                        vol.Optional("guard_entity"): GUARD_ENTITY_SELECTOR,
                    }
                ),
                SectionConfig(collapsed=True),
            ),
            vol.Optional("time_filter_config"): section(
                vol.Schema(
                    {
                        vol.Optional("time_filter_override", default="inherit"): SelectSelector(
                            SelectSelectorConfig(
                                options=["inherit", "custom", "disabled"],
                                translation_key="time_filter_override",
                                mode=SelectSelectorMode.DROPDOWN,
                            )
                        ),
                        vol.Optional("time_filter_mode"): SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    TimeFilterMode.ONLY_DURING,
                                    TimeFilterMode.NOT_DURING,
                                ],
                                translation_key="time_filter_mode",
                                mode=SelectSelectorMode.DROPDOWN,
                            )
                        ),
                        vol.Optional("time_filter_start"): TimeSelector(),
                        vol.Optional("time_filter_end"): TimeSelector(),
                    }
                ),
                SectionConfig(collapsed=True),
            ),
            vol.Optional("presence_config"): section(
                vol.Schema(
                    {
                        vol.Optional("presence_mode", default=PresenceMode.INHERIT): SelectSelector(
                            SelectSelectorConfig(
                                options=[PresenceMode.INHERIT, PresenceMode.DISABLED],
                                translation_key="presence_mode",
                                mode=SelectSelectorMode.DROPDOWN,
                            )
                        ),
                    }
                ),
                SectionConfig(collapsed=True),
            ),
            vol.Optional("state_filter_config"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            "state_filter_mode", default=StateFilterMode.INHERIT
                        ): SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    StateFilterMode.INHERIT,
                                    StateFilterMode.CUSTOM,
                                    StateFilterMode.DISABLED,
                                ],
                                translation_key="state_filter_mode",
                                mode=SelectSelectorMode.DROPDOWN,
                            )
                        ),
                        vol.Optional("state_entity"): EntitySelector(EntitySelectorConfig()),
                        vol.Optional("state_filter_states"): SelectSelector(
                            SelectSelectorConfig(
                                options=["on", "off", "home", "not_home", "open", "closed"],
                                custom_value=True,
                                multiple=True,
                                mode=SelectSelectorMode.DROPDOWN,
                            )
                        ),
                    }
                ),
                SectionConfig(collapsed=True),
            ),
        }
    )
    schema = vol.Schema(schema_fields)

    all_sub_labels = sorted(
        {sl for cam in cameras for sl in discover_camera_sub_labels(ctx.hass, fid, cam)}
    )
    if all_sub_labels:
        sub_label_names = sorted({name for _, name in all_sub_labels})
        sub_label_options = [SelectOptionDict(value=s, label=s) for s in sub_label_names]
        schema = schema.extend(
            {
                vol.Optional("recognition_config"): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                "recognition_mode",
                                default=RecognitionMode.DISABLED,
                            ): SelectSelector(
                                SelectSelectorConfig(
                                    options=[
                                        RecognitionMode.DISABLED,
                                        RecognitionMode.REQUIRE_RECOGNIZED,
                                        RecognitionMode.EXCLUDE_SUB_LABELS,
                                    ],
                                    translation_key="recognition_mode",
                                    mode=SelectSelectorMode.DROPDOWN,
                                )
                            ),
                            vol.Optional("include_sub_labels"): SelectSelector(
                                SelectSelectorConfig(
                                    options=sub_label_options,
                                    multiple=True,
                                    mode=SelectSelectorMode.DROPDOWN,
                                )
                            ),
                            vol.Optional("exclude_sub_labels"): SelectSelector(
                                SelectSelectorConfig(
                                    options=sub_label_options,
                                    multiple=True,
                                    mode=SelectSelectorMode.DROPDOWN,
                                )
                            ),
                        }
                    ),
                    SectionConfig(collapsed=True),
                ),
            }
        )

    return schema


def build_filtering_suggested(draft: dict[str, Any], ctx: FlowContext) -> dict[str, Any]:
    """Build suggested values dict for the filtering form."""
    cameras = draft["cameras"]
    fid = ctx.frigate_entry_id
    suggested = dict(draft)

    suggested["guard_config"] = {
        "guard_mode": draft.get("guard_mode", GuardMode.INHERIT),
    }
    if "guard_entity" in draft:
        suggested["guard_config"]["guard_entity"] = draft["guard_entity"]

    suggested["time_filter_config"] = {}
    for key in (
        "time_filter_override",
        "time_filter_mode",
        "time_filter_start",
        "time_filter_end",
    ):
        if key in draft:
            suggested["time_filter_config"][key] = draft[key]

    suggested["presence_config"] = {
        "presence_mode": draft.get("presence_mode", PresenceMode.INHERIT),
    }

    suggested["state_filter_config"] = {}
    for key in ("state_filter_mode", "state_entity", "state_filter_states"):
        if key in draft:
            suggested["state_filter_config"][key] = draft[key]

    all_sub_labels = sorted(
        {sl for cam in cameras for sl in discover_camera_sub_labels(ctx.hass, fid, cam)}
    )
    if all_sub_labels:
        suggested["recognition_config"] = {
            "recognition_mode": draft.get("recognition_mode", RecognitionMode.DISABLED),
            "include_sub_labels": draft.get("include_sub_labels", []),
            "exclude_sub_labels": draft.get("exclude_sub_labels", []),
        }

    return suggested


def validate_filtering_input(
    draft: dict[str, Any], user_input: dict[str, Any], ctx: FlowContext
) -> dict[str, str]:
    """Validate filtering step input. Returns error dict."""
    errors: dict[str, str] = {}
    guard_sec = user_input.get("guard_config", {})
    tf_sec = user_input.get("time_filter_config", {})
    sf_sec = user_input.get("state_filter_config", {})

    if guard_sec.get("guard_mode", GuardMode.INHERIT) == GuardMode.CUSTOM and not guard_sec.get(
        "guard_entity"
    ):
        errors["guard_entity"] = "guard_entity_required"
    time_override = tf_sec.get("time_filter_override", "inherit")
    if time_override == "custom":
        tf_mode = tf_sec.get("time_filter_mode")
        if tf_mode and tf_mode != TimeFilterMode.DISABLED:
            if not tf_sec.get("time_filter_start"):
                errors["time_filter_start"] = "time_filter_start_required"
            if not tf_sec.get("time_filter_end"):
                errors["time_filter_end"] = "time_filter_end_required"
    if sf_sec.get(
        "state_filter_mode", StateFilterMode.INHERIT
    ) == StateFilterMode.CUSTOM and not sf_sec.get("state_entity"):
        errors["state_entity"] = "state_entity_required"

    rec_sec = user_input.get("recognition_config", {})
    include = set(rec_sec.get("include_sub_labels", []))
    exclude = set(rec_sec.get("exclude_sub_labels", []))
    if include & exclude:
        errors["exclude_sub_labels"] = "sub_label_overlap"

    return errors


def apply_filtering_input(
    draft: dict[str, Any], user_input: dict[str, Any], ctx: FlowContext
) -> None:
    """Apply filtering input to draft data."""
    guard_sec = user_input.get("guard_config", {})
    tf_sec = user_input.get("time_filter_config", {})
    pres_sec = user_input.get("presence_config", {})
    sf_sec = user_input.get("state_filter_config", {})

    objects = user_input.get("objects") or []
    if objects:
        draft["objects"] = objects
    else:
        draft.pop("objects", None)
    draft["severity"] = user_input["severity"]

    guard_mode = guard_sec.get("guard_mode", GuardMode.INHERIT)
    draft["guard_mode"] = guard_mode
    if guard_mode == GuardMode.CUSTOM:
        draft["guard_entity"] = guard_sec["guard_entity"]
    else:
        draft.pop("guard_entity", None)

    required_zones = user_input.get("required_zones") or []
    if required_zones:
        draft["required_zones"] = required_zones
        draft["zone_match_mode"] = user_input.get("zone_match_mode", ZoneMatchMode.ANY)
    else:
        draft.pop("required_zones", None)
        draft.pop("zone_match_mode", None)

    time_override = tf_sec.get("time_filter_override", "inherit")
    draft["time_filter_override"] = time_override
    if time_override == "custom":
        draft["time_filter_mode"] = tf_sec.get("time_filter_mode", TimeFilterMode.DISABLED)
        draft["time_filter_start"] = tf_sec.get("time_filter_start", "")
        draft["time_filter_end"] = tf_sec.get("time_filter_end", "")
    else:
        draft.pop("time_filter_mode", None)
        draft.pop("time_filter_start", None)
        draft.pop("time_filter_end", None)

    draft["presence_mode"] = pres_sec.get("presence_mode", PresenceMode.INHERIT)

    sf_mode = sf_sec.get("state_filter_mode", StateFilterMode.INHERIT)
    draft["state_filter_mode"] = sf_mode
    if sf_mode == StateFilterMode.CUSTOM:
        draft["state_entity"] = sf_sec.get("state_entity", "")
        draft["state_filter_states"] = sf_sec.get("state_filter_states", [])
    else:
        draft.pop("state_entity", None)
        draft.pop("state_filter_states", None)

    rec_sec = user_input.get("recognition_config", {})
    draft["recognition_mode"] = rec_sec.get("recognition_mode", RecognitionMode.DISABLED)
    draft["include_sub_labels"] = rec_sec.get("include_sub_labels", [])
    draft["exclude_sub_labels"] = rec_sec.get("exclude_sub_labels", [])
