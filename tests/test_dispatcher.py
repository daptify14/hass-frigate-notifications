"""Tests for the notification dispatcher."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant, ServiceCall
import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.frigate_notifications.config import (
    DEFAULT_PHASE_GENAI,
    DEFAULT_PHASE_INITIAL,
    PhaseConfig,
    PhaseDelivery,
)
from custom_components.frigate_notifications.const import SIGNAL_DISPATCH_PROBLEM
from custom_components.frigate_notifications.dispatcher import (
    NotificationDispatcher,
    lifecycle_to_phase,
    resolve_dispatch_plan,
)
from custom_components.frigate_notifications.enums import Lifecycle, Phase
from custom_components.frigate_notifications.filters import (
    FilterChain,
    FilterResult,
    build_default_filter_chain,
)
from custom_components.frigate_notifications.models import ReviewState

from .factories import make_genai, make_profile, make_review, make_runtime


@pytest.mark.parametrize(
    ("lifecycle", "is_initial", "expected"),
    [
        (Lifecycle.NEW, True, Phase.INITIAL),
        (Lifecycle.UPDATE, True, Phase.INITIAL),
        (Lifecycle.UPDATE, False, Phase.UPDATE),
        (Lifecycle.END, False, Phase.END),
        (Lifecycle.GENAI, False, Phase.GENAI),
    ],
    ids=["new→initial", "update-initial→initial", "update→update", "end→end", "genai→genai"],
)
def test_lifecycle_to_phase(lifecycle: Lifecycle, is_initial: bool, expected: Phase) -> None:
    """Lifecycle enum maps to correct Phase enum."""
    assert lifecycle_to_phase(lifecycle, is_initial=is_initial) == expected


@pytest.fixture
def _zero_delays():
    """Make asyncio.sleep resolve instantly."""
    with patch("asyncio.sleep", new_callable=AsyncMock):
        yield


@pytest.fixture
def notify_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Register a mock notify service and return the call list."""
    return async_mock_service(hass, "notify", "mobile_app_test_phone")


