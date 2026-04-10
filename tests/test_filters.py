"""Tests for the notification filter chain."""

from datetime import UTC, datetime, timedelta
import time
from unittest.mock import patch

from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
import pytest

from custom_components.frigate_notifications.enums import (
    Lifecycle,
    RecognitionMode,
    Severity,
    TimeFilterMode,
    ZoneMatchMode,
)
from custom_components.frigate_notifications.filters import (
    CooldownFilter,
    FilterChain,
    FilterContext,
    FilterResult,
    GuardEntityFilter,
    ObjectFilter,
    PresenceFilter,
    SeverityFilter,
    SilenceFilter,
    StateFilter,
    SubLabelFilter,
    SwitchEnabledFilter,
    TimeFilter,
    ZoneFilter,
    build_default_filter_chain,
)
from custom_components.frigate_notifications.models import ProfileState

from .factories import make_filter_context, make_profile, make_review


class TestSeverityFilter:
    def test_any_passes_all(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(hass=hass, profile=make_profile(severity=Severity.ANY))
        assert SeverityFilter().check(ctx).passed is True

    def test_matching_severity_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(severity=Severity.ALERT),
            review=make_review(severity="alert"),
        )
        assert SeverityFilter().check(ctx).passed is True

    def test_mismatched_severity_rejects(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(severity=Severity.ALERT),
            review=make_review(severity="detection"),
        )
        result = SeverityFilter().check(ctx)
        assert result.passed is False
        assert result.filter_name == "severity"


class TestObjectFilter:
    def test_empty_objects_passes_all(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(hass=hass, profile=make_profile(objects=()))
        assert ObjectFilter().check(ctx).passed is True

    def test_matching_object_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(objects=("person",)),
            review=make_review(objects=["person"]),
        )
        assert ObjectFilter().check(ctx).passed is True

    def test_verified_suffix_stripped(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(objects=("car",)),
            review=make_review(objects=["car-verified"]),
        )
        assert ObjectFilter().check(ctx).passed is True

    def test_no_overlap_rejects(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(objects=("dog",)),
            review=make_review(objects=["person"]),
        )
        result = ObjectFilter().check(ctx)
        assert result.passed is False
        assert result.filter_name == "object"


class TestSubLabelFilter:
    """Tests for SubLabelFilter."""

    def test_disabled_mode_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(recognition_mode=RecognitionMode.DISABLED),
        )
        assert SubLabelFilter().check(ctx).passed is True

    def test_require_recognized_rejects_no_verified(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(recognition_mode=RecognitionMode.REQUIRE_RECOGNIZED),
            review=make_review(objects=["person"]),
        )
        result = SubLabelFilter().check(ctx)
        assert result.passed is False
        assert result.filter_name == "sub_label"

    def test_require_recognized_passes_with_verified(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(recognition_mode=RecognitionMode.REQUIRE_RECOGNIZED),
            review=make_review(objects=["person-verified"]),
        )
        assert SubLabelFilter().check(ctx).passed is True

    def test_require_recognized_with_include_rejects_no_match(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(
                recognition_mode=RecognitionMode.REQUIRE_RECOGNIZED,
                required_sub_labels=("Alice",),
            ),
            review=make_review(objects=["person-verified"], sub_labels=["Bob"]),
        )
        result = SubLabelFilter().check(ctx)
        assert result.passed is False

    def test_require_recognized_with_include_passes_on_match(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(
                recognition_mode=RecognitionMode.REQUIRE_RECOGNIZED,
                required_sub_labels=("Alice",),
            ),
            review=make_review(objects=["person-verified"], sub_labels=["Alice"]),
        )
        assert SubLabelFilter().check(ctx).passed is True

    def test_exclude_sub_labels_rejects_matched(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(
                recognition_mode=RecognitionMode.EXCLUDE_SUB_LABELS,
                excluded_sub_labels=("Alice",),
            ),
            review=make_review(sub_labels=["Alice"]),
        )
        result = SubLabelFilter().check(ctx)
        assert result.passed is False
        assert result.filter_name == "sub_label"

    def test_exclude_sub_labels_passes_no_match(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(
                recognition_mode=RecognitionMode.EXCLUDE_SUB_LABELS,
                excluded_sub_labels=("Alice",),
            ),
            review=make_review(sub_labels=["Bob"]),
        )
        assert SubLabelFilter().check(ctx).passed is True

    def test_exclude_empty_list_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(
                recognition_mode=RecognitionMode.EXCLUDE_SUB_LABELS,
                excluded_sub_labels=(),
            ),
            review=make_review(sub_labels=["Alice"]),
        )
        assert SubLabelFilter().check(ctx).passed is True

    def test_case_insensitive_matching(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(
                recognition_mode=RecognitionMode.REQUIRE_RECOGNIZED,
                required_sub_labels=("alice",),
            ),
            review=make_review(objects=["person-verified"], sub_labels=["Alice"]),
        )
        assert SubLabelFilter().check(ctx).passed is True


