"""Replay retained reviews through a profile without touching live dispatch state."""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
from typing import TYPE_CHECKING

from homeassistant.helpers.template import TemplateError
import jinja2

from .dispatcher import DispatchRequest, assemble_notification, resolve_dispatch_plan
from .enums import Lifecycle, Phase, ReplayOutcome
from .filters import FilterChain, FilterContext
from .message_builder import TemplateCache
from .models import ProfileState, Review, ReviewSnapshot, ReviewState, update_reasons
from .providers.base import get_provider

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import FrigateNotificationsRuntimeData, ProfileRuntime, RuntimeConfig
    from .dispatcher import DispatchPlan
    from .providers.models import NotifyCall, RenderedNotification
    from .review_history import ReviewRecord

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReplayOverrides:
    """Template overrides applied to every phase before a replay."""

    title_template: str = ""
    message_template: str = ""
    subtitle_template: str = ""

    def apply(self, profile: ProfileRuntime) -> ProfileRuntime:
        """Return a profile whose resolved phases use the override templates."""
        if not (self.title_template or self.message_template or self.subtitle_template):
            return profile
        phases = {}
        for phase in Phase:
            cfg = profile.get_phase(phase)
            content = cfg.content
            if self.title_template:
                content = replace(content, title_template=self.title_template)
            if self.message_template:
                content = replace(content, message_template=self.message_template)
            if self.subtitle_template:
                content = replace(content, subtitle_template=self.subtitle_template)
            phases[phase] = replace(cfg, content=content)
        return replace(profile, phases=phases)


@dataclass(frozen=True)
class ReplayRow:
    """What one retained message would have produced."""

    step: int
    lifecycle: Lifecycle
    received_at: float
    outcome: ReplayOutcome
    phase: Phase | None = None
    fired_at: float | None = None
    detail: str = ""
    rendered: RenderedNotification | None = None
    notify_call: NotifyCall | None = None


@dataclass(frozen=True)
class ReplayResult:
    """Rows for one replayed review, in message order."""

    record: ReviewRecord
    rows: tuple[ReplayRow, ...]


@dataclass(frozen=True)
class _Pending:
    """A dispatch waiting for its delay, standing in for the live pending task."""

    step: int
    lifecycle: Lifecycle
    fire_at: float
    plan: DispatchPlan


