"""Template rendering and notification context building."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.template import Template, TemplateError
from homeassistant.util import dt as dt_util

from .const import humanize_zone
from .enums import Lifecycle, Phase

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .config import PhaseConfig
    from .data import ProfileRuntime
    from .models import Review

_LOGGER = logging.getLogger(__name__)


def _clean_objects(objects: list[str]) -> list[str]:
    """Remove -verified suffix and deduplicate, preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for obj in objects:
        clean = obj.replace("-verified", "")
        if clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _get_emoji(item: str, profile: ProfileRuntime) -> str:
    """Look up emoji: sub_label_overrides (original case) -> emoji_map (normalized) -> default."""
    if val := profile.sub_label_overrides.get(item):
        return val
    return profile.emoji_map.get(item.lower().replace(" ", "_"), profile.default_emoji)


def _build_subjects(
    objects: list[str],
    sub_labels: list[str],
    profile: ProfileRuntime,
    *,
    emoji_mode: bool,
) -> list[str]:
    """Build the merged subject list."""
    non_verified = [o for o in objects if not o.endswith("-verified")]
    clean = _clean_objects(non_verified)

    seen: set[str] = set()
    merged: list[str] = []
    for sl in sub_labels:
        key = sl.lower()
        if key not in seen:
            seen.add(key)
            merged.append(sl)

    for obj in clean:
        key = obj.lower()
        if key not in seen:
            seen.add(key)
            display = obj.replace("_", " ").title()
            merged.append(display)

    if emoji_mode:
        result: list[str] = []
        for item in merged:
            emoji = _get_emoji(item, profile)
            result.append(f"{emoji} {item}" if emoji else item)
        return result
    return merged


class TemplateCache:
    """Cache for parsed HA Template objects."""

    def __init__(self) -> None:
        """Initialize empty template cache."""
        self._cache: dict[str, Template] = {}

    def get_or_create(self, template_str: str, hass: HomeAssistant | None) -> Template:
        """Return a cached Template or create and cache a new one."""
        tpl = self._cache.get(template_str)
        if tpl is None:
            tpl = Template(template_str, hass)
            self._cache[template_str] = tpl
        return tpl

    def clear(self) -> None:
        """Clear all cached templates."""
        self._cache.clear()


def render_template(
    hass: HomeAssistant | None,
    template_str: str,
    ctx: Mapping[str, Any],
    cache: TemplateCache | None = None,
) -> str:
    """Render a Jinja2 template string with the given context."""
    if not template_str:
        return ""
    if cache is not None:
        tpl = cache.get_or_create(template_str, hass)
    else:
        tpl = Template(template_str, hass)
    return tpl.async_render(variables=ctx, parse_result=False)


