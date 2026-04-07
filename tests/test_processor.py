"""Tests for the review processor."""

import asyncio
import json
import time

import pytest

from custom_components.frigate_notifications.processor import ReviewProcessor
from tests.payloads import (
    REVIEW_END_PAYLOAD,
    REVIEW_GENAI_PAYLOAD,
    REVIEW_NEW_PAYLOAD,
    REVIEW_UPDATE_PAYLOAD,
)


class TestHandleReviewMessage:
    """Tests for the review message handler happy paths."""

    @pytest.fixture
    def callbacks(self) -> dict[str, list]:
        return {
            "new": [],
            "update": [],
            "end": [],
            "genai": [],
            "complete": [],
            "message": [],
        }

    @pytest.fixture
    def processor(self, callbacks: dict[str, list]) -> ReviewProcessor:
        return ReviewProcessor(
            on_review_new=callbacks["new"].append,
            on_review_update=lambda r, c: callbacks["update"].append((r, c)),
            on_review_end=callbacks["end"].append,
            on_genai=callbacks["genai"].append,
            on_review_retired=callbacks["complete"].append,
            on_review_message=lambda t, p: callbacks["message"].append((t, p)),
        )

    async def test_new_creates_review_fires_callback_and_increments_count(
        self, processor: ReviewProcessor, callbacks: dict[str, list]
    ) -> None:
        assert processor.active_review_count == 0
        await processor.handle_review_message(json.dumps(REVIEW_NEW_PAYLOAD))
        assert len(callbacks["new"]) == 1
        review = callbacks["new"][0]
        assert review.review_id == "1773840946.10543-review1"
        assert review.camera == "driveway"
        assert review.latest_detection_id == "det_id_1"
        assert processor.active_review_count == 1

    async def test_update_known_review_fires_callback_with_change_string(
        self, processor: ReviewProcessor, callbacks: dict[str, list]
    ) -> None:
        await processor.handle_review_message(json.dumps(REVIEW_NEW_PAYLOAD))
        await processor.handle_review_message(json.dumps(REVIEW_UPDATE_PAYLOAD))
        assert len(callbacks["update"]) == 1
        review, change = callbacks["update"][0]
        assert "det_id_2" in change
        assert review.latest_detection_id == "det_id_2"

    async def test_update_known_review_tracks_new_objects(
        self, processor: ReviewProcessor, callbacks: dict[str, list]
    ) -> None:
        await processor.handle_review_message(json.dumps(REVIEW_NEW_PAYLOAD))
        update_payload = json.loads(json.dumps(REVIEW_UPDATE_PAYLOAD))
        update_payload["after"]["data"]["detections"] = ["det_id_1"]
        update_payload["after"]["data"]["objects"] = ["person", "car"]
        await processor.handle_review_message(json.dumps(update_payload))
        _, change = callbacks["update"][0]
        assert "new_objects" in change

    async def test_update_unknown_review_creates_then_fires_callback(
        self, processor: ReviewProcessor, callbacks: dict[str, list]
    ) -> None:
        await processor.handle_review_message(json.dumps(REVIEW_UPDATE_PAYLOAD))
        assert len(callbacks["update"]) == 1
        assert processor.active_review_count == 1

    async def test_end_known_review_updates_and_fires_callback(
        self, processor: ReviewProcessor, callbacks: dict[str, list]
    ) -> None:
        await processor.handle_review_message(json.dumps(REVIEW_NEW_PAYLOAD))
        await processor.handle_review_message(json.dumps(REVIEW_END_PAYLOAD))
        assert len(callbacks["end"]) == 1
        review = callbacks["end"][0]
        assert review.end_time == 1773840991.854811

    async def test_end_unknown_review_creates_then_fires_callback(
        self, processor: ReviewProcessor, callbacks: dict[str, list]
    ) -> None:
        await processor.handle_review_message(json.dumps(REVIEW_END_PAYLOAD))
        assert len(callbacks["end"]) == 1
        assert processor.active_review_count == 1

    async def test_genai_known_review_attaches_data_and_fires_callbacks(
        self, processor: ReviewProcessor, callbacks: dict[str, list]
    ) -> None:
        await processor.handle_review_message(json.dumps(REVIEW_NEW_PAYLOAD))
        await processor.handle_review_message(json.dumps(REVIEW_GENAI_PAYLOAD))
        assert len(callbacks["genai"]) == 1
        review = callbacks["genai"][0]
        assert review.genai is not None
        assert review.genai.title == "Person and Vehicle in Driveway"
        # GenAI no longer calls on_review_retired — review stays in _active_reviews.
        assert len(callbacks["complete"]) == 0
        assert processor.get_review("1773840946.10543-review1") is not None

    async def test_genai_unknown_review_ignored(
        self, processor: ReviewProcessor, callbacks: dict[str, list]
    ) -> None:
        await processor.handle_review_message(json.dumps(REVIEW_GENAI_PAYLOAD))
        assert len(callbacks["genai"]) == 0
        assert len(callbacks["complete"]) == 0


