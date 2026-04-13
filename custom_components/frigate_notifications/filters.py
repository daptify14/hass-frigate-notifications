"""Notification filter chain for Notifications for Frigate."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, time as dt_time
import logging
import time
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from homeassistant.const import STATE_HOME, STATE_OFF
from homeassistant.util import dt as dt_util

from .enums import Lifecycle, RecognitionMode, Severity, TimeFilterMode, ZoneMatchMode

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import FrigateNotificationsRuntimeData, ProfileRuntime
    from .models import ProfileState, Review, ReviewState


_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FilterContext:
    """Immutable context passed to every filter in the chain."""

    profile: ProfileRuntime
    review: Review
    lifecycle: Lifecycle
    review_state: ReviewState
    profile_state: ProfileState
    hass: HomeAssistant
    runtime_data: FrigateNotificationsRuntimeData | None = None


@dataclass(frozen=True)
class FilterResult:
    """Result of a single filter evaluation."""

    passed: bool
    filter_name: str = ""
    reason: str = ""


_PASS = FilterResult(passed=True)


@runtime_checkable
class NotificationFilter(Protocol):
    """Protocol that all notification filters implement."""

    runtime_recheck: bool

    def check(self, ctx: FilterContext) -> FilterResult:
        """Evaluate the filter and return pass/reject."""
        ...


def _reject(filter_name: str, reason: str) -> FilterResult:
    return FilterResult(passed=False, filter_name=filter_name, reason=reason)


class SeverityFilter:
    """Reject reviews that don't match the profile's severity requirement."""

    runtime_recheck = False

    def check(self, ctx: FilterContext) -> FilterResult:
        """Evaluate the filter."""
        if ctx.profile.severity == Severity.ANY:
            return _PASS
        if ctx.profile.severity != ctx.review.severity:
            return _reject(
                "severity",
                f"severity {ctx.review.severity} != required {ctx.profile.severity}",
            )
        return _PASS


class ObjectFilter:
    """Reject reviews whose objects don't intersect the profile's object list."""

    runtime_recheck = False

    def check(self, ctx: FilterContext) -> FilterResult:
        """Evaluate the filter."""
        if not ctx.profile.objects:
            return _PASS
        clean_objs = {o.replace("-verified", "") for o in ctx.review.objects}
        if not clean_objs & set(ctx.profile.objects):
            return _reject(
                "object",
                f"objects {sorted(clean_objs)} not in required {list(ctx.profile.objects)}",
            )
        return _PASS


class SubLabelFilter:
    """Reject reviews based on recognition mode and sub-label include/exclude lists."""

    runtime_recheck = False

    def check(self, ctx: FilterContext) -> FilterResult:
        """Evaluate the filter."""
        mode = ctx.profile.recognition_mode
        if mode == RecognitionMode.DISABLED:
            return _PASS

        if mode == RecognitionMode.REQUIRE_RECOGNIZED:
            has_verified = any(o.endswith("-verified") for o in ctx.review.objects)
            if not has_verified:
                return _reject(
                    "sub_label",
                    "no verified objects present, recognition required",
                )
            required = ctx.profile.required_sub_labels
            if required:
                actual = {s.lower() for s in ctx.review.sub_labels}
                if not actual & {s.lower() for s in required}:
                    return _reject(
                        "sub_label",
                        f"no required sub_labels in {sorted(actual)}",
                    )
            return _PASS

        if mode == RecognitionMode.EXCLUDE_SUB_LABELS:
            excluded = ctx.profile.excluded_sub_labels
            if not excluded:
                return _PASS
            actual = {s.lower() for s in ctx.review.sub_labels}
            matched = actual & {s.lower() for s in excluded}
            if matched:
                return _reject(
                    "sub_label",
                    f"excluded sub_labels {sorted(matched)} present",
                )

        return _PASS


class ZoneFilter:
    """Reject reviews whose zones don't satisfy the profile's zone requirement."""

    runtime_recheck = False

    def check(self, ctx: FilterContext) -> FilterResult:
        """Evaluate the filter."""
        if ctx.profile.is_multi_camera:
            return _PASS
        required = ctx.profile.required_zones
        if not required:
            return _PASS
        actual = ctx.review.zones
        if not actual:
            return _reject("zone", f"no zones present, required {list(required)}")
        mode = ctx.profile.zone_match_mode
        if mode == ZoneMatchMode.ANY:
            if not (set(required) & set(actual)):
                return _reject(
                    "zone",
                    f"zones {actual} have no overlap with required {list(required)}",
                )
        elif mode == ZoneMatchMode.ALL:
            if not (set(required) <= set(actual)):
                return _reject(
                    "zone",
                    f"zones {actual} missing required {sorted(set(required) - set(actual))}",
                )
        elif mode == ZoneMatchMode.ORDERED:
            if required[0] != actual[0]:
                return _reject(
                    "zone",
                    f"first zone {actual[0]} != required first {required[0]}",
                )
            it = iter(actual)
            if not all(z in it for z in required):
                return _reject(
                    "zone",
                    f"zones {actual} not in required order {list(required)}",
                )
        return _PASS


class TimeFilter:
    """Reject notifications outside the configured time window."""

    runtime_recheck = True

    def check(self, ctx: FilterContext) -> FilterResult:
        """Evaluate the filter."""
        mode = ctx.profile.time_filter_mode
        start = ctx.profile.time_filter_start
        end = ctx.profile.time_filter_end
        if mode == TimeFilterMode.DISABLED or not start or not end:
            return _PASS
        now = dt_util.now().time()
        try:
            start_t = dt_time.fromisoformat(start)
            end_t = dt_time.fromisoformat(end)
        except ValueError:
            _LOGGER.warning("Invalid time filter value start=%s end=%s; passing filter", start, end)
            return _PASS
        # Same-day window (08:00-18:00) vs overnight wrap (22:00-06:00).
        in_window = start_t <= now <= end_t if start_t <= end_t else now >= start_t or now <= end_t
        if mode == TimeFilterMode.ONLY_DURING and not in_window:
            return _reject("time", f"current time {now} outside window {start}-{end}")
        if mode == TimeFilterMode.NOT_DURING and in_window:
            return _reject("time", f"current time {now} inside excluded window {start}-{end}")
        return _PASS


class StateFilter:
    """Reject when the configured state entity is not in an allowed state."""

    runtime_recheck = True

    def check(self, ctx: FilterContext) -> FilterResult:
        """Evaluate the filter."""
        entity_id = ctx.profile.state_entity
        if not entity_id:
            return _PASS
        allowed = ctx.profile.state_filter_states
        if not allowed:
            return _PASS
        st = ctx.hass.states.get(entity_id)
        current = st.state if st else "unavailable"
        if current not in allowed:
            return _reject(
                "state",
                f"{entity_id} state={current} not in {list(allowed)}",
            )
        return _PASS


class PresenceFilter:
    """Reject when any presence entity is home."""

    runtime_recheck = True

    def check(self, ctx: FilterContext) -> FilterResult:
        """Evaluate the filter."""
        if not ctx.profile.presence_entities:
            return _PASS
        for eid in ctx.profile.presence_entities:
            st = ctx.hass.states.get(eid)
            if st and st.state == STATE_HOME:
                return _reject("presence", f"{eid} is home")
        return _PASS


class SilenceFilter:
    """Reject when the profile's silence datetime entity is active."""

    runtime_recheck = True

    def check(self, ctx: FilterContext) -> FilterResult:
        """Evaluate the filter."""
        entity = (
            ctx.runtime_data.silence_datetimes.get(ctx.profile.profile_id)
            if ctx.runtime_data is not None
            else None
        )
        if entity is None:
            return _PASS
        state = ctx.hass.states.get(entity.entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return _PASS
        try:
            silenced_until = datetime.fromisoformat(state.state)
            if silenced_until > dt_util.utcnow():
                return _reject("silence", f"silenced until {state.state}")
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Malformed silence state '%s' for profile %s: %s",
                state.state,
                ctx.profile.profile_id,
                err,
            )
        return _PASS


