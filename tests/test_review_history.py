"""Tests for the bounded review history."""

import copy
from typing import Any

from custom_components.frigate_notifications.enums import Lifecycle
from custom_components.frigate_notifications.review_history import ReviewHistory

from .payloads import (
    REVIEW_END_PAYLOAD,
    REVIEW_GENAI_PAYLOAD,
    REVIEW_NEW_PAYLOAD,
    REVIEW_UPDATE_PAYLOAD,
)

REVIEW_ID = REVIEW_NEW_PAYLOAD["after"]["id"]


def _new_for(review_id: str, camera: str = "driveway") -> dict[str, Any]:
    payload = copy.deepcopy(REVIEW_NEW_PAYLOAD)
    payload["after"]["id"] = review_id
    payload["after"]["camera"] = camera
    return payload


class TestRecord:
    def test_record_appends_steps_in_order(self) -> None:
        history = ReviewHistory()
        history.record(REVIEW_NEW_PAYLOAD, 1.0)
        history.record(REVIEW_UPDATE_PAYLOAD, 2.0)
        history.record(REVIEW_END_PAYLOAD, 3.0)

        record = history.get(REVIEW_ID)
        assert record is not None
        assert record.camera == "driveway"
        assert record.started_at == 1.0
        assert [s.lifecycle for s in record.steps] == [
            Lifecycle.NEW,
            Lifecycle.UPDATE,
            Lifecycle.END,
        ]
        assert record.steps[1].received_at == 2.0
        assert not record.truncated

    def test_record_ignores_unknown_type_and_missing_id(self) -> None:
        history = ReviewHistory()
        history.record({"type": "bogus", "after": {"id": "x"}}, 1.0)
        history.record({"type": "new", "after": {}}, 1.0)
        history.record({"type": "new"}, 1.0)
        assert history.records() == ()

    def test_record_copies_payload(self) -> None:
        history = ReviewHistory()
        payload = copy.deepcopy(REVIEW_NEW_PAYLOAD)
        history.record(payload, 1.0)
        payload["after"]["data"]["objects"].append("dog")

        record = history.get(REVIEW_ID)
        assert record is not None
        assert record.steps[0].payload["after"]["data"]["objects"] == ["person"]

    def test_record_evicts_oldest_review_when_full(self) -> None:
        history = ReviewHistory(max_reviews=2)
        history.record(_new_for("a"), 1.0)
        history.record(_new_for("b"), 2.0)
        history.record(_new_for("c"), 3.0)

        assert history.get("a") is None
        assert [r.review_id for r in history.records()] == ["c", "b"]

    def test_record_drops_steps_past_cap(self) -> None:
        history = ReviewHistory(max_steps=2)
        history.record(REVIEW_NEW_PAYLOAD, 1.0)
        history.record(REVIEW_UPDATE_PAYLOAD, 2.0)
        history.record(REVIEW_END_PAYLOAD, 3.0)
        history.record(REVIEW_GENAI_PAYLOAD, 4.0)

        record = history.get(REVIEW_ID)
        assert record is not None
        assert len(record.steps) == 2
        assert record.dropped_steps == 2
        assert record.truncated


class TestLatest:
    def test_latest_filters_by_camera_newest_first(self) -> None:
        history = ReviewHistory()
        history.record(_new_for("a", "driveway"), 1.0)
        history.record(_new_for("b", "backyard"), 2.0)
        history.record(_new_for("c", "driveway"), 3.0)

        latest = history.latest(["driveway"], count=5)
        assert [r.review_id for r in latest] == ["c", "a"]
        assert [r.review_id for r in history.latest(["driveway"], count=1)] == ["c"]
        assert history.latest(["garage"], count=1) == ()