class TestValidation:
    """Tests for payload validation and rejection."""

    @pytest.mark.parametrize(
        ("payload_str", "reason"),
        [
            ("x" * 65537, "oversized"),
            ("{not valid json", "invalid_json"),
            (
                json.dumps({"type": "new", "after": {"data": {"detections": []}}}),
                "missing_review_id",
            ),
            (
                json.dumps(
                    {
                        "type": "new",
                        "after": {
                            "id": "test-review",
                            "data": {"detections": [f"det_{i}" for i in range(51)]},
                        },
                    }
                ),
                "excessive_detections",
            ),
            (
                json.dumps(
                    {
                        "type": "new",
                        "after": {
                            "id": "test-review",
                            "data": {"detections": "not_a_list"},
                        },
                    }
                ),
                "non_list_detections",
            ),
            (json.dumps([1, 2, 3]), "non_object_json"),
            (json.dumps("just a string"), "non_object_string"),
        ],
        ids=[
            "oversized",
            "invalid_json",
            "missing_review_id",
            "excessive_detections",
            "non_list",
            "non_object_json",
            "non_object_string",
        ],
    )
    async def test_invalid_payload_dropped(self, payload_str: str, reason: str) -> None:
        processor = ReviewProcessor()
        await processor.handle_review_message(payload_str)
        assert processor.active_review_count == 0


class TestStateIntegrity:
    """Tests for state consistency across lifecycle."""

    async def test_delayed_consumer_sees_latest_state(self) -> None:
        processor = ReviewProcessor()
        await processor.handle_review_message(json.dumps(REVIEW_NEW_PAYLOAD))
        review = processor.get_review("1773840946.10543-review1")
        assert review is not None
        assert review.objects == ["person"]

        await processor.handle_review_message(json.dumps(REVIEW_UPDATE_PAYLOAD))
        # Same reference — delayed consumer sees updated state.
        assert review.objects == ["person", "car"]

    async def test_before_data_captured_before_update(self) -> None:
        processor = ReviewProcessor()
        await processor.handle_review_message(json.dumps(REVIEW_NEW_PAYLOAD))
        await processor.handle_review_message(json.dumps(REVIEW_UPDATE_PAYLOAD))
        review = processor.get_review("1773840946.10543-review1")
        assert review is not None
        assert review.before_objects == ["person"]
        assert review.before_zones == ["driveway_approach"]

    async def test_unknown_message_type_logged(self) -> None:
        processor = ReviewProcessor()
        payload = {
            "type": "unknown_type",
            "after": {
                "id": "test-review",
                "data": {"detections": []},
            },
        }
        await processor.handle_review_message(json.dumps(payload))
        assert processor.active_review_count == 0


class TestCleanupStale:
    """Tests for stale review cleanup."""

    async def test_removes_reviews_older_than_timeout(self) -> None:
        processor = ReviewProcessor()
        await processor.handle_review_message(json.dumps(REVIEW_NEW_PAYLOAD))
        assert processor.active_review_count == 1

        review = processor.get_review("1773840946.10543-review1")
        assert review is not None
        review.last_update = time.time() - 1801

        processor.cleanup_stale()
        assert processor.active_review_count == 0
        assert "1773840946.10543-review1" not in processor._review_locks

    async def test_fires_on_review_retired_for_each_stale_review(self) -> None:
        complete_calls: list[str] = []
        processor = ReviewProcessor(
            on_review_retired=complete_calls.append,
        )
        await processor.handle_review_message(json.dumps(REVIEW_NEW_PAYLOAD))

        review = processor.get_review("1773840946.10543-review1")
        assert review is not None
        review.last_update = time.time() - 1801

        processor.cleanup_stale()
        assert complete_calls == ["1773840946.10543-review1"]

    async def test_keeps_recent_reviews(self) -> None:
        processor = ReviewProcessor()
        await processor.handle_review_message(json.dumps(REVIEW_NEW_PAYLOAD))

        review = processor.get_review("1773840946.10543-review1")
        assert review is not None
        review.last_update = time.time()

        processor.cleanup_stale()
        assert processor.active_review_count == 1


class TestGetReview:
    """Tests for get_review method."""

    async def test_returns_none_for_unknown_id(self) -> None:
        processor = ReviewProcessor()
        assert processor.get_review("nonexistent") is None


class TestConcurrency:
    """Tests for concurrent message handling."""

    async def test_concurrent_messages_serialized_by_lock(self) -> None:
        results: list[tuple[str, str]] = []
        processor = ReviewProcessor(
            on_review_new=lambda r: results.append(("new", r.review_id)),
            on_review_update=lambda r, c: results.append(("update", r.review_id)),
        )
        await asyncio.gather(
            processor.handle_review_message(json.dumps(REVIEW_NEW_PAYLOAD)),
            processor.handle_review_message(json.dumps(REVIEW_UPDATE_PAYLOAD)),
        )
        # Both processed without corruption.
        assert len(results) == 2
        review = processor.get_review("1773840946.10543-review1")
        assert review is not None
