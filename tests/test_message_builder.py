"""Tests for the message builder (template rendering and context building)."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import TemplateError
import pytest

from custom_components.frigate_notifications.config import (
    DEFAULT_PHASE_GENAI,
    DEFAULT_PHASE_INITIAL,
    PhaseConfig,
    PhaseContent,
)
from custom_components.frigate_notifications.enums import Lifecycle, Phase
from custom_components.frigate_notifications.message_builder import (
    RenderedContent,
    TemplateCache,
    _format_duration,
    build_context,
    humanize_zone,
    render_notification,
    render_template,
)

from .factories import make_genai, make_profile, make_review


@pytest.mark.parametrize(
    ("input_zone", "expected"),
    [
        ("driveway_approach", "Driveway Approach"),
        ("driveway", "Driveway"),
        ("", ""),
    ],
)
def test_humanize_zone(input_zone: str, expected: str) -> None:
    assert humanize_zone(input_zone) == expected


class TestTemplateCache:
    def test_get_or_create_caches(self, hass: HomeAssistant) -> None:
        cache = TemplateCache()
        t1 = cache.get_or_create("{{ x }}", hass)
        t2 = cache.get_or_create("{{ x }}", hass)
        assert t1 is t2

    def test_clear_empties_cache(self, hass: HomeAssistant) -> None:
        cache = TemplateCache()
        cache.get_or_create("{{ x }}", hass)
        cache.clear()
        assert len(cache._cache) == 0


class TestRenderTemplate:
    def test_simple_variable(self, hass: HomeAssistant) -> None:
        result = render_template(hass, "{{ object }}", {"object": "Car"})
        assert result == "Car"

    def test_empty_template_returns_empty(self, hass: HomeAssistant) -> None:
        assert render_template(hass, "", {"object": "Car"}) == ""

    def test_invalid_jinja_raises(self, hass: HomeAssistant) -> None:
        with pytest.raises(TemplateError):
            render_template(hass, "{% for x in %}broken{% endfor %}", {})

    def test_custom_cache_used(self, hass: HomeAssistant) -> None:
        cache = TemplateCache()
        render_template(hass, "{{ x }}", {"x": "val"}, cache)
        assert "{{ x }}" in cache._cache


class TestBuildContextTier1:
    def test_raw_variables(self) -> None:
        """All tier-1 raw variables are set correctly."""
        review = make_review(
            objects=["car-verified", "person"],
            sub_labels=["Alice", "Known Vehicle"],
            zones=["driveway_approach", "driveway_main"],
        )
        ctx = build_context(review, make_profile(), Phase.INITIAL, Lifecycle.NEW)
        assert ctx["objects_raw"] == "car-verified, person"
        assert ctx["sub_labels_raw"] == "Alice, Known Vehicle"
        assert ctx["zones_raw"] == "driveway_approach, driveway_main"
        # car + car-verified dedup to car, plus person = 2
        assert ctx["object_count"] == "2"
        # Profile cameras (single default).
        assert ctx["profile_cameras"] == "driveway"
        assert ctx["profile_cameras_name"] == "Driveway"

    def test_profile_cameras_multi(self) -> None:
        """profile_cameras joins multiple cameras."""
        profile = make_profile(cameras=("front_door", "back_yard"))
        ctx = build_context(make_review(), profile, Phase.INITIAL, Lifecycle.NEW)
        assert ctx["profile_cameras"] == "front_door, back_yard"
        assert ctx["profile_cameras_name"] == "Front Door, Back Yard"


class TestBuildContextObjects:
    def test_objects_formatted(self) -> None:
        """Objects are title-cased with -verified stripped."""
        review = make_review(objects=["car-verified", "person"])
        ctx = build_context(review, make_profile(), Phase.INITIAL, Lifecycle.NEW)
        assert ctx["object"] == "Car"
        assert ctx["objects"] == "Car, Person"

    def test_empty_objects(self) -> None:
        review = make_review(objects=[])
        ctx = build_context(review, make_profile(), Phase.INITIAL, Lifecycle.NEW)
        assert ctx["object"] == ""
        assert ctx["objects"] == ""
        assert ctx["emoji"] == ""


class TestBuildContextSubjects:
    def test_subjects_drop_verified(self) -> None:
        """-verified entries are dropped entirely from subjects."""
        review = make_review(objects=["car-verified", "person"], sub_labels=[])
        ctx = build_context(review, make_profile(), Phase.INITIAL, Lifecycle.NEW, emoji_mode=False)
        assert ctx["subject"] == "Person"
        assert ctx["subjects"] == "Person"

        # Dedup: sub_label matching object title-case
        review2 = make_review(objects=["person"], sub_labels=["Person"])
        ctx2 = build_context(
            review2, make_profile(), Phase.INITIAL, Lifecycle.NEW, emoji_mode=False
        )
        assert ctx2["subjects"] == "Person"

    def test_subjects_merge_with_sub_labels(self) -> None:
        review = make_review(objects=["car", "person"], sub_labels=["Alice"])
        ctx = build_context(review, make_profile(), Phase.INITIAL, Lifecycle.NEW, emoji_mode=False)
        # Sub-labels come first, then non-verified objects
        assert "Alice" in ctx["subjects"]
        assert "Car" in ctx["subjects"]
        assert "Person" in ctx["subjects"]

    def test_subjects_with_emoji(self) -> None:
        review = make_review(objects=["car"], sub_labels=[])
        profile = make_profile(emoji_map={"car": "\U0001f698"})
        ctx = build_context(review, profile, Phase.INITIAL, Lifecycle.NEW, emoji_mode=True)
        assert "\U0001f698" in ctx["subject"]
        assert "Car" in ctx["subject"]

    def test_subjects_emoji_sublabel_override(self) -> None:
        """sub_label_overrides provides emoji for sublabel items."""
        review = make_review(objects=["person"], sub_labels=["Alice"])
        profile = make_profile(
            sub_label_overrides={"Alice": "\U0001f467"},
            emoji_map={"person": "\U0001f464"},
        )
        ctx = build_context(review, profile, Phase.INITIAL, Lifecycle.NEW, emoji_mode=True)
        assert "\U0001f467 Alice" in ctx["subjects"]
        assert "\U0001f464 Person" in ctx["subjects"]

    def test_subjects_emoji_sublabel_override_priority(self) -> None:
        """sub_label_overrides wins over emoji_map for the same key."""
        review = make_review(objects=[], sub_labels=["amazon"])
        profile = make_profile(
            sub_label_overrides={"amazon": "\U0001f4e6"},
            emoji_map={"amazon": "\U0001f6d2"},
        )
        ctx = build_context(review, profile, Phase.INITIAL, Lifecycle.NEW, emoji_mode=True)
        assert "\U0001f4e6 amazon" in ctx["subjects"]

    def test_added_subject_delta(self) -> None:
        review = make_review(
            objects=["car", "person"],
            before_objects=["car"],
            sub_labels=[],
            before_sub_labels=[],
        )
        ctx = build_context(review, make_profile(), Phase.INITIAL, Lifecycle.NEW, emoji_mode=False)
        assert ctx["added_subject"] == "Person"


class TestBuildContextZones:
    def test_zone_context_variables(self) -> None:
        """Zone-derived variables: humanized names, first/last zone."""
        review = make_review(zones=["a", "b", "c"])
        ctx = build_context(review, make_profile(), Phase.INITIAL, Lifecycle.NEW)
        assert ctx["zone"] == "a"
        assert ctx["zone_name"] == "A"
        assert ctx["first_zone"] == "a"
        assert ctx["last_zone"] == "c"
        assert ctx["first_zone_name"] == "A"
        assert ctx["last_zone_name"] == "C"
        assert "A" in ctx["zones"]
        assert "C" in ctx["zones"]

    def test_empty_zones(self) -> None:
        review = make_review(zones=[])
        ctx = build_context(review, make_profile(), Phase.INITIAL, Lifecycle.NEW)
        assert ctx["zone"] == ""
        assert ctx["zone_name"] == ""
        assert ctx["zone_phrase"] == "detected"

    def test_zone_alias_with_and_without_override(self) -> None:
        """Zone alias uses override when available, else humanized name."""
        review = make_review(zones=["front_yard"])
        profile_with = make_profile(zone_aliases={"front_yard": "Front"})
        ctx_with = build_context(review, profile_with, Phase.INITIAL, Lifecycle.NEW)
        assert ctx_with["zone_alias"] == "Front"

        review2 = make_review(zones=["back_yard"])
        ctx_without = build_context(review2, make_profile(), Phase.INITIAL, Lifecycle.NEW)
        assert ctx_without["zone_alias"] == "Back Yard"

    def test_zone_alias_resolves_per_review_camera_multi_camera(self) -> None:
        """Multi-camera profile resolves zone alias from global map using review.camera."""
        review = make_review(camera="driveway", zones=["front_yard"])
        profile = make_profile(cameras=("driveway", "backyard"), zone_aliases={})
        global_aliases = {
            "driveway": {"front_yard": "Front"},
            "backyard": {"patio": "Patio Area"},
        }
        ctx = build_context(
            review, profile, Phase.INITIAL, Lifecycle.NEW, global_zone_aliases=global_aliases
        )
        assert ctx["zone_alias"] == "Front"

        # Same profile, different camera's review uses that camera's aliases.
        review2 = make_review(camera="backyard", zones=["patio"])
        ctx2 = build_context(
            review2, profile, Phase.INITIAL, Lifecycle.NEW, global_zone_aliases=global_aliases
        )
        assert ctx2["zone_alias"] == "Patio Area"

    def test_zone_phrase(self, hass: HomeAssistant) -> None:
        """Default phrase is 'detected'; Jinja override renders with context."""
        review = make_review(zones=["driveway_approach"])
        ctx_default = build_context(review, make_profile(), Phase.INITIAL, Lifecycle.NEW)
        assert ctx_default["zone_phrase"] == "detected"

        review2 = make_review(zones=["front_yard"])
        profile = make_profile(zone_overrides={"front_yard": "spotted near {{ zone_name }}"})
        ctx_override = build_context(review2, profile, Phase.INITIAL, Lifecycle.NEW, hass=hass)
        assert ctx_override["zone_phrase"] == "spotted near Front Yard"

    def test_added_zones_delta(self) -> None:
        review = make_review(
            zones=["front_yard", "back_yard"],
            before_zones=["front_yard"],
        )
        ctx = build_context(review, make_profile(), Phase.INITIAL, Lifecycle.NEW)
        assert ctx["added_zones"] == "Back Yard"


class TestBuildContextPhaseLifecycle:
    def test_phase_and_lifecycle_separate(self) -> None:
        review = make_review()
        ctx = build_context(review, make_profile(), Phase.INITIAL, Lifecycle.UPDATE)
        assert ctx["phase"] == "initial"
        assert ctx["lifecycle"] == "update"

    def test_phase_boolean_flags(self) -> None:
        """All is_* phase flags are set correctly."""
        ctx_initial = build_context(make_review(), make_profile(), Phase.INITIAL, Lifecycle.NEW)
        assert ctx_initial["is_initial"] is True
        assert ctx_initial["is_update"] is False
        assert ctx_initial["is_genai"] is False

        ctx_genai = build_context(make_review(), make_profile(), Phase.GENAI, Lifecycle.GENAI)
        assert ctx_genai["is_genai"] is True
        assert ctx_genai["is_initial"] is False

    def test_phase_emoji_all_phases(self) -> None:
        """Each phase maps to its default emoji."""
        expected = {
            Phase.INITIAL: "\U0001f195",
            Phase.UPDATE: "\U0001f504",
            Phase.END: "\U0001f51a",
            Phase.GENAI: "\u2728",
        }
        for phase, emoji in expected.items():
            ctx = build_context(make_review(), make_profile(), phase, Lifecycle.NEW)
            assert ctx["phase_emoji"] == emoji, f"Failed for {phase}"

    def test_phase_emoji_custom_map(self) -> None:
        """Custom phase_emoji_map on profile flows through to context."""
        custom = {"initial": "A", "update": "B", "end": "C", "genai": "D"}
        profile = make_profile(phase_emoji_map=custom)
        ctx = build_context(make_review(), profile, Phase.INITIAL, Lifecycle.NEW)
        assert ctx["phase_emoji"] == "A"
        ctx_end = build_context(make_review(), profile, Phase.END, Lifecycle.END)
        assert ctx_end["phase_emoji"] == "C"


class TestBuildContextGenAI:
    def test_genai_fields_populated(self) -> None:
        genai = make_genai(
            title="Person on Porch",
            short_summary="A person approached the front porch.",
            confidence=0.95,
            threat_level=2,
            other_concerns=("Dog nearby",),
        )
        review = make_review(genai=genai)
        ctx = build_context(review, make_profile(), Phase.GENAI, Lifecycle.GENAI)
        assert ctx["genai_title"] == "Person on Porch"
        assert ctx["genai_summary"] == "A person approached the front porch."
        assert ctx["genai_confidence"] == "0.95"
        assert ctx["genai_threat_level"] == "2"
        assert ctx["genai_concerns"] == "Dog nearby"

    def test_genai_fields_empty_when_none(self) -> None:
        review = make_review(genai=None)
        ctx = build_context(review, make_profile(), Phase.INITIAL, Lifecycle.NEW)
        assert ctx["genai_title"] == ""
        assert ctx["genai_summary"] == ""
        assert ctx["genai_confidence"] == ""


class TestBuildContextIDs:
    def test_detection_id_resolution(self) -> None:
        """First detection_id used; falls back to review_id when empty."""
        review = make_review(detection_ids=["det1", "det2"])
        ctx = build_context(review, make_profile(), Phase.INITIAL, Lifecycle.NEW)
        assert ctx["detection_id"] == "det1"
        assert ctx["detection_ids"] == "det1, det2"
        assert ctx["detection_count"] == "2"

        review_empty = make_review(detection_ids=[])
        ctx_empty = build_context(review_empty, make_profile(), Phase.INITIAL, Lifecycle.NEW)
        assert ctx_empty["detection_id"] == review_empty.review_id
        assert ctx_empty["detection_ids"] == ""
        assert ctx_empty["detection_count"] == "0"

    def test_url_and_id_context(self) -> None:
        """URLs, client_id, and latest_detection_id appear in context."""
        profile = make_profile(
            base_url="https://ha.local",
            frigate_url="https://frigate.local",
            client_id="/my-instance",
        )
        review = make_review(latest_detection_id="latest_det")
        ctx = build_context(review, profile, Phase.INITIAL, Lifecycle.NEW)
        assert ctx["base_url"] == "https://ha.local"
        assert ctx["frigate_url"] == "https://frigate.local"
        assert ctx["client_id"] == "/my-instance"
        assert ctx["latest_detection_id"] == "latest_det"


class TestFormatDuration:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (0, "0s"),
            (45, "45s"),
            (60, "1m"),
            (154, "2m 34s"),
            (3600, "60m"),
        ],
    )
    def test_format_duration(self, seconds: int, expected: str) -> None:
        assert _format_duration(seconds) == expected


class TestBuildContextTime:
    def test_time_and_camera_context(self) -> None:
        """Time fields present; camera name humanized."""
        review = make_review(camera="front_door")
        ctx = build_context(review, make_profile(), Phase.INITIAL, Lifecycle.NEW)
        assert ctx["time"]
        assert ctx["time_24hr"]
        assert ctx["camera_name"] == "Front Door"
        assert ctx["camera"] == "front_door"

    def test_duration_context(self) -> None:
        """Duration calculated when end_time present; empty otherwise."""
        review_with = make_review(start_time=100.0, end_time=145.0)
        ctx_with = build_context(review_with, make_profile(), Phase.END, Lifecycle.END)
        assert ctx_with["duration"] == "45"
        assert ctx_with["duration_human"] == "45s"

        review_without = make_review(end_time=None)
        ctx_without = build_context(review_without, make_profile(), Phase.INITIAL, Lifecycle.NEW)
        assert ctx_without["duration"] == ""
        assert ctx_without["duration_human"] == ""


class TestRenderNotification:
    def test_basic_render(self, hass: HomeAssistant) -> None:
        review = make_review(objects=["person"], zones=["driveway_approach"])
        profile = make_profile()
        result = render_notification(
            hass, profile, review, Phase.INITIAL, DEFAULT_PHASE_INITIAL, Lifecycle.NEW
        )
        assert isinstance(result, RenderedContent)
        assert result.message
        assert result.title

    def test_phase_title_overrides_profile(self, hass: HomeAssistant) -> None:
        phase = PhaseConfig(
            content=PhaseContent(
                title_template="Custom: {{ camera_name }}",
                message_template="{{ object }}",
            )
        )
        review = make_review(camera="garage")
        result = render_notification(
            hass, make_profile(), review, Phase.INITIAL, phase, Lifecycle.NEW
        )
        assert result.title == "Custom: Garage"

    def test_empty_phase_title_falls_back_to_profile(self, hass: HomeAssistant) -> None:
        phase = PhaseConfig(
            content=PhaseContent(
                title_template="",
                message_template="{{ object }}",
            )
        )
        result = render_notification(
            hass, make_profile(), make_review(), Phase.INITIAL, phase, Lifecycle.NEW
        )
        assert result.title

    def test_subtitle_from_template(self, hass: HomeAssistant) -> None:
        phase = PhaseConfig(
            content=PhaseContent(
                message_template="{{ object }}",
                subtitle_template="{{ camera_name }}",
            )
        )
        review = make_review(camera="garage")
        result = render_notification(
            hass, make_profile(), review, Phase.INITIAL, phase, Lifecycle.NEW
        )
        assert result.subtitle == "Garage"

    def test_empty_subtitle_falls_back_to_subjects(self, hass: HomeAssistant) -> None:
        phase = PhaseConfig(
            content=PhaseContent(
                message_template="{{ object }}",
                subtitle_template="",
            )
        )
        review = make_review(objects=["person"])
        result = render_notification(
            hass, make_profile(), review, Phase.INITIAL, phase, Lifecycle.NEW
        )
        assert "Person" in result.subtitle

    def test_genai_phase_render(self, hass: HomeAssistant, template_id_map: dict[str, str]) -> None:
        review = make_review(genai=make_genai(short_summary="A person on the porch."))
        result = render_notification(
            hass,
            make_profile(),
            review,
            Phase.GENAI,
            DEFAULT_PHASE_GENAI,
            Lifecycle.GENAI,
            template_id_map=template_id_map,
        )
        assert result.message == "A person on the porch."

    def test_emoji_in_message_controlled_by_phase(self, hass: HomeAssistant) -> None:
        """emoji_message=True means subjects in context have emoji."""
        phase_emoji = PhaseConfig(
            content=PhaseContent(
                message_template="{{ subjects }}",
                emoji_message=True,
            )
        )
        phase_no_emoji = PhaseConfig(
            content=PhaseContent(
                message_template="{{ subjects }}",
                emoji_message=False,
            )
        )
        review = make_review(objects=["person"])
        profile = make_profile(emoji_map={"person": "\U0001f464"})

        with_emoji = render_notification(
            hass, profile, review, Phase.INITIAL, phase_emoji, Lifecycle.NEW
        )
        without_emoji = render_notification(
            hass, profile, review, Phase.INITIAL, phase_no_emoji, Lifecycle.NEW
        )
        assert "\U0001f464" in with_emoji.message
        assert "\U0001f464" not in without_emoji.message

    def test_subtitle_emoji_differs_from_message(self, hass: HomeAssistant) -> None:
        """emoji_subtitle=True with emoji_message=False rebuilds context for subtitle."""
        phase = PhaseConfig(
            content=PhaseContent(
                message_template="{{ subjects }}",
                subtitle_template="{{ subjects }}",
                emoji_message=False,
                emoji_subtitle=True,
            )
        )
        review = make_review(objects=["person"])
        profile = make_profile(emoji_map={"person": "\U0001f464"})
        result = render_notification(hass, profile, review, Phase.INITIAL, phase, Lifecycle.NEW)
        assert "\U0001f464" not in result.message
        assert "\U0001f464" in result.subtitle

    @pytest.mark.parametrize(
        ("field", "phase_kwargs"),
        [
            ("message", {"message_template": "{% for x in %}broken{% endfor %}"}),
            (
                "title",
                {
                    "title_template": "{% for x in %}broken{% endfor %}",
                    "message_template": "{{ object }}",
                },
            ),
        ],
        ids=["message", "title"],
    )
    def test_render_error_falls_back_to_raw(
        self, hass: HomeAssistant, field: str, phase_kwargs: dict
    ) -> None:
        """TemplateError falls back to raw template for message or title."""
        phase = PhaseConfig(content=PhaseContent(**phase_kwargs))
        result = render_notification(
            hass, make_profile(), make_review(), Phase.INITIAL, phase, Lifecycle.NEW
        )
        assert getattr(result, field) == "{% for x in %}broken{% endfor %}"

    def test_subtitle_render_error_falls_back_to_subjects(self, hass: HomeAssistant) -> None:
        """Broken subtitle template falls back to subjects string."""
        phase = PhaseConfig(
            content=PhaseContent(
                message_template="{{ object }}",
                subtitle_template="{% for x in %}broken{% endfor %}",
            )
        )
        review = make_review(objects=["person"])
        result = render_notification(
            hass, make_profile(), review, Phase.INITIAL, phase, Lifecycle.NEW
        )
        assert "Person" in result.subtitle

    def test_id_based_phase_config_renders_via_id_map(
        self, hass: HomeAssistant, template_id_map: dict[str, str]
    ) -> None:
        """PhaseConfig using template IDs renders correctly when template_id_map is passed."""
        phase = PhaseConfig(
            content=PhaseContent(
                message_template="object_action_zone",
                subtitle_template="merged_subjects",
            )
        )
        review = make_review(objects=["person"], zones=["front_yard"])
        result = render_notification(
            hass,
            make_profile(),
            review,
            Phase.INITIAL,
            phase,
            Lifecycle.NEW,
            template_id_map=template_id_map,
        )
        assert "Person" in result.message
        assert "Front Yard" in result.message
        assert "Person" in result.subtitle

    def test_id_passthrough_for_raw_jinja(self, hass: HomeAssistant) -> None:
        """Raw Jinja passes through unchanged when not found in ID map."""
        phase = PhaseConfig(
            content=PhaseContent(
                message_template="{{ camera_name }} custom",
            )
        )
        review = make_review(camera="garage")
        result = render_notification(
            hass,
            make_profile(),
            review,
            Phase.INITIAL,
            phase,
            Lifecycle.NEW,
            template_id_map={"object_action_zone": "{{ object }}"},
        )
        assert result.message == "Garage custom"

    def test_zone_override_render_error_falls_back_to_detected(self, hass: HomeAssistant) -> None:
        """Broken zone_override Jinja template falls back to 'detected'."""
        review = make_review(zones=["front_yard"])
        profile = make_profile(zone_overrides={"front_yard": "{% for x in %}broken{% endfor %}"})
        ctx = build_context(review, profile, Phase.INITIAL, Lifecycle.NEW, hass=hass)
        assert ctx["zone_phrase"] == "detected"
