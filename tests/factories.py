"""Factory functions for building test fixtures.

Factories use dataclasses.replace() for variations on frozen dataclasses
and direct construction with deep-copied lists for mutable dataclasses.
"""

import copy
from dataclasses import replace
from typing import Any

from custom_components.frigate_notifications.config import DEFAULT_PHASE_INITIAL, PhaseConfig
from custom_components.frigate_notifications.const import (
    DEFAULT_EMOJI,
    DEFAULT_GROUP,
    DEFAULT_PHASE_EMOJI_MAP,
    DEFAULT_TAG,
    DEFAULT_TITLE_GENAI_PREFIXES,
    DEFAULT_TITLE_TEMPLATE,
)
from custom_components.frigate_notifications.data import ProfileRuntime, RuntimeConfig
from custom_components.frigate_notifications.dispatcher import DispatchRequest
from custom_components.frigate_notifications.enums import (
    GuardMode,
    Lifecycle,
    Phase,
    Provider,
    RecognitionMode,
    Severity,
    TimeFilterMode,
    ZoneMatchMode,
)
from custom_components.frigate_notifications.filters import FilterContext
from custom_components.frigate_notifications.media import DEFAULT_GIF_URL, DEFAULT_SNAPSHOT_URL
from custom_components.frigate_notifications.message_builder import TemplateCache
from custom_components.frigate_notifications.models import (
    GenAIData,
    ProfileState,
    Review,
    ReviewState,
)
from custom_components.frigate_notifications.providers.models import MobileAppConfig

_MUTABLE_LIST_FIELDS = (
    "detection_ids",
    "objects",
    "sub_labels",
    "zones",
    "before_zones",
    "before_objects",
    "before_sub_labels",
)


def make_review(**overrides: Any) -> Review:
    """Create a Review with sensible defaults.

    List fields are deep-copied to ensure independence between instances.
    """
    defaults: dict[str, Any] = {
        "review_id": "1773840946.10543-review1",
        "camera": "driveway",
        "start_time": 1773840946.10543,
        "end_time": None,
        "severity": "alert",
        "detection_ids": ["det_id_1"],
        "objects": ["person"],
        "sub_labels": [],
        "zones": ["driveway_approach"],
        "latest_detection_id": "det_id_1",
        "before_zones": [],
        "before_objects": [],
        "before_sub_labels": [],
        "genai": None,
        "last_update": 0.0,
    }
    merged = {**defaults, **overrides}
    for key in _MUTABLE_LIST_FIELDS:
        if key in merged and isinstance(merged[key], list):
            merged[key] = copy.copy(merged[key])
    return Review(**merged)


def make_genai(**overrides: Any) -> GenAIData:
    """Create a GenAIData with sensible defaults."""
    defaults = GenAIData(
        title="Person and Vehicle in Driveway",
        short_summary="A person walked up the driveway as a car pulled in.",
        scene="A person walks up the driveway approach.",
        confidence=0.92,
        threat_level=1,
        other_concerns=("Vehicle speed appears normal",),
        time="Wednesday, 09:35 AM",
    )
    if not overrides:
        return defaults
    return replace(defaults, **overrides)


def make_phase(**overrides: Any) -> PhaseConfig:
    """Create a PhaseConfig with sensible defaults (composed sub-configs)."""
    defaults = PhaseConfig()
    if not overrides:
        return defaults
    return replace(defaults, **overrides)