def build_context(
    review: Review,
    config: ProfileRuntime,
    phase: Phase,
    lifecycle: Lifecycle,
    *,
    emoji_mode: bool = True,
    hass: HomeAssistant | None = None,
    global_zone_aliases: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build the complete variable context dict for template rendering."""
    clean_objs = _clean_objects(review.objects)
    first_obj = clean_objs[0] if clean_objs else ""
    first_zone = review.zones[0] if review.zones else ""
    last_zone = review.zones[-1] if review.zones else ""

    emoji = _get_emoji(first_obj, config) if first_obj else ""
    subjects = _build_subjects(review.objects, review.sub_labels, config, emoji_mode=emoji_mode)
    first_subject = subjects[0] if subjects else ""
    subjects_str = ", ".join(subjects)

    before_subjects = _build_subjects(
        review.before_objects, review.before_sub_labels, config, emoji_mode=emoji_mode
    )
    before_set = {s.lower() for s in before_subjects}
    added = [s for s in subjects if s.lower() not in before_set]
    added_subject = ", ".join(added)

    if first_zone:
        if config.zone_aliases:
            zone_alias = config.zone_aliases.get(first_zone, humanize_zone(first_zone))
        elif global_zone_aliases:
            camera_aliases = global_zone_aliases.get(review.camera, {})
            zone_alias = camera_aliases.get(first_zone, humanize_zone(first_zone))
        else:
            zone_alias = humanize_zone(first_zone)
    else:
        zone_alias = ""

    # Zone phrase: two-pass rendering (override may be Jinja2 template).
    zone_override_tpl = config.zone_overrides.get(first_zone, "") if first_zone else ""
    if zone_override_tpl and hass is not None:
        partial_ctx = {
            "object": first_obj.replace("_", " ").title() if first_obj else "",
            "objects": ", ".join(o.replace("_", " ").title() for o in clean_objs),
            "emoji": emoji,
            "zone_alias": zone_alias,
            "zone_name": humanize_zone(first_zone) if first_zone else "",
            "sub_label": review.sub_labels[0] if review.sub_labels else "",
            "severity": review.severity,
            "camera_name": humanize_zone(review.camera),
        }
        try:
            rendered = render_template(hass, zone_override_tpl, partial_ctx)
            zone_phrase = rendered.strip() or "detected"
        except TemplateError:
            zone_phrase = "detected"
    elif zone_override_tpl:
        zone_phrase = zone_override_tpl
    else:
        zone_phrase = "detected"

    zone_text = (
        config.zone_overrides.get(first_zone, humanize_zone(first_zone)) if first_zone else ""
    )

    before_zones_set = set(review.before_zones)
    added_zones = ", ".join(humanize_zone(z) for z in sorted(set(review.zones) - before_zones_set))

    genai = review.genai
    genai_summary = genai.short_summary if genai else ""

    first_det_id = review.detection_ids[0] if review.detection_ids else review.review_id
    latest_det_id = review.latest_detection_id or first_det_id

    phase_emoji = config.phase_emoji_map.get(phase.value, "")

    now = datetime.now(tz=dt_util.DEFAULT_TIME_ZONE)

    return {
        # Tier 1: raw.
        "objects_raw": ", ".join(review.objects),
        "sub_labels_raw": ", ".join(review.sub_labels),
        "zones_raw": ", ".join(review.zones),
        "object_count": str(len(clean_objs)),
        # Tier 2: formatted objects.
        "object": first_obj.replace("_", " ").title() if first_obj else "",
        "objects": ", ".join(o.replace("_", " ").title() for o in clean_objs),
        # Tier 2: formatted subjects.
        "subject": first_subject,
        "subjects": subjects_str,
        "added_subject": added_subject,
        # Tier 2: sub_labels (deduped, raw form).
        "sub_label": review.sub_labels[0] if review.sub_labels else "",
        "sub_labels": ", ".join(dict.fromkeys(review.sub_labels)),
        # Tier 2: zone.
        "zone": first_zone,
        "zones": ", ".join(humanize_zone(z) for z in review.zones),
        "first_zone": first_zone,
        "last_zone": last_zone,
        "first_zone_name": humanize_zone(first_zone) if first_zone else "",
        "last_zone_name": humanize_zone(last_zone) if last_zone else "",
        "zone_name": humanize_zone(first_zone) if first_zone else "",
        "zone_text": zone_text,
        "zone_alias": zone_alias,
        "zone_phrase": zone_phrase,
        "added_zones": added_zones,
        # Camera and metadata.
        "camera": review.camera,
        "camera_name": humanize_zone(review.camera),
        "phase": str(phase),
        "lifecycle": str(lifecycle),
        "phase_emoji": phase_emoji,
        "severity": review.severity,
        "emoji": emoji,
        "time": now.strftime("%-I:%M %p"),
        "time_24hr": now.strftime("%H:%M"),
        # Phase flags.
        "is_initial": phase == Phase.INITIAL,
        "is_update": phase == Phase.UPDATE,
        "is_end": phase == Phase.END,
        "is_genai": phase == Phase.GENAI,
        # GenAI.
        "genai_title": genai.title if genai else "",
        "genai_summary": genai_summary,
        "genai_scene": genai.scene if genai else "",
        "genai_confidence": str(genai.confidence) if genai else "",
        "genai_threat_level": str(genai.threat_level) if genai else "",
        "genai_concerns": ", ".join(genai.other_concerns) if genai else "",
        "genai_time": genai.time if genai else "",
        # Event data.
        "start_time": str(review.start_time),
        "end_time": str(review.end_time) if review.end_time else "",
        "duration": str(int(review.end_time - review.start_time)) if review.end_time else "",
        # IDs.
        "review_id": review.review_id,
        "detection_id": first_det_id,
        "latest_detection_id": latest_det_id,
        "base_url": config.base_url,
        "frigate_url": config.frigate_url,
        "client_id": config.client_id,
    }


def resolve_template(id_or_jinja: str, id_map: dict[str, str]) -> str:
    """Resolve a template ID to Jinja, or pass raw Jinja through unchanged."""
    return id_map.get(id_or_jinja, id_or_jinja)


@dataclass(frozen=True)
class RenderedContent:
    """The rendered title, message, and subtitle."""

    title: str
    message: str
    subtitle: str


def render_notification(
    hass: HomeAssistant,
    profile: ProfileRuntime,
    review: Review,
    phase_name: Phase,
    phase_config: PhaseConfig,
    lifecycle: Lifecycle,
    cache: TemplateCache | None = None,
    *,
    global_zone_aliases: dict[str, dict[str, str]] | None = None,
    template_id_map: dict[str, str] | None = None,
) -> RenderedContent:
    """Render title/message/subtitle from phase config."""
    _map = template_id_map or {}

    ctx = build_context(
        review,
        profile,
        phase_name,
        lifecycle,
        emoji_mode=phase_config.content.emoji_message,
        hass=hass,
        global_zone_aliases=global_zone_aliases,
    )

    message_tpl = resolve_template(phase_config.content.message_template, _map)
    try:
        message = render_template(hass, message_tpl, ctx, cache)
    except TemplateError:
        _LOGGER.warning("Message template render failed, using raw template")
        message = message_tpl

    title_tpl = resolve_template(
        phase_config.content.title_template or profile.title_template, _map
    )
    try:
        title = render_template(hass, title_tpl, ctx, cache)
    except TemplateError:
        _LOGGER.warning("Title template render failed, using raw template")
        title = title_tpl

    subtitle_tpl = resolve_template(phase_config.content.subtitle_template, _map)
    if subtitle_tpl:
        # Subtitle may use a different emoji mode than the message.
        if phase_config.content.emoji_subtitle != phase_config.content.emoji_message:
            subtitle_ctx = build_context(
                review,
                profile,
                phase_name,
                lifecycle,
                emoji_mode=phase_config.content.emoji_subtitle,
                hass=hass,
                global_zone_aliases=global_zone_aliases,
            )
        else:
            subtitle_ctx = ctx
        try:
            subtitle = render_template(hass, subtitle_tpl, subtitle_ctx, cache)
        except TemplateError:
            subtitle = ctx.get("subjects", "")
    else:
        subtitle = str(ctx.get("subjects", ""))

    return RenderedContent(title=title, message=message, subtitle=subtitle)