class TestZoneFilter:
    def test_multi_camera_skips_zone_filter(self, hass: HomeAssistant) -> None:
        """Multi-camera profile bypasses zone filtering entirely."""
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(
                cameras=("driveway", "backyard"),
                required_zones=("front_yard",),
            ),
            review=make_review(zones=[]),
        )
        assert ZoneFilter().check(ctx).passed is True

    def test_empty_required_zones_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(hass=hass, profile=make_profile(required_zones=()))
        assert ZoneFilter().check(ctx).passed is True

    def test_no_actual_zones_rejects(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(required_zones=("front_yard",)),
            review=make_review(zones=[]),
        )
        result = ZoneFilter().check(ctx)
        assert result.passed is False
        assert result.filter_name == "zone"

    @pytest.mark.parametrize(
        ("mode", "required", "actual", "expected"),
        [
            (ZoneMatchMode.ANY, ("front_yard", "back_yard"), ["front_yard"], True),
            (ZoneMatchMode.ANY, ("front_yard",), ["back_yard"], False),
            (ZoneMatchMode.ALL, ("a", "b"), ["a", "b", "c"], True),
            (ZoneMatchMode.ALL, ("a", "b"), ["a"], False),
            (ZoneMatchMode.ORDERED, ("a", "c"), ["a", "b", "c"], True),
            (ZoneMatchMode.ORDERED, ("a", "b"), ["b", "a"], False),
            (ZoneMatchMode.ORDERED, ("a", "c", "b"), ["a", "b", "c"], False),
        ],
        ids=[
            "any-overlap-passes",
            "any-no-overlap-rejects",
            "all-subset-passes",
            "all-missing-rejects",
            "ordered-correct-passes",
            "ordered-wrong-first-rejects",
            "ordered-wrong-order-rejects",
        ],
    )
    def test_zone_match_modes(
        self,
        mode: ZoneMatchMode,
        required: tuple[str, ...],
        actual: list[str],
        expected: bool,
        hass: HomeAssistant,
    ) -> None:
        """Zone filter evaluates match modes correctly."""
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(required_zones=required, zone_match_mode=mode),
            review=make_review(zones=actual),
        )
        assert ZoneFilter().check(ctx).passed is expected


class TestTimeFilter:
    def test_disabled_mode_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(time_filter_mode=TimeFilterMode.DISABLED),
        )
        assert TimeFilter().check(ctx).passed is True

    def test_empty_start_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(
                time_filter_mode=TimeFilterMode.ONLY_DURING,
                time_filter_start="",
                time_filter_end="18:00",
            ),
        )
        assert TimeFilter().check(ctx).passed is True

    @pytest.mark.parametrize(
        ("mode", "start", "end", "now_dt", "expected"),
        [
            (
                TimeFilterMode.ONLY_DURING,
                "08:00",
                "18:00",
                datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
                True,
            ),
            (
                TimeFilterMode.ONLY_DURING,
                "08:00",
                "18:00",
                datetime(2026, 1, 1, 20, 0, tzinfo=UTC),
                False,
            ),
            (
                TimeFilterMode.NOT_DURING,
                "22:00",
                "06:00",
                datetime(2026, 1, 1, 23, 0, tzinfo=UTC),
                False,
            ),
            (
                TimeFilterMode.ONLY_DURING,
                "22:00",
                "06:00",
                datetime(2026, 1, 1, 23, 30, tzinfo=UTC),
                True,
            ),
            (
                TimeFilterMode.ONLY_DURING,
                "22:00",
                "06:00",
                datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
                False,
            ),
        ],
        ids=[
            "only-during-inside-passes",
            "only-during-outside-rejects",
            "not-during-inside-rejects",
            "overnight-inside-passes",
            "overnight-outside-rejects",
        ],
    )
    def test_time_window_filtering(
        self,
        mode: TimeFilterMode,
        start: str,
        end: str,
        now_dt: datetime,
        expected: bool,
        hass: HomeAssistant,
    ) -> None:
        """Time filter evaluates window boundaries correctly."""
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(
                time_filter_mode=mode,
                time_filter_start=start,
                time_filter_end=end,
            ),
        )
        with patch(
            "custom_components.frigate_notifications.filters.dt_util.now",
            return_value=now_dt,
        ):
            assert TimeFilter().check(ctx).passed is expected

    def test_invalid_times_pass_with_warning(
        self, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
    ) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(
                time_filter_mode=TimeFilterMode.ONLY_DURING,
                time_filter_start="not-a-time",
                time_filter_end="also-bad",
            ),
        )
        assert TimeFilter().check(ctx).passed is True
        assert "Invalid time filter" in caplog.text