def make_profile(**overrides: Any) -> ProfileRuntime:
    """Build a ProfileRuntime with sensible defaults.

    All enum-typed fields use enums. Filtering fields use permissive defaults
    so tests only override what they're testing.
    """
    defaults: dict[str, Any] = {
        "entry_id": "test_entry_id",
        "profile_id": "test_profile_id",
        "name": "Test Profile",
        "cameras": ("driveway",),
        "provider": Provider.APPLE,
        "notify_target": "notify.mobile_app_test_phone",
        "objects": (),
        "severity": Severity.ANY,
        "guard_mode": GuardMode.DISABLED,
        "guard_entity": None,
        "required_zones": (),
        "zone_match_mode": ZoneMatchMode.ANY,
        "cooldown_seconds": 0,
        "time_filter_mode": TimeFilterMode.DISABLED,
        "time_filter_start": "",
        "time_filter_end": "",
        "presence_entities": (),
        "state_entity": None,
        "state_filter_states": (),
        "recognition_mode": RecognitionMode.DISABLED,
        "required_sub_labels": (),
        "excluded_sub_labels": (),
        "title_template": DEFAULT_TITLE_TEMPLATE,
        "zone_overrides": {},
        "zone_aliases": {},
        "sub_label_overrides": {},
        "emoji_map": {},
        "default_emoji": DEFAULT_EMOJI,
        "phase_emoji_map": dict(DEFAULT_PHASE_EMOJI_MAP),
        "title_genai_prefixes": dict(DEFAULT_TITLE_GENAI_PREFIXES),
        "phases": {},
        "silence_duration": 30,
        "alert_once": False,
        "tag": DEFAULT_TAG,
        "group": DEFAULT_GROUP,
        "base_url": "https://hass.test",
        "snapshot_url": DEFAULT_SNAPSHOT_URL,
        "gif_url": DEFAULT_GIF_URL,
        "provider_config": MobileAppConfig(),
        "action_config": (
            {"preset": "view_clip"},
            {"preset": "view_snapshot"},
            {"preset": "silence"},
        ),
        "tap_action": {"preset": "view_clip"},
        "on_button_action": (),
        "frigate_url": "",
        "client_id": "",
    }
    merged = {**defaults, **overrides}
    return ProfileRuntime(**merged)


def make_filter_context(
    hass: Any = None,
    profile: ProfileRuntime | None = None,
    review: Review | None = None,
    lifecycle: Lifecycle = Lifecycle.NEW,
    review_state: ReviewState | None = None,
    profile_state: ProfileState | None = None,
) -> FilterContext:
    """Build a FilterContext with sensible defaults."""
    return FilterContext(
        profile=profile or make_profile(),
        review=review or make_review(),
        lifecycle=lifecycle,
        review_state=review_state or ReviewState(),
        profile_state=profile_state or ProfileState(),
        hass=hass,
    )


def make_runtime(
    profiles: dict[str, list[ProfileRuntime]] | list[ProfileRuntime] | None = None,
    initial_delay: float = 0.0,
    template_id_map: dict[str, str] | None = None,
) -> RuntimeConfig:
    """Build a RuntimeConfig from profile dict or list."""
    if profiles is None:
        resolved: dict[str, list[ProfileRuntime]] = {}
    elif isinstance(profiles, list):
        resolved = {}
        for p in profiles:
            for cam in p.cameras:
                resolved.setdefault(cam, []).append(p)
    else:
        resolved = profiles
    return RuntimeConfig(
        profiles=resolved,
        initial_delay=initial_delay,
        template_id_map=template_id_map or {},
    )


def make_dispatch_request(
    hass: Any,
    *,
    profile: ProfileRuntime | None = None,
    review: Review | None = None,
    phase: Phase = Phase.INITIAL,
    phase_config: PhaseConfig | None = None,
    lifecycle: Lifecycle = Lifecycle.NEW,
    is_genai: bool = False,
    is_initial: bool = True,
    review_state: ReviewState | None = None,
    template_cache: TemplateCache | None = None,
    global_zone_aliases: dict[str, dict[str, str]] | None = None,
    template_id_map: dict[str, str] | None = None,
) -> DispatchRequest:
    """Build a DispatchRequest with sensible defaults."""
    return DispatchRequest(
        hass=hass,
        profile=profile or make_profile(),
        review=review or make_review(),
        phase=phase,
        phase_config=phase_config or DEFAULT_PHASE_INITIAL,
        lifecycle=lifecycle,
        is_genai=is_genai,
        is_initial=is_initial,
        review_state=review_state or ReviewState(),
        template_cache=template_cache or TemplateCache(),
        global_zone_aliases=global_zone_aliases or {},
        template_id_map=template_id_map or {},
    )