class SwitchEnabledFilter:
    """Reject when the profile's enabled switch is off."""

    runtime_recheck = True

    def check(self, ctx: FilterContext) -> FilterResult:
        """Evaluate the filter."""
        entity = (
            ctx.runtime_data.enabled_switches.get(ctx.profile.profile_id)
            if ctx.runtime_data is not None
            else None
        )
        if entity is None:
            return _PASS
        state = ctx.hass.states.get(entity.entity_id)
        if state is not None and state.state == STATE_OFF:
            return _reject("switch_enabled", f"switch {entity.entity_id} is off")
        return _PASS


class GuardEntityFilter:
    """Reject when the external guard entity is off."""

    runtime_recheck = True

    def check(self, ctx: FilterContext) -> FilterResult:
        """Evaluate the filter."""
        entity_id = ctx.profile.guard_entity
        if not entity_id:
            return _PASS
        state = ctx.hass.states.get(entity_id)
        if state and state.state == STATE_OFF:
            return _reject(
                "guard_entity",
                f"{entity_id} is off",
            )
        return _PASS


class CooldownFilter:
    """Reject new reviews within the cooldown window."""

    runtime_recheck = False

    def check(self, ctx: FilterContext) -> FilterResult:
        """Evaluate the filter."""
        if ctx.lifecycle != Lifecycle.NEW:
            return _PASS
        if ctx.profile.cooldown_seconds <= 0:
            return _PASS
        last = ctx.profile_state.last_sent_at.get(ctx.review.camera, 0.0)
        elapsed = time.time() - last
        if elapsed < ctx.profile.cooldown_seconds:
            remaining = ctx.profile.cooldown_seconds - elapsed
            return _reject(
                "cooldown",
                f"{remaining:.0f}s remaining for {ctx.review.camera}",
            )
        return _PASS


class FilterChain:
    """Evaluates a sequence of filters, short-circuiting on first rejection."""

    def __init__(self, filters: Sequence[NotificationFilter]) -> None:
        """Initialize with an ordered sequence of filters."""
        self._filters = list(filters)

    def evaluate(self, ctx: FilterContext) -> FilterResult:
        """Run all filters in order, returning the first rejection or a pass."""
        for f in self._filters:
            result = f.check(ctx)
            if not result.passed:
                _LOGGER.debug(
                    "Profile %s rejected by %s: %s",
                    ctx.profile.name,
                    result.filter_name,
                    result.reason,
                )
                return result
        return _PASS

    def evaluate_runtime(self, ctx: FilterContext) -> FilterResult:
        """Re-run only HA-state-driven filters (for post-delay recheck)."""
        for f in self._filters:
            if not f.runtime_recheck:
                continue
            result = f.check(ctx)
            if not result.passed:
                _LOGGER.debug(
                    "Profile %s rejected by %s (post-delay): %s",
                    ctx.profile.name,
                    result.filter_name,
                    result.reason,
                )
                return result
        return _PASS


def build_default_filter_chain() -> FilterChain:
    """Build the standard filter chain in the canonical order."""
    return FilterChain(
        [
            SeverityFilter(),
            ObjectFilter(),
            SubLabelFilter(),
            ZoneFilter(),
            TimeFilter(),
            StateFilter(),
            PresenceFilter(),
            SilenceFilter(),
            SwitchEnabledFilter(),
            GuardEntityFilter(),
            CooldownFilter(),
        ]
    )