class TestStateFilter:
    def test_no_entity_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(state_entity=None),
        )
        assert StateFilter().check(ctx).passed is True

    def test_no_allowed_states_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(state_entity="input_select.mode", state_filter_states=()),
        )
        assert StateFilter().check(ctx).passed is True

    def test_matching_state_passes(self, hass: HomeAssistant) -> None:
        hass.states.async_set("input_select.mode", "armed")
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(
                state_entity="input_select.mode",
                state_filter_states=("armed", "away"),
            ),
        )
        assert StateFilter().check(ctx).passed is True

    def test_non_matching_state_rejects(self, hass: HomeAssistant) -> None:
        hass.states.async_set("input_select.mode", "disarmed")
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(
                state_entity="input_select.mode",
                state_filter_states=("armed",),
            ),
        )
        result = StateFilter().check(ctx)
        assert result.passed is False
        assert result.filter_name == "state"

    def test_missing_entity_rejects(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(
                state_entity="input_select.nonexistent",
                state_filter_states=("armed",),
            ),
        )
        result = StateFilter().check(ctx)
        assert result.passed is False
        assert "unavailable" in result.reason


class TestPresenceFilter:
    def test_no_presence_entities_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(hass=hass, profile=make_profile(presence_entities=()))
        assert PresenceFilter().check(ctx).passed is True

    def test_nobody_home_passes(self, hass: HomeAssistant) -> None:
        hass.states.async_set("person.alice", STATE_NOT_HOME)
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(presence_entities=("person.alice",)),
        )
        assert PresenceFilter().check(ctx).passed is True

    def test_someone_home_rejects(self, hass: HomeAssistant) -> None:
        hass.states.async_set("person.alice", STATE_HOME)
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(presence_entities=("person.alice",)),
        )
        result = PresenceFilter().check(ctx)
        assert result.passed is False
        assert result.filter_name == "presence"


class _FakeEntity:
    """Minimal stand-in for an entity, providing entity_id."""

    def __init__(self, entity_id: str) -> None:
        self.entity_id = entity_id


class _StaticRejectFilter:
    """Filter with runtime_recheck=False that always rejects."""

    runtime_recheck = False

    def check(self, ctx: FilterContext) -> FilterResult:
        return FilterResult(passed=False, filter_name="static", reason="always reject")