class _Walker:
    """Walks one record's messages, firing delayed dispatches from real message gaps."""

    def __init__(
        self,
        hass: HomeAssistant,
        runtime: RuntimeConfig,
        filter_chain: FilterChain | None,
        runtime_data: FrigateNotificationsRuntimeData | None,
        profile: ProfileRuntime,
        record: ReviewRecord,
    ) -> None:
        """Set up fresh per-replay state; nothing here is shared with the live dispatcher."""
        self._hass = hass
        self._runtime = runtime
        self._chain = filter_chain
        self._runtime_data = runtime_data
        self._profile = profile
        self._record = record
        self._review = Review.from_message(record.steps[0].payload)
        self._review_state = ReviewState()
        self._profile_state = ProfileState()
        self._cache = TemplateCache()
        self._rows: list[ReplayRow] = []

    def run(self) -> ReplayResult:
        """Produce one row per retained message."""
        pending: _Pending | None = None
        independent: _Pending | None = None
        for index, step in enumerate(self._record.steps):
            # Due dispatches fire before this message is applied, so they render the
            # review exactly as the live delivery would have seen it.
            pending, independent = self._fire_due(pending, independent, step.received_at)
            self._review.apply_message(step.payload)

            rejection = self._reject_reason(step.lifecycle)
            if rejection:
                self._add(
                    index, step.lifecycle, step.received_at, ReplayOutcome.REJECTED, rejection
                )
                continue

            plan = resolve_dispatch_plan(
                step.lifecycle,
                self._profile,
                self._review_state,
                self._runtime.initial_delay,
                has_pending_task=pending is not None,
                reasons=update_reasons(self._review, self._review_state.scheduled),
            )
            if plan.mark_initial_sent:
                self._review_state.initial_sent = True
            if plan.mark_initial_sent or plan.action in ("absorb", "dispatch"):
                self._review_state.scheduled = ReviewSnapshot.of(
                    self._review, self._review_state.scheduled
                )
            # Absorbed messages already changed the review; the pending row carries them.
            if plan.action == "absorb" and pending is not None:
                detail = f"absorbed into step {pending.step}"
                self._add(index, step.lifecycle, step.received_at, ReplayOutcome.ABSORBED, detail)
                continue
            if plan.action in ("skip", "filtered"):
                outcome = (
                    ReplayOutcome.FILTERED if plan.action == "filtered" else ReplayOutcome.SKIPPED
                )
                self._add(index, step.lifecycle, step.received_at, outcome, plan.detail, plan.phase)
                continue
            if plan.cancel_pending and pending is not None:
                self._add(
                    pending.step,
                    pending.lifecycle,
                    self._record.steps[pending.step].received_at,
                    ReplayOutcome.SUPERSEDED,
                    f"superseded by step {index}",
                    pending.plan.phase,
                )
                pending = None
            dispatch = _Pending(index, step.lifecycle, step.received_at + plan.delay, plan)
            # GenAI neither waits on nor cancels other dispatches, so it gets its own slot.
            if plan.action == "fire_independent":
                if independent is not None:
                    self._fire(independent)
                independent = dispatch
            else:
                pending = dispatch
        self._fire_due(pending, independent, float("inf"))
        return ReplayResult(self._record, tuple(sorted(self._rows, key=lambda r: r.step)))

    def _fire_due(
        self, pending: _Pending | None, independent: _Pending | None, now: float
    ) -> tuple[_Pending | None, _Pending | None]:
        """Fire every dispatch due by ``now`` in time order; return the ones still waiting."""
        due = [d for d in (pending, independent) if d is not None and d.fire_at <= now]
        for dispatch in sorted(due, key=lambda d: (d.fire_at, d.step)):
            self._fire(dispatch)
        return (
            pending if pending is not None and pending not in due else None,
            independent if independent is not None and independent not in due else None,
        )

    def _reject_reason(self, lifecycle: Lifecycle) -> str:
        """Return "filter: reason" when the chain rejects the current review, else empty."""
        if self._chain is None:
            return ""
        ctx = FilterContext(
            profile=self._profile,
            review=self._review,
            lifecycle=lifecycle,
            review_state=self._review_state,
            profile_state=self._profile_state,
            hass=self._hass,
            runtime_data=self._runtime_data,
        )
        result = self._chain.evaluate(ctx)
        return "" if result.passed else f"{result.filter_name}: {result.reason}"

    def _fire(self, pending: _Pending) -> None:
        """Render with the review as it stands now, the state a live delivery would see."""
        plan = pending.plan
        received_at = self._record.steps[pending.step].received_at
        request = DispatchRequest(
            hass=self._hass,
            profile=self._profile,
            review=self._review,
            phase=plan.phase,
            phase_config=self._profile.get_phase(plan.phase),
            lifecycle=pending.lifecycle,
            is_genai=plan.is_genai,
            is_initial=plan.is_initial,
            review_state=self._review_state,
            template_cache=self._cache,
            global_zone_aliases=self._runtime.global_zone_aliases,
            template_id_map=self._runtime.template_id_map,
        )
        try:
            rendered = assemble_notification(request)
            call = get_provider(self._profile.provider).build_notify_call(
                self._hass, self._profile, self._review, rendered
            )
        except (TemplateError, jinja2.TemplateError) as err:
            self._add(
                pending.step,
                pending.lifecycle,
                received_at,
                ReplayOutcome.RENDER_ERROR,
                str(err),
                plan.phase,
                pending.fire_at,
            )
            return
        self._rows.append(
            ReplayRow(
                step=pending.step,
                lifecycle=pending.lifecycle,
                received_at=received_at,
                outcome=ReplayOutcome.RENDERED,
                phase=plan.phase,
                fired_at=pending.fire_at,
                rendered=rendered,
                notify_call=call,
            )
        )
        if plan.is_initial:
            self._review_state.initial_sent = True
        self._review_state.notified = ReviewSnapshot.of(self._review, self._review_state.notified)
        self._review_state.scheduled = self._review_state.notified

    def _add(
        self,
        step: int,
        lifecycle: Lifecycle,
        received_at: float,
        outcome: ReplayOutcome,
        detail: str,
        phase: Phase | None = None,
        fired_at: float | None = None,
    ) -> None:
        """Record a row that produced no notification."""
        self._rows.append(
            ReplayRow(
                step=step,
                lifecycle=lifecycle,
                received_at=received_at,
                outcome=outcome,
                phase=phase,
                fired_at=fired_at,
                detail=detail,
            )
        )


def replay_review(
    hass: HomeAssistant,
    runtime: RuntimeConfig,
    filter_chain: FilterChain,
    runtime_data: FrigateNotificationsRuntimeData | None,
    profile: ProfileRuntime,
    record: ReviewRecord,
    *,
    run_filters: bool,
    overrides: ReplayOverrides,
) -> ReplayResult:
    """Replay a retained review through a profile's current configuration.

    Filters, when run, are evaluated against Home Assistant's state now. Cooldown
    never rejects because the replay starts from a fresh profile state.
    """
    chain = filter_chain if run_filters else None
    walker = _Walker(hass, runtime, chain, runtime_data, overrides.apply(profile), record)
    return walker.run()
