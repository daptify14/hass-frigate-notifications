"""Tests for replaying retained reviews through a profile."""

import copy
from typing import Any

from homeassistant.core import HomeAssistant
import pytest

from custom_components.frigate_notifications.config import PhaseDelivery
from custom_components.frigate_notifications.data import ProfileRuntime
from custom_components.frigate_notifications.enums import (
    Lifecycle,
    Phase,
    RecognitionMode,
    ReplayOutcome,
    UpdateTrigger,
)
from custom_components.frigate_notifications.filters import build_default_filter_chain
from custom_components.frigate_notifications.replay import (
    ReplayOverrides,
    ReplayResult,
    replay_review,
)
from custom_components.frigate_notifications.review_history import ReviewRecord, ReviewStep

from .factories import make_phase, make_profile, make_runtime
from .payloads import (
    REVIEW_END_PAYLOAD,
    REVIEW_GENAI_PAYLOAD,
    REVIEW_NEW_PAYLOAD,
    REVIEW_UPDATE_PAYLOAD,
    REVIEW_UPDATE_VERIFIED_PAYLOAD,
)

REVIEW_ID = REVIEW_NEW_PAYLOAD["after"]["id"]


def _record(*steps: tuple[Lifecycle, float, dict[str, Any]]) -> ReviewRecord:
    return ReviewRecord(
        review_id=REVIEW_ID,
        camera="driveway",
        steps=tuple(ReviewStep(lc, at, copy.deepcopy(payload)) for lc, at, payload in steps),
    )


def _replay(
    hass: HomeAssistant,
    record: ReviewRecord,
    profile: ProfileRuntime | None = None,
    *,
    initial_delay: float = 0.0,
    run_filters: bool = False,
    overrides: ReplayOverrides | None = None,
) -> ReplayResult:
    profile = profile or make_profile()
    return replay_review(
        hass,
        make_runtime([profile], initial_delay=initial_delay),
        build_default_filter_chain(),
        None,
        profile,
        record,
        run_filters=run_filters,
        overrides=overrides or ReplayOverrides(),
    )


class TestTiming:
    async def test_update_inside_initial_delay_is_absorbed_and_initial_renders_later_state(
        self, hass: HomeAssistant
    ) -> None:
        result = _replay(
            hass,
            _record(
                (Lifecycle.NEW, 0.0, REVIEW_NEW_PAYLOAD),
                (Lifecycle.UPDATE, 2.0, REVIEW_UPDATE_VERIFIED_PAYLOAD),
                (Lifecycle.END, 10.0, REVIEW_END_PAYLOAD),
            ),
            initial_delay=5.0,
        )
        first, second, third = result.rows
        assert first.outcome is ReplayOutcome.RENDERED
        assert first.phase is Phase.INITIAL
        assert first.fired_at == 5.0
        assert first.rendered is not None
        assert "Bob" in first.rendered.ctx["subjects"]
        assert first.notify_call is not None
        assert second.outcome is ReplayOutcome.ABSORBED
        assert second.detail == "absorbed into step 0"
        assert third.outcome is ReplayOutcome.RENDERED
        assert third.phase is Phase.END

    async def test_newer_update_supersedes_pending_update(self, hass: HomeAssistant) -> None:
        profile = make_profile(phases={Phase.UPDATE: make_phase(delivery=PhaseDelivery(delay=5.0))})
        result = _replay(
            hass,
            _record(
                (Lifecycle.NEW, 0.0, REVIEW_NEW_PAYLOAD),
                (Lifecycle.UPDATE, 1.0, REVIEW_UPDATE_PAYLOAD),
                (Lifecycle.UPDATE, 2.0, REVIEW_UPDATE_VERIFIED_PAYLOAD),
            ),
            profile,
        )
        first, second, third = result.rows
        assert first.outcome is ReplayOutcome.RENDERED
        assert first.fired_at == 0.0
        assert second.outcome is ReplayOutcome.SUPERSEDED
        assert second.detail == "superseded by step 2"
        assert second.phase is Phase.UPDATE
        assert third.outcome is ReplayOutcome.RENDERED
        assert third.fired_at == 7.0

    async def test_genai_renders_its_own_phase(self, hass: HomeAssistant) -> None:
        result = _replay(
            hass,
            _record(
                (Lifecycle.NEW, 0.0, REVIEW_NEW_PAYLOAD),
                (Lifecycle.END, 5.0, REVIEW_END_PAYLOAD),
                (Lifecycle.GENAI, 8.0, REVIEW_GENAI_PAYLOAD),
            ),
        )
        assert [row.outcome for row in result.rows] == [ReplayOutcome.RENDERED] * 3
        assert [row.phase for row in result.rows] == [Phase.INITIAL, Phase.END, Phase.GENAI]

    async def test_delayed_genai_fires_after_pending_initial_with_later_state(
        self, hass: HomeAssistant
    ) -> None:
        profile = make_profile(
            alert_once=True,
            phases={Phase.GENAI: make_phase(delivery=PhaseDelivery(delay=20.0))},
        )
        result = _replay(
            hass,
            _record(
                (Lifecycle.NEW, 0.0, REVIEW_NEW_PAYLOAD),
                (Lifecycle.GENAI, 2.0, REVIEW_GENAI_PAYLOAD),
                (Lifecycle.UPDATE, 5.0, REVIEW_UPDATE_VERIFIED_PAYLOAD),
            ),
            profile,
            initial_delay=10.0,
        )
        initial, genai, update = result.rows
        assert initial.outcome is ReplayOutcome.RENDERED
        assert initial.fired_at == 10.0
        assert update.outcome is ReplayOutcome.ABSORBED
        assert genai.outcome is ReplayOutcome.RENDERED
        assert genai.fired_at == 22.0
        assert genai.rendered is not None
        # GenAI rendered after the initial went out and saw the absorbed update.
        assert genai.rendered.alert_once_silent is True
        assert "Bob" in genai.rendered.ctx["subjects"]

    async def test_disabled_initial_phase_is_skipped_and_update_renders_as_update(
        self, hass: HomeAssistant
    ) -> None:
        profile = make_profile(
            phases={Phase.INITIAL: make_phase(delivery=PhaseDelivery(enabled=False))}
        )
        result = _replay(
            hass,
            _record(
                (Lifecycle.NEW, 0.0, REVIEW_NEW_PAYLOAD),
                (Lifecycle.UPDATE, 1.0, REVIEW_UPDATE_PAYLOAD),
            ),
            profile,
        )
        first, second = result.rows
        assert first.outcome is ReplayOutcome.SKIPPED
        assert first.phase is Phase.INITIAL
        assert second.outcome is ReplayOutcome.RENDERED
        assert second.phase is Phase.UPDATE