class TestSilenceFilter:
    def test_no_entity_registered_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(hass=hass)
        assert SilenceFilter().check(ctx).passed is True

    @pytest.mark.parametrize(
        ("state_value", "expected"),
        [
            ((datetime.now(tz=UTC) + timedelta(hours=1)).isoformat(), False),
            ((datetime.now(tz=UTC) - timedelta(hours=1)).isoformat(), True),
            ("unknown", True),
            ("not-a-date", True),
        ],
        ids=["future-rejects", "past-passes", "unknown-passes", "malformed-passes"],
    )
    def test_silence_entity_state(
        self,
        hass: HomeAssistant,
        state_value: str,
        expected: bool,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        entity_id = "datetime.test_silenced_until"
        fake_entity = _FakeEntity(entity_id)
        fake_runtime = type("R", (), {"silence_datetimes": {"test_profile_id": fake_entity}})()
        fake_entry = type("E", (), {"runtime_data": fake_runtime})()
        hass.states.async_set(entity_id, state_value)
        ctx = make_filter_context(hass=hass)
        with patch(
            "custom_components.frigate_notifications.filters.find_entry_for_profile",
            return_value=fake_entry,
        ):
            result = SilenceFilter().check(ctx)
        assert result.passed is expected
        if not expected:
            assert result.filter_name == "silence"
        # Malformed datetime state should warn.
        if state_value == "not-a-date":
            assert "Malformed silence state" in caplog.text


class TestSwitchEnabledFilter:
    def test_no_switch_registered_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(hass=hass)
        assert SwitchEnabledFilter().check(ctx).passed is True

    def test_switch_on_passes(self, hass: HomeAssistant) -> None:
        entity_id = "switch.test_enabled"
        fake_entity = _FakeEntity(entity_id)
        fake_runtime = type("R", (), {"enabled_switches": {"test_profile_id": fake_entity}})()
        fake_entry = type("E", (), {"runtime_data": fake_runtime})()
        hass.states.async_set(entity_id, STATE_ON)
        ctx = make_filter_context(hass=hass)
        with patch(
            "custom_components.frigate_notifications.filters.find_entry_for_profile",
            return_value=fake_entry,
        ):
            assert SwitchEnabledFilter().check(ctx).passed is True

    def test_switch_off_rejects(self, hass: HomeAssistant) -> None:
        entity_id = "switch.test_enabled"
        fake_entity = _FakeEntity(entity_id)
        fake_runtime = type("R", (), {"enabled_switches": {"test_profile_id": fake_entity}})()
        fake_entry = type("E", (), {"runtime_data": fake_runtime})()
        hass.states.async_set(entity_id, STATE_OFF)
        ctx = make_filter_context(hass=hass)
        with patch(
            "custom_components.frigate_notifications.filters.find_entry_for_profile",
            return_value=fake_entry,
        ):
            result = SwitchEnabledFilter().check(ctx)
        assert result.passed is False
        assert result.filter_name == "switch_enabled"


class TestGuardEntityFilter:
    def test_no_guard_entity_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(hass=hass, profile=make_profile(guard_entity=None))
        assert GuardEntityFilter().check(ctx).passed is True

    def test_guard_on_passes(self, hass: HomeAssistant) -> None:
        hass.states.async_set("input_boolean.guard", STATE_ON)
        ctx = make_filter_context(
            hass=hass, profile=make_profile(guard_entity="input_boolean.guard")
        )
        assert GuardEntityFilter().check(ctx).passed is True

    def test_guard_off_rejects(self, hass: HomeAssistant) -> None:
        hass.states.async_set("input_boolean.guard", STATE_OFF)
        ctx = make_filter_context(
            hass=hass, profile=make_profile(guard_entity="input_boolean.guard")
        )
        result = GuardEntityFilter().check(ctx)
        assert result.passed is False
        assert result.filter_name == "guard_entity"

    def test_guard_missing_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass, profile=make_profile(guard_entity="input_boolean.nonexistent")
        )
        assert GuardEntityFilter().check(ctx).passed is True


class TestCooldownFilter:
    def test_non_new_lifecycle_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(hass=hass, lifecycle=Lifecycle.UPDATE)
        assert CooldownFilter().check(ctx).passed is True

    def test_zero_cooldown_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(cooldown_seconds=0),
        )
        assert CooldownFilter().check(ctx).passed is True

    def test_no_previous_send_passes(self, hass: HomeAssistant) -> None:
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(cooldown_seconds=60),
        )
        assert CooldownFilter().check(ctx).passed is True

    def test_cooldown_active_rejects(self, hass: HomeAssistant) -> None:
        ps = ProfileState(last_sent_at={"driveway": time.time()})
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(cooldown_seconds=60),
            profile_state=ps,
        )
        result = CooldownFilter().check(ctx)
        assert result.passed is False
        assert result.filter_name == "cooldown"

    def test_cooldown_expired_passes(self, hass: HomeAssistant) -> None:
        ps = ProfileState(last_sent_at={"driveway": time.time() - 120})
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(cooldown_seconds=60),
            profile_state=ps,
        )
        assert CooldownFilter().check(ctx).passed is True


class TestFilterChain:
    def test_all_pass_returns_pass(self, hass: HomeAssistant) -> None:
        chain = build_default_filter_chain()
        ctx = make_filter_context(hass=hass)
        result = chain.evaluate(ctx)
        assert result.passed is True

    def test_first_rejection_short_circuits(self, hass: HomeAssistant) -> None:
        chain = build_default_filter_chain()
        ctx = make_filter_context(
            hass=hass,
            profile=make_profile(severity=Severity.ALERT),
            review=make_review(severity="detection"),
        )
        result = chain.evaluate(ctx)
        assert result.passed is False
        assert result.filter_name == "severity"

    def test_empty_chain_passes(self, hass: HomeAssistant) -> None:
        chain = FilterChain([])
        ctx = make_filter_context(hass=hass)
        assert chain.evaluate(ctx).passed is True

    def test_evaluate_runtime_skips_static_filters(self, hass: HomeAssistant) -> None:
        """Static filters (runtime_recheck=False) are not re-run by evaluate_runtime."""
        chain = FilterChain([_StaticRejectFilter()])
        ctx = make_filter_context(hass=hass)
        # evaluate() should reject (static filter runs)
        assert chain.evaluate(ctx).passed is False
        # evaluate_runtime() should pass (static filter skipped)
        assert chain.evaluate_runtime(ctx).passed is True
