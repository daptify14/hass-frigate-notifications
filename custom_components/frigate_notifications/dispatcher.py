"""Notification dispatcher for review lifecycle events."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
import logging
import time
from typing import TYPE_CHECKING, Any, Literal

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.template import TemplateError

from .action_presets import resolve_tap_url
from .const import DOMAIN, SIGNAL_DISPATCH_PROBLEM, SIGNAL_LAST_SENT, SIGNAL_STATS
from .enums import Lifecycle, Phase
from .filters import FilterChain, FilterContext
from .message_builder import (
    TemplateCache,
    build_context,
    render_notification,
    render_template,
)
from .models import ProfileState, ReviewState
from .providers.base import get_provider
from .providers.models import RenderedMedia, RenderedNotification

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .config import PhaseConfig
    from .data import ProfileRuntime, RuntimeConfig
    from .models import Review

_LOGGER = logging.getLogger(__name__)


def lifecycle_to_phase(lifecycle: Lifecycle, *, is_initial: bool) -> Phase:
    """Map a lifecycle type to a notification phase."""
    if lifecycle == Lifecycle.NEW:
        return Phase.INITIAL
    if lifecycle == Lifecycle.UPDATE:
        return Phase.INITIAL if is_initial else Phase.UPDATE
    if lifecycle == Lifecycle.END:
        return Phase.END
    if lifecycle == Lifecycle.GENAI:
        return Phase.GENAI
    msg = f"Unexpected lifecycle: {lifecycle!r}"
    raise ValueError(msg)


@dataclass(frozen=True)
class DispatchPlan:
    """Resolved action, phase, and delay for a lifecycle event."""

    action: Literal["dispatch", "fire_independent", "absorb", "skip"]
    phase: Phase
    delay: float
    is_initial: bool
    is_genai: bool
    cancel_pending: bool = False
    mark_initial_sent: bool = False


def resolve_dispatch_plan(
    lifecycle: Lifecycle,
    profile: ProfileRuntime,
    review_state: ReviewState,
    initial_delay: float,
    *,
    has_pending_task: bool,
) -> DispatchPlan:
    """Determine what action to take for a lifecycle event against a profile."""
    # GenAI fires independently, no interaction with pending tasks.
    if lifecycle == Lifecycle.GENAI:
        phase_cfg = profile.get_phase(Phase.GENAI)
        if not phase_cfg.delivery.enabled:
            return DispatchPlan(
                action="skip",
                phase=Phase.GENAI,
                delay=0,
                is_initial=False,
                is_genai=True,
            )
        return DispatchPlan(
            action="fire_independent",
            phase=Phase.GENAI,
            delay=phase_cfg.delivery.delay,
            is_initial=False,
            is_genai=True,
        )

    # Phase-enabled gating for UPDATE and END.
    if lifecycle == Lifecycle.UPDATE and review_state.initial_sent:
        phase_cfg = profile.get_phase(Phase.UPDATE)
        if not phase_cfg.delivery.enabled:
            return DispatchPlan(
                action="skip",
                phase=Phase.UPDATE,
                delay=0,
                is_initial=False,
                is_genai=False,
            )
    if lifecycle == Lifecycle.END:
        phase_cfg = profile.get_phase(Phase.END)
        if not phase_cfg.delivery.enabled:
            return DispatchPlan(
                action="skip",
                phase=Phase.END,
                delay=0,
                is_initial=False,
                is_genai=False,
            )

    is_initial = not review_state.initial_sent

    if is_initial:
        phase_cfg = profile.get_phase(Phase.INITIAL)
        if not phase_cfg.delivery.enabled:
            return DispatchPlan(
                action="skip",
                phase=Phase.INITIAL,
                delay=0,
                is_initial=True,
                is_genai=False,
                mark_initial_sent=True,
            )
    else:
        phase_name = lifecycle_to_phase(lifecycle, is_initial=False)
        phase_cfg = profile.get_phase(phase_name)

    # Absorb updates while an initial dispatch is still pending.
    if is_initial and has_pending_task:
        return DispatchPlan(
            action="absorb",
            phase=Phase.INITIAL,
            delay=0,
            is_initial=True,
            is_genai=False,
        )

    delay = phase_cfg.delivery.delay
    if is_initial:
        delay = initial_delay + phase_cfg.delivery.delay

    phase = lifecycle_to_phase(lifecycle, is_initial=is_initial)
    return DispatchPlan(
        action="dispatch",
        phase=phase,
        delay=delay,
        is_initial=is_initial,
        is_genai=False,
        cancel_pending=has_pending_task,
    )


async def execute_custom_actions(
    hass: HomeAssistant,
    actions: tuple[dict, ...],
    run_variables: Mapping[str, Any],
    profile_name: str,
) -> str | None:
    """Execute a custom action sequence. Returns an error string on failure."""
    if not actions:
        return None
    try:
        from homeassistant.helpers.script import Script, async_validate_actions_config

        validated = await async_validate_actions_config(hass, list(actions))
        script = Script(hass, validated, f"FN: {profile_name}", DOMAIN)
        await script.async_run(run_variables=run_variables)
    except Exception as err:
        _LOGGER.exception("Custom action failed for profile %s", profile_name)
        return str(err) or type(err).__name__
    return None


@dataclass(frozen=True)
class DispatchRequest:
    """Inputs for assembling a notification."""

    hass: HomeAssistant
    profile: ProfileRuntime
    review: Review
    phase: Phase
    phase_config: PhaseConfig
    lifecycle: Lifecycle
    is_genai: bool
    is_initial: bool
    review_state: ReviewState
    template_cache: TemplateCache
    global_zone_aliases: dict[str, dict[str, str]]
    template_id_map: dict[str, str]


def assemble_notification(request: DispatchRequest) -> RenderedNotification:
    """Render notification content into a provider-neutral payload."""
    r = request
    ctx = build_context(
        r.review,
        r.profile,
        r.phase,
        r.lifecycle,
        emoji_mode=r.phase_config.content.emoji_message,
        hass=r.hass,
        global_zone_aliases=r.global_zone_aliases,
    )

    content = render_notification(
        r.hass,
        r.profile,
        r.review,
        r.phase,
        r.phase_config,
        r.lifecycle,
        r.template_cache,
        ctx=ctx,
        template_id_map=r.template_id_map,
    )

    title = content.title
    if r.is_genai and r.review.genai and r.phase_config.content.title_prefix_enabled:
        for level in sorted(r.profile.title_genai_prefixes.keys(), reverse=True):
            if r.review.genai.threat_level >= level:
                prefix = r.profile.title_genai_prefixes[level].strip()
                if prefix:
                    title = f"{prefix} {title}"
                break

    alert_once_silent = (
        r.profile.alert_once
        and r.review_state.initial_sent
        and not r.is_initial
        and not r.phase_config.delivery.critical
    )

    # Attachment context: swap detection_id when use_latest_detection is enabled.
    attachment_ctx = ctx
    if r.phase_config.media.use_latest_detection and ctx.get("latest_detection_id"):
        attachment_ctx = {**ctx, "detection_id": ctx["latest_detection_id"]}

    # Enrich action/tap URI context with access_token (not exposed to templates).
    camera_name = str(ctx.get("camera", ""))
    camera_state = r.hass.states.get(f"camera.{camera_name}") if camera_name else None
    access_token = camera_state.attributes.get("access_token", "") if camera_state else ""
    action_ctx = {**ctx, "access_token": access_token}

    click_url = resolve_tap_url(r.profile, action_ctx)

    return RenderedNotification(
        title=title,
        message=content.message,
        subtitle=content.subtitle,
        tag=render_template(r.hass, r.profile.tag, ctx, r.template_cache),
        group=render_template(r.hass, r.profile.group, ctx, r.template_cache),
        click_url=click_url,
        alert_once_silent=alert_once_silent,
        critical=r.phase_config.delivery.critical,
        phase_name=r.phase,
        media=RenderedMedia(
            still_kind=r.phase_config.media.attachment,
            video_kind=r.phase_config.media.video,
            use_latest_detection=r.phase_config.media.use_latest_detection,
        ),
        ctx=ctx,
        attachment_ctx=attachment_ctx,
        action_ctx=action_ctx,
    )


async def deliver_notification(
    hass: HomeAssistant,
    profile: ProfileRuntime,
    review: Review,
    rendered: RenderedNotification,
) -> bool:
    """Resolve provider and dispatch the notification via HA service call."""
    if not profile.notify_target:
        _LOGGER.warning("No notify target for profile %s, skipping", profile.name)
        return False

    provider = get_provider(profile.provider)
    notify_call = provider.build_notify_call(hass, profile, review, rendered)
    await hass.services.async_call(
        "notify",
        notify_call.service,
        service_data=notify_call.service_data,
        blocking=True,
    )
    return True


@dataclass
class _DispatchContext:
    """Mutable state for one delayed dispatch attempt."""

    profile: ProfileRuntime
    review: Review
    lifecycle: Lifecycle
    review_state: ReviewState
    is_initial: bool
    is_genai: bool
    delay: float
    phase: Phase | None = None
    phase_cfg: PhaseConfig | None = None
    rendered: RenderedNotification | None = None


class NotificationDispatcher:
    """Dispatches notifications based on review lifecycle events."""

    def __init__(
        self,
        hass: HomeAssistant,
        runtime_config: RuntimeConfig,
        filter_chain: FilterChain,
    ) -> None:
        """Initialize dispatcher with runtime config and filter chain."""
        self._hass = hass
        self._runtime = runtime_config
        self._filter_chain = filter_chain
        self._template_cache = TemplateCache()
        self._profile_states: dict[str, ProfileState] = {}
        self._review_states: dict[tuple[str, str], ReviewState] = {}
        self._profiles_by_id: dict[str, ProfileRuntime] = {
            profile.profile_id: profile
            for profiles in runtime_config.profiles.values()
            for profile in profiles
        }

    def _get_profile_state(self, profile_id: str) -> ProfileState:
        if profile_id not in self._profile_states:
            self._profile_states[profile_id] = ProfileState()
        return self._profile_states[profile_id]

    def _get_review_state(self, profile_id: str, review_id: str) -> ReviewState:
        key = (profile_id, review_id)
        if key not in self._review_states:
            self._review_states[key] = ReviewState()
        return self._review_states[key]

    @property
    def global_zone_aliases(self) -> dict[str, dict[str, str]]:
        """Return the global zone alias map from runtime config."""
        return self._runtime.global_zone_aliases

    def get_profile(self, profile_id: str) -> ProfileRuntime | None:
        """Return a profile runtime by profile ID."""
        return self._profiles_by_id.get(profile_id)

    async def on_review_new(self, review: Review) -> None:
        """Handle a new review."""
        await self._handle_lifecycle(review, Lifecycle.NEW)

    async def on_review_update(self, review: Review) -> None:
        """Handle a review update."""
        await self._handle_lifecycle(review, Lifecycle.UPDATE)

    async def on_review_end(self, review: Review) -> None:
        """Handle a review end."""
        await self._handle_lifecycle(review, Lifecycle.END)

    async def on_genai(self, review: Review) -> None:
        """Handle a GenAI update."""
        await self._handle_lifecycle(review, Lifecycle.GENAI)

    def shutdown(self) -> None:
        """Cancel all pending dispatch tasks (called on integration unload)."""
        for rs in self._review_states.values():
            if rs.pending_task and not rs.pending_task.done():
                rs.pending_task.cancel()
        self._review_states.clear()

    def cleanup_review(self, review_id: str) -> None:
        """Cancel pending tasks and remove all states for a review (stale-timer fallback)."""
        keys = [k for k in self._review_states if k[1] == review_id]
        for key in keys:
            rs = self._review_states[key]
            if rs.pending_task and not rs.pending_task.done():
                rs.pending_task.cancel()
            del self._review_states[key]

    def retire_profile_review(self, profile_id: str, review_id: str) -> None:
        """Remove dispatcher state for a (profile, review) pair after final dispatch."""
        key = (profile_id, review_id)
        if key in self._review_states:
            del self._review_states[key]

    async def _handle_lifecycle(self, review: Review, lifecycle: Lifecycle) -> None:
        """Iterate matching profiles and dispatch for each that passes."""
        profiles = self._runtime.profiles.get(review.camera, [])
        for profile in profiles:
            try:
                rs = self._get_review_state(profile.profile_id, review.review_id)
                ps = self._get_profile_state(profile.profile_id)

                ctx = FilterContext(
                    profile=profile,
                    review=review,
                    lifecycle=lifecycle,
                    review_state=rs,
                    profile_state=ps,
                    hass=self._hass,
                )
                result = self._filter_chain.evaluate(ctx)
                if not result.passed:
                    continue

                await self._dispatch_for_profile(profile, review, lifecycle, rs)
            except Exception as err:
                _LOGGER.exception(
                    "Unhandled %s in %s for profile %s / review %s",
                    type(err).__name__,
                    lifecycle.value,
                    profile.profile_id,
                    review.review_id,
                )
                self._signal_dispatch_problem(profile, error_msg=f"lifecycle_error: {err}")

    async def _dispatch_for_profile(
        self,
        profile: ProfileRuntime,
        review: Review,
        lifecycle: Lifecycle,
        review_state: ReviewState,
    ) -> None:
        """Gate by phase enabled toggle and schedule delayed dispatch."""
        has_pending = review_state.pending_task is not None and not review_state.pending_task.done()
        plan = resolve_dispatch_plan(
            lifecycle,
            profile,
            review_state,
            self._runtime.initial_delay,
            has_pending_task=has_pending,
        )

        if plan.mark_initial_sent:
            review_state.initial_sent = True

        if plan.action in ("skip", "absorb"):
            return

        if (
            plan.cancel_pending
            and review_state.pending_task
            and not review_state.pending_task.done()
        ):
            review_state.pending_task.cancel()

        task = self._hass.async_create_task(
            self._delayed_dispatch(
                profile,
                review,
                lifecycle,
                is_initial=plan.is_initial,
                is_genai=plan.is_genai,
                delay=plan.delay,
                review_state=review_state,
            ),
            name=f"fn_{'genai' if plan.is_genai else 'delayed'}_{profile.name}_{review.review_id}",
        )

        # GenAI tasks are fire-and-forget; non-genai are tracked for absorption/cancellation.
        if plan.action == "dispatch":
            review_state.pending_task = task

    async def _delayed_dispatch(
        self,
        profile: ProfileRuntime,
        review: Review,
        lifecycle: Lifecycle,
        *,
        is_initial: bool,
        is_genai: bool,
        delay: float,
        review_state: ReviewState,
    ) -> None:
        """Sleep for any configured delay, then render and send the notification."""
        if delay > 0:
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                return

        ctx = _DispatchContext(
            profile=profile,
            review=review,
            lifecycle=lifecycle,
            review_state=review_state,
            is_initial=is_initial,
            is_genai=is_genai,
            delay=delay,
        )

        if not self._passes_runtime_recheck(ctx):
            return

        if not self._render_notification(ctx):
            self._retire_if_final_dispatch(profile, review, lifecycle, is_genai=is_genai)
            return
        assert ctx.phase is not None
        assert ctx.phase_cfg is not None
        assert ctx.rendered is not None
        phase = ctx.phase
        phase_cfg = ctx.phase_cfg
        rendered = ctx.rendered

        try:
            success = await deliver_notification(self._hass, profile, review, rendered)
        except HomeAssistantError as err:
            _LOGGER.warning(
                "Delivery failed to %s for review %s: %s",
                profile.notify_target or "<unset>",
                review.review_id[:25],
                err,
            )
            self._signal_dispatch_problem(profile, error_msg=f"delivery_error: {err}")
            self._retire_if_final_dispatch(profile, review, lifecycle, is_genai=is_genai)
            return
        except Exception as err:
            _LOGGER.exception(
                "Unexpected delivery failure to %s for review %s",
                profile.notify_target or "<unset>",
                review.review_id[:25],
            )
            self._signal_dispatch_problem(profile, error_msg=str(err))
            self._retire_if_final_dispatch(profile, review, lifecycle, is_genai=is_genai)
            return

        # No notify target is configured. This is not an error and should not retire state.
        if not success:
            return

        self._signal_dispatch_problem(profile, error_msg=None)
        self._update_last_sent(
            profile,
            review,
            str(phase),
            rendered.title,
            rendered.message,
        )
        self._update_stats(profile, review)

        if phase_cfg.custom_actions:
            action_error = await execute_custom_actions(
                self._hass,
                phase_cfg.custom_actions,
                rendered.ctx,
                profile.name,
            )
            if action_error:
                self._signal_dispatch_problem(
                    profile, error_msg=f"custom_action_error: {action_error}"
                )

        if not is_genai:
            self._get_profile_state(profile.profile_id).last_sent_at[review.camera] = time.time()
        if is_initial:
            review_state.initial_sent = True

        _LOGGER.debug(
            "NOTIFY %s -> %s for review %s",
            lifecycle,
            profile.notify_target,
            review.review_id[:25],
        )

        self._retire_if_final_dispatch(profile, review, lifecycle, is_genai=is_genai)

    def _passes_runtime_recheck(self, ctx: _DispatchContext) -> bool:
        """Re-check runtime filters after a delayed wait."""
        if ctx.delay <= 0:
            return True
        ps = self._get_profile_state(ctx.profile.profile_id)
        recheck_ctx = FilterContext(
            profile=ctx.profile,
            review=ctx.review,
            lifecycle=ctx.lifecycle,
            review_state=ctx.review_state,
            profile_state=ps,
            hass=self._hass,
        )
        return self._filter_chain.evaluate_runtime(recheck_ctx).passed

    def _render_notification(self, ctx: _DispatchContext) -> bool:
        """Populate rendered notification state on the dispatch context."""
        ctx.phase = lifecycle_to_phase(ctx.lifecycle, is_initial=ctx.is_initial)
        ctx.phase_cfg = ctx.profile.get_phase(ctx.phase)
        try:
            request = DispatchRequest(
                hass=self._hass,
                profile=ctx.profile,
                review=ctx.review,
                phase=ctx.phase,
                phase_config=ctx.phase_cfg,
                lifecycle=ctx.lifecycle,
                is_genai=ctx.is_genai,
                is_initial=ctx.is_initial,
                review_state=ctx.review_state,
                template_cache=self._template_cache,
                global_zone_aliases=self._runtime.global_zone_aliases,
                template_id_map=self._runtime.template_id_map,
            )
            ctx.rendered = assemble_notification(request)
        except TemplateError as err:
            _LOGGER.warning(
                "Render failed for %s / review %s: %s",
                ctx.profile.name,
                ctx.review.review_id[:25],
                err,
            )
            self._signal_dispatch_problem(ctx.profile, error_msg=f"render_error: {err}")
            return False
        except Exception as err:
            _LOGGER.exception(
                "Unexpected render failure for %s / review %s",
                ctx.profile.name,
                ctx.review.review_id[:25],
            )
            self._signal_dispatch_problem(ctx.profile, error_msg=str(err))
            return False
        return True

    def _retire_if_final_dispatch(
        self,
        profile: ProfileRuntime,
        review: Review,
        lifecycle: Lifecycle,
        *,
        is_genai: bool,
    ) -> None:
        """Retire this profile's review state if this was the final dispatch."""
        # A review is done for this profile after GenAI fires, or after END when
        # GenAI notifications are disabled and no follow-up dispatch remains.
        should_retire = is_genai or (
            lifecycle == Lifecycle.END and not profile.get_phase(Phase.GENAI).delivery.enabled
        )
        if should_retire:
            self.retire_profile_review(profile.profile_id, review.review_id)

    def _update_last_sent(
        self,
        profile: ProfileRuntime,
        review: Review,
        phase: str,
        title: str,
        message: str,
    ) -> None:
        """Signal the profile's last_sent sensor to update."""
        async_dispatcher_send(
            self._hass,
            f"{SIGNAL_LAST_SENT}_{profile.entry_id}_{profile.profile_id}",
            review.review_id,
            phase,
            title,
            message,
        )

    def _update_stats(self, profile: ProfileRuntime, review: Review) -> None:
        """Signal the stats sensor to increment."""
        async_dispatcher_send(
            self._hass,
            f"{SIGNAL_STATS}_{profile.entry_id}",
            review.camera,
            profile.name,
        )

    def _signal_dispatch_problem(self, profile: ProfileRuntime, *, error_msg: str | None) -> None:
        """Signal the profile's dispatch problem binary sensor."""
        async_dispatcher_send(
            self._hass,
            f"{SIGNAL_DISPATCH_PROBLEM}_{profile.entry_id}_{profile.profile_id}",
            error_msg,
        )