class TestFilters:
    async def test_rejected_new_then_update_promoted_to_initial(self, hass: HomeAssistant) -> None:
        profile = make_profile(recognition_mode=RecognitionMode.REQUIRE_RECOGNIZED)
        result = _replay(
            hass,
            _record(
                (Lifecycle.NEW, 0.0, REVIEW_NEW_PAYLOAD),
                (Lifecycle.UPDATE, 2.0, REVIEW_UPDATE_VERIFIED_PAYLOAD),
            ),
            profile,
            run_filters=True,
        )
        first, second = result.rows
        assert first.outcome is ReplayOutcome.REJECTED
        assert first.detail.startswith("sub_label:")
        assert second.outcome is ReplayOutcome.RENDERED
        assert second.phase is Phase.INITIAL

    async def test_filters_not_run_by_default(self, hass: HomeAssistant) -> None:
        profile = make_profile(recognition_mode=RecognitionMode.REQUIRE_RECOGNIZED)
        result = _replay(hass, _record((Lifecycle.NEW, 0.0, REVIEW_NEW_PAYLOAD)), profile)
        assert result.rows[0].outcome is ReplayOutcome.RENDERED


class TestRendering:
    async def test_person_then_car_reports_added_subject(self, hass: HomeAssistant) -> None:
        result = _replay(
            hass,
            _record(
                (Lifecycle.NEW, 0.0, REVIEW_NEW_PAYLOAD),
                (Lifecycle.UPDATE, 1.0, REVIEW_UPDATE_PAYLOAD),
            ),
        )
        rendered = result.rows[1].rendered
        assert rendered is not None
        assert rendered.ctx["added_subject"].endswith("Car")

    async def test_second_person_adds_no_subject(self, hass: HomeAssistant) -> None:
        second_person = copy.deepcopy(REVIEW_UPDATE_PAYLOAD)
        second_person["after"]["data"]["objects"] = ["person", "person"]
        result = _replay(
            hass,
            _record(
                (Lifecycle.NEW, 0.0, REVIEW_NEW_PAYLOAD),
                (Lifecycle.UPDATE, 1.0, second_person),
            ),
        )
        rendered = result.rows[1].rendered
        assert rendered is not None
        assert rendered.ctx["added_subject"] == ""
        assert rendered.ctx["detection_count"] == "2"

    async def test_overrides_apply_to_every_phase(self, hass: HomeAssistant) -> None:
        result = _replay(
            hass,
            _record(
                (Lifecycle.NEW, 0.0, REVIEW_NEW_PAYLOAD),
                (Lifecycle.END, 5.0, REVIEW_END_PAYLOAD),
            ),
            overrides=ReplayOverrides(
                title_template="Custom {{ camera }}",
                message_template="Msg {{ objects }}",
                subtitle_template="Sub",
            ),
        )
        for row in result.rows:
            assert row.rendered is not None
            assert row.rendered.title == "Custom driveway"
            assert row.rendered.message.startswith("Msg ")
            assert row.rendered.subtitle == "Sub"

    async def test_empty_overrides_leave_profile_untouched(self) -> None:
        profile = make_profile()
        assert ReplayOverrides().apply(profile) is profile

    @pytest.mark.parametrize(
        "profile_overrides",
        [
            {"tag": "{{ no_such_function() }}"},
            {"action_config": ({"preset": "view_clip", "uri": "{{ no_such_function() }}"},)},
            {"tap_action": {"preset": "view_clip", "uri": "{{ missing_var.x }}"}},
        ],
        ids=["tag", "action-button-uri", "tap-uri"],
    )
    async def test_template_error_produces_render_error_row(
        self, hass: HomeAssistant, profile_overrides: dict[str, Any]
    ) -> None:
        profile = make_profile(**profile_overrides)
        result = _replay(
            hass,
            _record(
                (Lifecycle.NEW, 0.0, REVIEW_NEW_PAYLOAD),
                (Lifecycle.END, 1.0, REVIEW_END_PAYLOAD),
            ),
            profile,
        )
        first, second = result.rows
        assert first.outcome is ReplayOutcome.RENDER_ERROR
        assert first.phase is Phase.INITIAL
        assert first.detail
        assert first.rendered is None
        # The replay carries on past a broken row.
        assert second.outcome is ReplayOutcome.RENDER_ERROR
        assert second.phase is Phase.END


