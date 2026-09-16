"""Bounded in-memory history of recent Frigate reviews for replay."""

from __future__ import annotations

from collections.abc import Collection, Mapping
import copy
from dataclasses import dataclass, replace
from typing import Any

from .const import REVIEW_HISTORY_MAX_REVIEWS, REVIEW_HISTORY_MAX_STEPS
from .enums import Lifecycle


@dataclass(frozen=True)
class ReviewStep:
    """One frigate/reviews message as received."""

    lifecycle: Lifecycle
    received_at: float
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class ReviewRecord:
    """The ordered messages received for one review."""

    review_id: str
    camera: str
    steps: tuple[ReviewStep, ...]
    dropped_steps: int = 0

    @property
    def started_at(self) -> float:
        """Receive time of the first stored message."""
        return self.steps[0].received_at

    @property
    def truncated(self) -> bool:
        """Whether messages were dropped once the step cap was reached."""
        return self.dropped_steps > 0


class ReviewHistory:
    """Keeps the most recent reviews, oldest evicted first."""

    def __init__(
        self,
        *,
        max_reviews: int = REVIEW_HISTORY_MAX_REVIEWS,
        max_steps: int = REVIEW_HISTORY_MAX_STEPS,
    ) -> None:
        """Initialize an empty history."""
        self._max_reviews = max_reviews
        self._max_steps = max_steps
        self._records: dict[str, ReviewRecord] = {}

    def record(self, payload: Mapping[str, Any], now: float) -> None:
        """Store a message; unknown types and messages without a review id are ignored."""
        msg_type = payload.get("type", "")
        if msg_type not in Lifecycle.__members__.values():
            return
        after = payload.get("after")
        if not isinstance(after, Mapping):
            return
        review_id = after.get("id", "")
        if not review_id:
            return

        step = ReviewStep(Lifecycle(msg_type), now, copy.deepcopy(payload))
        existing = self._records.get(review_id)
        if existing is None:
            if len(self._records) >= self._max_reviews:
                oldest = min(self._records.values(), key=lambda r: r.started_at)
                del self._records[oldest.review_id]
            self._records[review_id] = ReviewRecord(
                review_id=review_id, camera=str(after.get("camera", "")), steps=(step,)
            )
        elif len(existing.steps) >= self._max_steps:
            self._records[review_id] = replace(existing, dropped_steps=existing.dropped_steps + 1)
        else:
            self._records[review_id] = replace(existing, steps=(*existing.steps, step))

    def get(self, review_id: str) -> ReviewRecord | None:
        """Return the record for a review id."""
        return self._records.get(review_id)

    def latest(self, cameras: Collection[str], count: int) -> tuple[ReviewRecord, ...]:
        """Return the newest records on the given cameras, newest first."""
        matching = [r for r in self._records.values() if r.camera in cameras]
        matching.sort(key=lambda r: r.started_at, reverse=True)
        return tuple(matching[:count])

    def records(self) -> tuple[ReviewRecord, ...]:
        """Return every record, newest first."""
        return tuple(sorted(self._records.values(), key=lambda r: r.started_at, reverse=True))
