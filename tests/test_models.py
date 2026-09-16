"""Tests for data models."""

from typing import Any

import pytest

from custom_components.frigate_notifications.models import (
    GenAIData,
    ProfileState,
    Review,
)
from tests.factories import make_genai, make_review
from tests.payloads import (
    REVIEW_GENAI_PAYLOAD,
    REVIEW_NEW_PAYLOAD,
    REVIEW_UPDATE_PAYLOAD,
)


class TestGenAIData:
    def test_from_metadata_maps_camel_case_keys(self) -> None:
        metadata = {
            "title": "Test Title",
            "shortSummary": "Short summary text",
            "scene": "Scene description",
            "confidence": 0.95,
            "potential_threat_level": 2,
            "other_concerns": ["concern1"],
            "time": "Monday, 10:00 AM",
        }
        genai = GenAIData.from_metadata(metadata)
        assert genai.title == "Test Title"
        assert genai.short_summary == "Short summary text"
        assert genai.scene == "Scene description"
        assert genai.confidence == 0.95
        assert genai.time == "Monday, 10:00 AM"
        assert genai.threat_level == 2

    def test_from_metadata_other_concerns_is_tuple(self) -> None:
        metadata = {"other_concerns": ["a", "b"]}
        genai = GenAIData.from_metadata(metadata)
        assert genai.other_concerns == ("a", "b")
        assert isinstance(genai.other_concerns, tuple)

    def test_from_metadata_missing_keys_use_defaults(self) -> None:
        genai = GenAIData.from_metadata({})
        assert genai.title == ""
        assert genai.short_summary == ""
        assert genai.scene == ""
        assert genai.confidence == 0.0
        assert genai.threat_level == 0
        assert genai.other_concerns == ()
        assert genai.time == ""

    def test_from_metadata_null_other_concerns_becomes_empty_tuple(self) -> None:
        metadata = {"other_concerns": None}
        genai = GenAIData.from_metadata(metadata)
        assert genai.other_concerns == ()


class TestReview:
    def test_from_message_after_apply_extracts_fields(self) -> None:
        """NEW payload extracts all review and data fields."""
        review = Review.from_message(REVIEW_NEW_PAYLOAD)
        review.apply_message(REVIEW_NEW_PAYLOAD)
        # Top-level fields
        assert review.review_id == "1773840946.10543-review1"
        assert review.camera == "driveway"
        assert review.start_time == 1773840946.10543
        assert review.end_time is None
        assert review.severity == "alert"
        # Data fields
        assert review.detection_ids == ["det_id_1"]
        assert review.objects == ["person"]
        assert review.sub_labels == []
        assert review.zones == ["driveway_approach"]

    @pytest.mark.parametrize("payload", [{"after": {}}, {}])
    def test_from_message_defaults(self, payload: dict[str, Any]) -> None:
        """Missing or empty payloads produce safe defaults."""
        review = Review.from_message(payload)
        assert review.review_id == ""
        assert review.camera == ""
        assert review.start_time == 0.0
        assert review.end_time is None
        assert review.severity == ""
        assert review.detection_ids == []
        assert review.objects == []

    def test_from_message_uses_before_for_unknown_review(self) -> None:
        """A review first seen on an update starts from Frigate's before snapshot."""
        review = Review.from_message(REVIEW_UPDATE_PAYLOAD)
        assert review.objects == ["person"]
        assert review.detection_ids == ["det_id_1"]

    def test_from_message_ignores_before_for_other_review(self) -> None:
        """A before snapshot for a different review id is not used as the baseline."""
        payload = {**REVIEW_UPDATE_PAYLOAD, "before": {"id": "other", "data": {"objects": ["dog"]}}}
        review = Review.from_message(payload)
        assert review.objects == ["person", "car"]

    def test_apply_message_tracks_latest_detection(self) -> None:
        """Applying a message returns the new detection ids and tracks the newest."""
        review = Review.from_message(REVIEW_NEW_PAYLOAD)
        assert review.apply_message(REVIEW_NEW_PAYLOAD) == ["det_id_1"]
        assert review.latest_detection_id == "det_id_1"
        assert review.apply_message(REVIEW_UPDATE_PAYLOAD) == ["det_id_2"]
        assert review.latest_detection_id == "det_id_2"
        assert review.apply_message(REVIEW_UPDATE_PAYLOAD) == []
        assert review.latest_detection_id == "det_id_2"

    def test_apply_message_first_genai_populates_metadata(self) -> None:
        """A review first seen on GenAI carries the metadata after apply."""
        review = Review.from_message(REVIEW_GENAI_PAYLOAD)
        assert review.genai is None
        review.apply_message(REVIEW_GENAI_PAYLOAD)
        assert review.genai is not None
        assert review.genai.title == "Person and Vehicle in Driveway"

    def test_update_from_review_captures_before_data_first(self) -> None:
        review = make_review()
        review.update_from_review(REVIEW_UPDATE_PAYLOAD)
        assert review.before_objects == ["person"]
        assert review.before_zones == ["driveway_approach"]

    def test_update_from_review_overwrites_after_fields(self) -> None:
        review = make_review()
        review.update_from_review(REVIEW_UPDATE_PAYLOAD)
        assert review.objects == ["person", "car"]
        assert review.zones == ["driveway_approach", "driveway_main"]
        assert review.detection_ids == ["det_id_1", "det_id_2"]

    def test_update_from_review_attaches_genai_when_metadata_present(self) -> None:
        review = make_review()
        review.update_from_review(REVIEW_GENAI_PAYLOAD)
        assert review.genai is not None
        assert review.genai.title == "Person and Vehicle in Driveway"
        assert review.genai.threat_level == 1

    def test_update_from_review_preserves_fields_on_empty_after(self) -> None:
        """Fields are preserved when after payload has no data."""
        review = make_review(
            objects=["person"], zones=["driveway_approach"], severity="alert", end_time=100.0
        )
        review.update_from_review({"after": {}, "before": {}})
        assert review.objects == ["person"]
        assert review.zones == ["driveway_approach"]
        assert review.severity == "alert"
        assert review.end_time == 100.0

    def test_summary(self) -> None:
        """Summary works with and without GenAI data."""
        # Without GenAI
        review = make_review()
        s = review.summary()
        assert s["review_id"] == "1773840946.10543-review1"
        assert s["camera"] == "driveway"
        assert s["objects"] == ["person"]
        assert s["genai"] is None

        # With GenAI
        review_genai = make_review(genai=make_genai())
        s2 = review_genai.summary()
        assert s2["genai"]["title"] == "Person and Vehicle in Driveway"
        assert s2["genai"]["threat_level"] == 1
        assert s2["genai"]["summary"] == "A person walked up the driveway as a car pulled in."


class TestProfileState:
    def test_last_sent_at_is_independent_dict(self) -> None:
        state1 = ProfileState()
        state2 = ProfileState()
        state1.last_sent_at["driveway"] = 100.0
        assert "driveway" not in state2.last_sent_at