class TestUpdateTriggers:
    async def test_reacquire_after_recognition_is_filtered(self, hass: HomeAssistant) -> None:
        """New, a late face, a re-acquired track, end: only the re-acquire says nothing new."""
        reacquired = copy.deepcopy(REVIEW_UPDATE_VERIFIED_PAYLOAD)
        reacquired["before"] = copy.deepcopy(REVIEW_UPDATE_VERIFIED_PAYLOAD["after"])
        reacquired["after"]["data"]["detections"] = ["det_id_1", "det_id_2"]
        reacquired["after"]["data"]["sub_labels"] = ["Bob", "Bob"]
        profile = make_profile(
            update_triggers=frozenset({UpdateTrigger.ZONE, UpdateTrigger.SUBJECT})
        )
        result = _replay(
            hass,
            _record(
                (Lifecycle.NEW, 0.0, REVIEW_NEW_PAYLOAD),
                (Lifecycle.UPDATE, 5.0, REVIEW_UPDATE_VERIFIED_PAYLOAD),
                (Lifecycle.UPDATE, 60.0, reacquired),
                (Lifecycle.END, 120.0, REVIEW_END_PAYLOAD),
            ),
            profile,
        )
        assert [row.outcome for row in result.rows] == [
            ReplayOutcome.RENDERED,
            ReplayOutcome.RENDERED,
            ReplayOutcome.FILTERED,
            ReplayOutcome.RENDERED,
        ]
        assert result.rows[2].phase == Phase.UPDATE
        assert result.rows[2].detail == "update_triggers: none of [subject, zone] (new: detection)"

    async def test_filtered_update_does_not_supersede_pending_update(
        self, hass: HomeAssistant
    ) -> None:
        no_change = copy.deepcopy(REVIEW_UPDATE_PAYLOAD)
        no_change["before"] = copy.deepcopy(REVIEW_UPDATE_PAYLOAD["after"])
        profile = make_profile(
            phases={Phase.UPDATE: make_phase(delivery=PhaseDelivery(delay=10.0))},
            update_triggers=frozenset({UpdateTrigger.ZONE}),
        )
        result = _replay(
            hass,
            _record(
                (Lifecycle.NEW, 0.0, REVIEW_NEW_PAYLOAD),
                (Lifecycle.UPDATE, 1.0, REVIEW_UPDATE_PAYLOAD),
                (Lifecycle.UPDATE, 2.0, no_change),
            ),
            profile,
        )
        assert [row.outcome for row in result.rows] == [
            ReplayOutcome.RENDERED,
            ReplayOutcome.RENDERED,
            ReplayOutcome.FILTERED,
        ]
        rendered = result.rows[1].rendered
        assert rendered is not None
        assert rendered.ctx["added_zones"] == "Driveway Main"