class TestDispatcherNew:
    @pytest.mark.usefixtures("_zero_delays")
    async def test_new_review_dispatches(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        profile = make_profile()
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()
        await dispatcher.on_review_new(review)
        await hass.async_block_till_done()
        assert len(notify_calls) == 1

    @pytest.mark.usefixtures("_zero_delays")
    async def test_no_profiles_for_camera_skips(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        runtime = make_runtime([])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        await dispatcher.on_review_new(make_review())
        await hass.async_block_till_done()
        assert len(notify_calls) == 0

    @pytest.mark.usefixtures("_zero_delays")
    async def test_filter_rejects_skips_dispatch(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """When filter chain rejects, no notification is sent."""

        class RejectAll:
            runtime_recheck = False

            def check(self, ctx):
                return FilterResult(passed=False, filter_name="test", reason="test")

        reject_chain = FilterChain([RejectAll()])
        runtime = make_runtime([make_profile()])
        dispatcher = NotificationDispatcher(hass, runtime, reject_chain)
        await dispatcher.on_review_new(make_review())
        await hass.async_block_till_done()
        assert len(notify_calls) == 0


class TestDispatcherUpdate:
    @pytest.mark.usefixtures("_zero_delays")
    async def test_update_after_initial_dispatches(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        profile = make_profile()
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        await dispatcher.on_review_new(review)
        await hass.async_block_till_done()
        assert len(notify_calls) == 1

        await dispatcher.on_review_update(review)
        await hass.async_block_till_done()
        assert len(notify_calls) == 2

    @pytest.mark.parametrize(
        ("phase", "handler"),
        [(Phase.UPDATE, "on_review_update"), (Phase.END, "on_review_end")],
        ids=["update", "end"],
    )
    @pytest.mark.usefixtures("_zero_delays")
    async def test_disabled_phase_skips(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall], phase: Phase, handler: str
    ) -> None:
        disabled = PhaseConfig(delivery=PhaseDelivery(enabled=False))
        profile = make_profile(phases={phase: disabled})
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        await dispatcher.on_review_new(review)
        await hass.async_block_till_done()
        assert len(notify_calls) == 1

        await getattr(dispatcher, handler)(review)
        await hass.async_block_till_done()
        assert len(notify_calls) == 1


class TestDispatcherEnd:
    @pytest.mark.usefixtures("_zero_delays")
    async def test_end_dispatches(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        profile = make_profile()
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        await dispatcher.on_review_new(review)
        await hass.async_block_till_done()

        await dispatcher.on_review_end(review)
        await hass.async_block_till_done()
        assert len(notify_calls) == 2


class TestDispatcherGenAI:
    @pytest.mark.usefixtures("_zero_delays")
    async def test_genai_dispatches_independently(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        profile = make_profile(phases={Phase.GENAI: DEFAULT_PHASE_GENAI})
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review(genai=make_genai())

        await dispatcher.on_review_new(review)
        await hass.async_block_till_done()

        await dispatcher.on_genai(review)
        await hass.async_block_till_done()
        assert len(notify_calls) == 2


class TestDispatcherRetirement:
    @pytest.mark.usefixtures("_zero_delays")
    async def test_genai_dispatch_retires_profile_review_state(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """Full lifecycle (new -> end -> genai) retires state after GenAI dispatch."""
        profile = make_profile(phases={Phase.GENAI: DEFAULT_PHASE_GENAI})
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review(genai=make_genai())

        await dispatcher.on_review_new(review)
        await hass.async_block_till_done()
        await dispatcher.on_review_end(review)
        await hass.async_block_till_done()

        key = (profile.profile_id, review.review_id)
        assert key in dispatcher._review_states

        await dispatcher.on_genai(review)
        await hass.async_block_till_done()

        assert key not in dispatcher._review_states

    @pytest.mark.usefixtures("_zero_delays")
    async def test_end_dispatch_retires_when_no_genai_configured(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """Profile with GenAI disabled retires state after end dispatch."""
        disabled_genai = PhaseConfig(delivery=PhaseDelivery(enabled=False))
        profile = make_profile(phases={Phase.GENAI: disabled_genai})
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        await dispatcher.on_review_new(review)
        await hass.async_block_till_done()

        key = (profile.profile_id, review.review_id)
        assert key in dispatcher._review_states

        await dispatcher.on_review_end(review)
        await hass.async_block_till_done()

        assert key not in dispatcher._review_states

    @pytest.mark.usefixtures("_zero_delays")
    async def test_end_dispatch_does_not_retire_when_genai_configured(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """Profile with GenAI enabled keeps state after end dispatch."""
        profile = make_profile(phases={Phase.GENAI: DEFAULT_PHASE_GENAI})
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        await dispatcher.on_review_new(review)
        await hass.async_block_till_done()
        await dispatcher.on_review_end(review)
        await hass.async_block_till_done()

        key = (profile.profile_id, review.review_id)
        assert key in dispatcher._review_states


class TestDispatcherCleanup:
    @pytest.mark.usefixtures("_zero_delays")
    async def test_cleanup_removes_states(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        profile = make_profile()
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        await dispatcher.on_review_new(review)
        await hass.async_block_till_done()

        key = (profile.profile_id, review.review_id)
        assert key in dispatcher._review_states

        dispatcher.cleanup_review(review.review_id)
        assert key not in dispatcher._review_states

    async def test_cleanup_cancels_pending_task(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """Cleanup cancels any pending dispatch task."""
        profile = make_profile()
        # Use a long delay so the task stays pending.
        runtime = make_runtime([profile], initial_delay=60.0)
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        await dispatcher.on_review_new(review)
        # Don't await block_till_done — task is pending (sleeping).
        key = (profile.profile_id, review.review_id)
        rs = dispatcher._review_states[key]
        assert rs.pending_task is not None
        assert not rs.pending_task.done()

        dispatcher.cleanup_review(review.review_id)
        assert key not in dispatcher._review_states
        # Task handles CancelledError internally and returns cleanly.
        await hass.async_block_till_done()
        assert rs.pending_task.done()
        assert len(notify_calls) == 0


class TestDispatcherPendingAbsorb:
    async def test_update_absorbed_during_pending_initial(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """Update arriving while initial dispatch is pending is silently absorbed."""
        profile = make_profile()
        # Long delay keeps the initial task pending.
        runtime = make_runtime([profile], initial_delay=60.0)
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        await dispatcher.on_review_new(review)
        # Don't await block_till_done — initial task is sleeping.

        # Update arrives while initial is pending — should be absorbed.
        await dispatcher.on_review_update(review)
        assert len(notify_calls) == 0

        # Clean up the pending task.
        dispatcher.cleanup_review(review.review_id)
        await hass.async_block_till_done()


class TestDispatcherFailure:
    @pytest.mark.usefixtures("_zero_delays")
    async def test_delivery_failure_tags_signal_and_skips_bookkeeping(
        self, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
    ) -> None:
        """HA delivery failure: logs warning, emits delivery_error signal, skips bookkeeping."""
        from homeassistant.exceptions import HomeAssistantError
        from homeassistant.helpers.dispatcher import async_dispatcher_connect

        async def _raise(*args, **kwargs):
            msg = "Push delivery failed"
            raise HomeAssistantError(msg)

        hass.services.async_register("notify", "mobile_app_test_phone", _raise)

        profile = make_profile(cooldown_seconds=60)
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        problem_received: list[str | None] = []
        signal = f"{SIGNAL_DISPATCH_PROBLEM}_{profile.entry_id}_{profile.profile_id}"
        async_dispatcher_connect(hass, signal, problem_received.append)

        stats_received: list = []
        async_dispatcher_connect(
            hass,
            f"frigate_notifications_stats_{profile.entry_id}",
            lambda *a: stats_received.append(a),
        )

        await dispatcher.on_review_new(review)
        await hass.async_block_till_done()

        # Tagged problem signal.
        assert len(problem_received) == 1
        assert problem_received[0] is not None
        assert problem_received[0].startswith("delivery_error:")
        # Warning logged.
        assert "Delivery failed to" in caplog.text
        # No bookkeeping.
        assert len(stats_received) == 0
        assert "driveway" not in dispatcher._get_profile_state(profile.profile_id).last_sent_at
        rs = dispatcher._get_review_state(profile.profile_id, review.review_id)
        assert rs.initial_sent is False

    @pytest.mark.usefixtures("_zero_delays")
    async def test_render_failure_tags_signal_and_skips_bookkeeping(
        self, hass: HomeAssistant
    ) -> None:
        """TemplateError during render: emits render_error signal, skips bookkeeping."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect
        from homeassistant.helpers.template import TemplateError

        profile = make_profile(cooldown_seconds=60)
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        problem_received: list[str | None] = []
        signal = f"{SIGNAL_DISPATCH_PROBLEM}_{profile.entry_id}_{profile.profile_id}"
        async_dispatcher_connect(hass, signal, problem_received.append)

        stats_received: list = []
        async_dispatcher_connect(
            hass,
            f"frigate_notifications_stats_{profile.entry_id}",
            lambda *a: stats_received.append(a),
        )

        with patch(
            "custom_components.frigate_notifications.dispatcher.assemble_notification",
            side_effect=TemplateError("bad template"),
        ):
            await dispatcher.on_review_new(review)
            await hass.async_block_till_done()

        # Tagged problem signal.
        assert len(problem_received) == 1
        assert problem_received[0] is not None
        assert problem_received[0].startswith("render_error:")
        # No bookkeeping.
        assert len(stats_received) == 0
        assert "driveway" not in dispatcher._get_profile_state(profile.profile_id).last_sent_at
        rs = dispatcher._get_review_state(profile.profile_id, review.review_id)
        assert rs.initial_sent is False

    @pytest.mark.usefixtures("_zero_delays")
    async def test_dispatch_success_clears_problem_signal(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """Successful dispatch emits problem signal with None to clear."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect

        profile = make_profile()
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())

        received: list[str | None] = []
        signal = f"{SIGNAL_DISPATCH_PROBLEM}_{profile.entry_id}_{profile.profile_id}"
        async_dispatcher_connect(hass, signal, received.append)

        await dispatcher.on_review_new(make_review())
        await hass.async_block_till_done()

        assert len(received) == 1
        assert received[0] is None

    @pytest.mark.usefixtures("_zero_delays")
    async def test_handle_lifecycle_exception_emits_problem_signal(
        self, hass: HomeAssistant
    ) -> None:
        """Exception in _handle_lifecycle emits problem signal."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect

        profile = make_profile()
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())

        received: list[str | None] = []
        signal = f"{SIGNAL_DISPATCH_PROBLEM}_{profile.entry_id}_{profile.profile_id}"
        async_dispatcher_connect(hass, signal, received.append)

        with patch.object(dispatcher, "_dispatch_for_profile", side_effect=RuntimeError("boom")):
            await dispatcher.on_review_new(make_review())
            await hass.async_block_till_done()

        assert len(received) == 1
        assert received[0] is not None
        assert "boom" in received[0]

    @pytest.mark.usefixtures("_zero_delays")
    async def test_unexpected_render_error_emits_untagged_signal(self, hass: HomeAssistant) -> None:
        """Non-TemplateError from render emits untagged problem signal."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect

        profile = make_profile()
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())

        received: list[str | None] = []
        signal = f"{SIGNAL_DISPATCH_PROBLEM}_{profile.entry_id}_{profile.profile_id}"
        async_dispatcher_connect(hass, signal, received.append)

        with patch(
            "custom_components.frigate_notifications.dispatcher.assemble_notification",
            side_effect=RuntimeError("context assembly bug"),
        ):
            await dispatcher.on_review_new(make_review())
            await hass.async_block_till_done()

        assert len(received) == 1
        assert received[0] is not None
        assert not received[0].startswith("render_error:")
        assert "context assembly bug" in received[0]

    @pytest.mark.usefixtures("_zero_delays")
    async def test_unexpected_delivery_error_emits_untagged_signal(
        self, hass: HomeAssistant
    ) -> None:
        """Non-HomeAssistantError from delivery emits untagged problem signal."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect

        profile = make_profile()
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())

        received: list[str | None] = []
        signal = f"{SIGNAL_DISPATCH_PROBLEM}_{profile.entry_id}_{profile.profile_id}"
        async_dispatcher_connect(hass, signal, received.append)

        with patch(
            "custom_components.frigate_notifications.dispatcher.deliver_notification",
            side_effect=RuntimeError("provider crash"),
        ):
            await dispatcher.on_review_new(make_review())
            await hass.async_block_till_done()

        assert len(received) == 1
        assert received[0] is not None
        assert not received[0].startswith("delivery_error:")
        assert "provider crash" in received[0]


class TestDispatcherCustomActions:
    @pytest.mark.usefixtures("_zero_delays")
    async def test_custom_actions_executed_after_dispatch(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """Phase custom_actions are executed after successful notification."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect

        custom_phase = replace(
            DEFAULT_PHASE_INITIAL,
            custom_actions=({"action": "test.dummy"},),
        )
        profile = make_profile(phases={Phase.INITIAL: custom_phase})
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())

        received: list[str | None] = []
        signal = f"{SIGNAL_DISPATCH_PROBLEM}_{profile.entry_id}_{profile.profile_id}"
        async_dispatcher_connect(hass, signal, received.append)

        with patch(
            "custom_components.frigate_notifications.dispatcher.execute_custom_actions",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_exec:
            await dispatcher.on_review_new(make_review())
            await hass.async_block_till_done()
            assert len(notify_calls) == 1
            mock_exec.assert_awaited_once()

        # Exactly one signal: the success clear.
        assert received == [None]

    @pytest.mark.usefixtures("_zero_delays")
    async def test_empty_custom_actions_returns_none(self, hass: HomeAssistant) -> None:
        """Empty actions tuple returns None without error."""
        from custom_components.frigate_notifications.dispatcher import execute_custom_actions

        assert await execute_custom_actions(hass, (), {}, "test") is None

    @pytest.mark.usefixtures("_zero_delays")
    async def test_custom_actions_script_exception_returns_error(
        self, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Script exception is logged and returns error string."""
        from custom_components.frigate_notifications.dispatcher import execute_custom_actions

        with (
            patch(
                "homeassistant.helpers.script.async_validate_actions_config",
                return_value=[{"action": "test.event"}],
            ),
            patch(
                "homeassistant.helpers.script.Script",
                side_effect=RuntimeError("boom"),
            ),
        ):
            result = await execute_custom_actions(
                hass, ({"action": "test.event"},), {}, "TestProfile"
            )
        assert "Custom action failed" in caplog.text
        assert result is not None
        assert "boom" in result

    @pytest.mark.usefixtures("_zero_delays")
    async def test_custom_actions_success_returns_none(self, hass: HomeAssistant) -> None:
        """Successful script execution returns None."""
        from custom_components.frigate_notifications.dispatcher import execute_custom_actions

        mock_script = AsyncMock()
        with (
            patch(
                "homeassistant.helpers.script.async_validate_actions_config",
                return_value=[{"action": "test.event"}],
            ),
            patch("homeassistant.helpers.script.Script", return_value=mock_script),
        ):
            result = await execute_custom_actions(
                hass, ({"action": "test.event"},), {}, "TestProfile"
            )
        assert result is None
        mock_script.async_run.assert_awaited_once()

    @pytest.mark.usefixtures("_zero_delays")
    async def test_custom_action_failure_emits_problem_signal_after_delivery(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """Custom action failure surfaces problem signal without rolling back delivery."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect

        custom_phase = replace(
            DEFAULT_PHASE_INITIAL,
            custom_actions=({"action": "test.dummy"},),
        )
        profile = make_profile(cooldown_seconds=60, phases={Phase.INITIAL: custom_phase})
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        received: list[str | None] = []
        signal = f"{SIGNAL_DISPATCH_PROBLEM}_{profile.entry_id}_{profile.profile_id}"
        async_dispatcher_connect(hass, signal, received.append)

        stats_received: list = []
        async_dispatcher_connect(
            hass,
            f"frigate_notifications_stats_{profile.entry_id}",
            lambda *a: stats_received.append(a),
        )

        with patch(
            "custom_components.frigate_notifications.dispatcher.execute_custom_actions",
            new_callable=AsyncMock,
            return_value="script blew up",
        ):
            await dispatcher.on_review_new(review)
            await hass.async_block_till_done()

        # Delivery succeeded — bookkeeping preserved.
        assert len(notify_calls) == 1
        assert len(stats_received) == 1
        assert review.camera in dispatcher._get_profile_state(profile.profile_id).last_sent_at
        rs = dispatcher._get_review_state(profile.profile_id, review.review_id)
        assert rs.initial_sent is True
        # Signal sequence: clear from delivery, then custom_action_error.
        assert len(received) == 2
        assert received[0] is None
        assert received[1] is not None
        assert received[1].startswith("custom_action_error:")


class TestDispatcherAlertOnce:
    @pytest.mark.usefixtures("_zero_delays")
    async def test_alert_once_silent_on_second_dispatch(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        profile = make_profile(alert_once=True)
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        await dispatcher.on_review_new(review)
        await hass.async_block_till_done()
        # First: not silent.
        first_data = notify_calls[0].data["data"]
        first_sound = first_data["push"]["sound"]
        assert first_sound["name"] != "none"

        await dispatcher.on_review_update(review)
        await hass.async_block_till_done()
        # Second: alert_once → silent.
        second_data = notify_calls[1].data["data"]
        second_sound = second_data["push"]["sound"]
        assert second_sound["name"] == "none"
        assert second_sound["volume"] == 0.0


class TestDispatcherCooldown:
    @pytest.mark.usefixtures("_zero_delays")
    async def test_cooldown_updated_after_dispatch(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """After successful dispatch, cooldown timestamp is set."""
        profile = make_profile(cooldown_seconds=60)
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        await dispatcher.on_review_new(review)
        await hass.async_block_till_done()
        assert len(notify_calls) == 1

        ps = dispatcher._profile_states[profile.profile_id]
        assert review.camera in ps.last_sent_at
        assert ps.last_sent_at[review.camera] > 0

    @pytest.mark.usefixtures("_zero_delays")
    async def test_genai_does_not_update_cooldown(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        profile = make_profile(
            cooldown_seconds=60,
            phases={Phase.GENAI: DEFAULT_PHASE_GENAI},
        )
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review(genai=make_genai())

        await dispatcher.on_genai(review)
        await hass.async_block_till_done()
        assert len(notify_calls) == 1

        ps = dispatcher._get_profile_state(profile.profile_id)
        assert review.camera not in ps.last_sent_at


class TestDispatcherInitialSentFlag:
    @pytest.mark.usefixtures("_zero_delays")
    async def test_disabled_initial_marks_initial_sent(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """Phase disabled: skip dispatch, but mark initial_sent = True."""
        disabled_initial = PhaseConfig(delivery=PhaseDelivery(enabled=False))
        profile = make_profile(phases={Phase.INITIAL: disabled_initial})
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        await dispatcher.on_review_new(review)
        await hass.async_block_till_done()
        assert len(notify_calls) == 0

        rs = dispatcher._get_review_state(profile.profile_id, review.review_id)
        assert rs.initial_sent is True

    @pytest.mark.usefixtures("_zero_delays")
    async def test_update_before_initial_treated_as_initial(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """Update arriving before initial_sent dispatches as initial phase."""
        profile = make_profile()
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        # Skip on_review_new, go straight to update.
        await dispatcher.on_review_update(review)
        await hass.async_block_till_done()
        assert len(notify_calls) == 1

        rs = dispatcher._get_review_state(profile.profile_id, review.review_id)
        assert rs.initial_sent is True

    @pytest.mark.usefixtures("_zero_delays")
    async def test_deferred_initial_with_recognition_filter(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """New rejected (no -verified), update with -verified fires as initial."""
        from custom_components.frigate_notifications.enums import RecognitionMode

        profile = make_profile(
            recognition_mode=RecognitionMode.REQUIRE_RECOGNIZED,
        )
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review(objects=["person"])

        # new: no verified objects → rejected by SubLabelFilter.
        await dispatcher.on_review_new(review)
        await hass.async_block_till_done()
        assert len(notify_calls) == 0

        # update: now with verified → fires as initial.
        review.objects = ["person-verified"]
        await dispatcher.on_review_update(review)
        await hass.async_block_till_done()
        assert len(notify_calls) == 1

        rs = dispatcher._get_review_state(profile.profile_id, review.review_id)
        assert rs.initial_sent is True


class TestDelayedRefilter:
    async def test_silence_during_delay_suppresses_notification(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """Silence activated during delay window prevents notification."""
        import asyncio

        from custom_components.frigate_notifications.const import SILENCE_DATETIMES_KEY

        profile = make_profile()
        runtime = make_runtime([profile], initial_delay=10.0)
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        blocker: asyncio.Future[None] = hass.loop.create_future()

        async def _block(delay: float) -> None:
            await blocker

        with patch("asyncio.sleep", side_effect=_block):
            await dispatcher.on_review_new(review)

            # Activate silence mid-delay.
            from datetime import UTC, datetime, timedelta

            future = (datetime.now(tz=UTC) + timedelta(hours=1)).isoformat()
            entity_id = "datetime.test_silenced_until"
            hass.data.setdefault(SILENCE_DATETIMES_KEY, {})[profile.profile_id] = type(
                "E", (), {"entity_id": entity_id}
            )()
            hass.states.async_set(entity_id, future)

            # Unblock the sleep.
            blocker.set_result(None)
            await hass.async_block_till_done()

        assert len(notify_calls) == 0


class TestDispatcherPendingTaskCancel:
    async def test_rapid_updates_cancel_previous_pending(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """A second update cancels the first update's pending task."""
        import asyncio

        update_phase = PhaseConfig(delivery=PhaseDelivery(delay=10.0))
        profile = make_profile(phases={Phase.UPDATE: update_phase})
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())
        review = make_review()

        # Initial with zero delay.
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await dispatcher.on_review_new(review)
            await hass.async_block_till_done()
        assert len(notify_calls) == 1

        # First update — sleep blocks so task stays pending.
        blocker: asyncio.Future[None] = hass.loop.create_future()

        async def _block_forever(delay: float) -> None:
            await blocker

        with patch("asyncio.sleep", side_effect=_block_forever):
            await dispatcher.on_review_update(review)
            # Don't block_till_done — task is pending.

        key = (profile.profile_id, review.review_id)
        rs = dispatcher._review_states[key]
        first_task = rs.pending_task
        assert first_task is not None
        assert not first_task.done()

        # Second update — cancels first pending, starts new (also blocked).
        with patch("asyncio.sleep", side_effect=_block_forever):
            await dispatcher.on_review_update(review)

        # First task should be cancelled now.
        await asyncio.sleep(0)  # yield to let cancellation propagate
        assert first_task.done()
        assert rs.pending_task is not first_task

        # Clean up.
        dispatcher.cleanup_review(review.review_id)
        await hass.async_block_till_done()


class TestDispatcherMultiCamera:
    @pytest.mark.usefixtures("_zero_delays")
    async def test_multi_camera_profile_receives_reviews_from_all_cameras(
        self, hass: HomeAssistant, notify_calls: list[ServiceCall]
    ) -> None:
        """Multi-camera profile dispatches for reviews from each camera."""
        profile = make_profile(cameras=("driveway", "backyard"))
        runtime = make_runtime([profile])
        dispatcher = NotificationDispatcher(hass, runtime, build_default_filter_chain())

        review_driveway = make_review(camera="driveway", review_id="rev_1")
        review_backyard = make_review(camera="backyard", review_id="rev_2")

        await dispatcher.on_review_new(review_driveway)
        await hass.async_block_till_done()
        assert len(notify_calls) == 1

        await dispatcher.on_review_new(review_backyard)
        await hass.async_block_till_done()
        assert len(notify_calls) == 2


class TestDispatcherLifecycleRouting:
    def _plan(
        self,
        lifecycle: Lifecycle = Lifecycle.NEW,
        *,
        initial_sent: bool = False,
        has_pending_task: bool = False,
        initial_delay: float = 0.0,
        profile=None,
    ):
        return resolve_dispatch_plan(
            lifecycle,
            profile or make_profile(),
            ReviewState(initial_sent=initial_sent),
            initial_delay,
            has_pending_task=has_pending_task,
        )

    def test_new_lifecycle_dispatches_as_initial(self) -> None:
        plan = self._plan(Lifecycle.NEW)
        assert plan.action == "dispatch"
        assert plan.phase == Phase.INITIAL
        assert plan.is_initial is True
        assert plan.is_genai is False

    def test_update_before_initial_sent_dispatches_as_initial(self) -> None:
        plan = self._plan(Lifecycle.UPDATE, initial_sent=False)
        assert plan.action == "dispatch"
        assert plan.phase == Phase.INITIAL
        assert plan.is_initial is True

    def test_update_after_initial_sent_dispatches_as_update(self) -> None:
        plan = self._plan(Lifecycle.UPDATE, initial_sent=True)
        assert plan.action == "dispatch"
        assert plan.phase == Phase.UPDATE
        assert plan.is_initial is False

    def test_update_disabled_skips(self) -> None:
        disabled = PhaseConfig(delivery=PhaseDelivery(enabled=False))
        profile = make_profile(phases={Phase.UPDATE: disabled})
        plan = self._plan(Lifecycle.UPDATE, initial_sent=True, profile=profile)
        assert plan.action == "skip"
        assert plan.phase == Phase.UPDATE

    def test_end_disabled_skips(self) -> None:
        disabled = PhaseConfig(delivery=PhaseDelivery(enabled=False))
        profile = make_profile(phases={Phase.END: disabled})
        plan = self._plan(Lifecycle.END, profile=profile)
        assert plan.action == "skip"
        assert plan.phase == Phase.END

    def test_initial_disabled_skips_and_marks_sent(self) -> None:
        disabled = PhaseConfig(delivery=PhaseDelivery(enabled=False))
        profile = make_profile(phases={Phase.INITIAL: disabled})
        plan = self._plan(Lifecycle.NEW, profile=profile)
        assert plan.action == "skip"
        assert plan.mark_initial_sent is True

    def test_genai_fires_independently(self) -> None:
        plan = self._plan(Lifecycle.GENAI)
        assert plan.action == "fire_independent"
        assert plan.phase == Phase.GENAI
        assert plan.is_genai is True
        assert plan.is_initial is False

    def test_genai_disabled_skips(self) -> None:
        disabled = PhaseConfig(delivery=PhaseDelivery(enabled=False))
        profile = make_profile(phases={Phase.GENAI: disabled})
        plan = self._plan(Lifecycle.GENAI, profile=profile)
        assert plan.action == "skip"
        assert plan.phase == Phase.GENAI

    def test_pending_initial_absorbs_update(self) -> None:
        plan = self._plan(Lifecycle.UPDATE, initial_sent=False, has_pending_task=True)
        assert plan.action == "absorb"

    def test_pending_update_cancels_and_reschedules(self) -> None:
        plan = self._plan(Lifecycle.UPDATE, initial_sent=True, has_pending_task=True)
        assert plan.action == "dispatch"
        assert plan.cancel_pending is True

    def test_initial_delay_added_to_initial_phase(self) -> None:
        plan = self._plan(Lifecycle.NEW, initial_delay=5.0)
        assert plan.delay == 5.0
        assert plan.is_initial is True

    def test_initial_delay_not_added_to_update(self) -> None:
        update_phase = PhaseConfig(delivery=PhaseDelivery(delay=2.0))
        profile = make_profile(phases={Phase.UPDATE: update_phase})
        plan = self._plan(
            Lifecycle.UPDATE,
            initial_sent=True,
            initial_delay=5.0,
            profile=profile,
        )
        assert plan.delay == 2.0
