"""Review processor — handles frigate/reviews MQTT lifecycle."""

import asyncio
from collections.abc import Callable
import json
import logging
import time
from typing import Any

from .const import MAX_DETECTION_IDS, MAX_PAYLOAD_SIZE, STALE_REVIEW_TIMEOUT
from .enums import Lifecycle
from .models import Review

_LOGGER = logging.getLogger(__name__)


class ReviewProcessor:
    """Processes frigate/reviews MQTT messages and fires lifecycle callbacks."""

    def __init__(
        self,
        on_review_new: Callable[[Review], None] | None = None,
        on_review_update: Callable[[Review, str], None] | None = None,
        on_review_end: Callable[[Review], None] | None = None,
        on_genai: Callable[[Review], None] | None = None,
        on_review_retired: Callable[[str], None] | None = None,
        on_review_message: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        """Initialize processor with lifecycle callbacks."""
        self._active_reviews: dict[str, Review] = {}
        self._review_locks: dict[str, asyncio.Lock] = {}

        self._on_review_new = on_review_new
        self._on_review_update = on_review_update
        self._on_review_end = on_review_end
        self._on_genai = on_genai
        self._on_review_retired = on_review_retired
        self._on_review_message = on_review_message

    @property
    def active_review_count(self) -> int:
        """Number of currently tracked reviews."""
        return len(self._active_reviews)

    def get_review(self, review_id: str) -> Review | None:
        """Get an active review by ID."""
        return self._active_reviews.get(review_id)

    async def handle_review_message(self, payload_str: str) -> None:
        """Handle a message from frigate/reviews."""
        if len(payload_str) > MAX_PAYLOAD_SIZE:
            _LOGGER.warning("Review message too large (%d bytes), dropping", len(payload_str))
            return

        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            _LOGGER.warning("Invalid JSON in review message")
            return

        if not isinstance(payload, dict):
            _LOGGER.warning("Review message payload is not a JSON object")
            return

        msg_type = payload.get("type", "")
        after = payload.get("after", {})
        review_id = after.get("id", "")

        data = after.get("data", {})
        detection_ids = data.get("detections", [])
        if not isinstance(detection_ids, list) or len(detection_ids) > MAX_DETECTION_IDS:
            _LOGGER.warning(
                "Invalid or excessive detection_ids (%s) for review %s, dropping",
                type(detection_ids).__name__
                if not isinstance(detection_ids, list)
                else len(detection_ids),
                review_id[:25],
            )
            return

        if not review_id:
            _LOGGER.debug("Review message missing ID, skipping")
            return

        now = time.time()

        if self._on_review_message:
            self._on_review_message(msg_type, payload)

        lock = self._review_locks.setdefault(review_id, asyncio.Lock())
        async with lock:
            if msg_type == Lifecycle.NEW:
                self._handle_new(review_id, payload, now)
            elif msg_type == Lifecycle.UPDATE:
                self._handle_update(review_id, payload, now)
            elif msg_type == Lifecycle.END:
                self._handle_end(review_id, payload, now)
            elif msg_type == Lifecycle.GENAI:
                self._handle_genai(review_id, payload, now)
            else:
                _LOGGER.debug("Unknown review type: %s", msg_type)

            if review_id not in self._active_reviews:
                self._review_locks.pop(review_id, None)

    def _handle_new(self, review_id: str, payload: dict[str, Any], now: float) -> None:
        """Handle a new review."""
        review = Review.from_review_mqtt(payload)
        review.last_update = now
        review.latest_detection_id = review.detection_ids[0] if review.detection_ids else ""
        self._active_reviews[review_id] = review

        _LOGGER.debug(
            "New review %s on %s: objects=%s zones=%s",
            review_id[:25],
            review.camera,
            review.objects,
            review.zones,
        )

        if self._on_review_new:
            self._on_review_new(review)

    def _handle_update(self, review_id: str, payload: dict[str, Any], now: float) -> None:
        """Handle a review update."""
        review = self._active_reviews.get(review_id)
        if not review:
            _LOGGER.debug("Update for unknown review %s, creating", review_id)
            review = Review.from_review_mqtt(payload)
            self._active_reviews[review_id] = review

        prev_objects = list(review.objects)
        prev_detection_ids = set(review.detection_ids)
        review.update_from_review(payload)
        review.last_update = now

        new_ids = set(review.detection_ids) - prev_detection_ids
        if new_ids:
            review.latest_detection_id = next(iter(new_ids))
        new_objects = [o for o in review.objects if o not in prev_objects]
        change = "update"
        if new_ids:
            change = f"new_detections:{','.join(d[:20] for d in new_ids)}"
        elif new_objects:
            change = f"new_objects:{','.join(new_objects)}"

        _LOGGER.debug(
            "Review %s updated (%s): objects=%s sub_labels=%s zones=%s",
            review_id[:25],
            change,
            review.objects,
            review.sub_labels,
            review.zones,
        )

        if self._on_review_update:
            self._on_review_update(review, change)

    def _handle_end(self, review_id: str, payload: dict[str, Any], now: float) -> None:
        """Handle review end."""
        review = self._active_reviews.get(review_id)
        if not review:
            _LOGGER.debug("End for unknown review %s, creating", review_id)
            review = Review.from_review_mqtt(payload)
            self._active_reviews[review_id] = review

        review.update_from_review(payload)
        review.last_update = now

        _LOGGER.debug(
            "Review %s ended: objects=%s sub_labels=%s zones=%s",
            review_id[:25],
            review.objects,
            review.sub_labels,
            review.zones,
        )

        if self._on_review_end:
            self._on_review_end(review)

    def _handle_genai(self, review_id: str, payload: dict[str, Any], now: float) -> None:
        """Handle genAI data arrival."""
        review = self._active_reviews.get(review_id)
        if not review:
            _LOGGER.debug("GenAI for unknown review %s", review_id)
            return

        review.update_from_review(payload)
        review.last_update = now

        if review.genai:
            _LOGGER.debug(
                "GenAI for review %s: title='%s' threat=%d",
                review_id[:25],
                review.genai.title,
                review.genai.threat_level,
            )

        if self._on_genai:
            self._on_genai(review)

    def cleanup_stale(self) -> None:
        """Remove stale reviews and their associated locks."""
        now = time.time()
        stale_reviews = [
            rid
            for rid, review in self._active_reviews.items()
            if now - review.last_update > STALE_REVIEW_TIMEOUT
        ]
        for rid in stale_reviews:
            _LOGGER.debug("Cleaning up stale review %s", rid[:25])
            del self._active_reviews[rid]
            self._review_locks.pop(rid, None)
            if self._on_review_retired:
                self._on_review_retired(rid)
        if stale_reviews:
            _LOGGER.debug("Cleaned up %d stale review(s)", len(stale_reviews))
