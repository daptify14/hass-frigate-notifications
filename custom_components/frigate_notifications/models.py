"""Data models for Notifications for Frigate."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .enums import UpdateTrigger

if TYPE_CHECKING:
    from .enums import Lifecycle, Phase


@dataclass(frozen=True)
class GenAIData:
    """GenAI metadata from a review."""

    title: str = ""
    short_summary: str = ""
    scene: str = ""
    confidence: float = 0.0
    threat_level: int = 0
    other_concerns: tuple[str, ...] = ()
    time: str = ""

    @classmethod
    def from_metadata(cls, metadata: Mapping[str, Any]) -> GenAIData:
        """Create from review metadata dict."""
        raw_concerns = metadata.get("other_concerns")
        return cls(
            title=metadata.get("title", ""),
            short_summary=metadata.get("shortSummary", ""),
            scene=metadata.get("scene", ""),
            confidence=metadata.get("confidence", 0.0),
            threat_level=metadata.get("potential_threat_level", 0),
            other_concerns=tuple(raw_concerns) if raw_concerns else (),
            time=metadata.get("time", ""),
        )


@dataclass
class Review:
    """A Frigate review from frigate/reviews MQTT."""

    review_id: str
    camera: str
    start_time: float
    end_time: float | None = None
    severity: str = ""

    detection_ids: list[str] = field(default_factory=list)
    objects: list[str] = field(default_factory=list)
    sub_labels: list[str] = field(default_factory=list)
    zones: list[str] = field(default_factory=list)

    latest_detection_id: str = ""

    before_zones: list[str] = field(default_factory=list)
    before_objects: list[str] = field(default_factory=list)
    before_sub_labels: list[str] = field(default_factory=list)

    genai: GenAIData | None = None
    last_update: float = 0.0

    @classmethod
    def from_message(cls, payload: Mapping[str, Any]) -> Review:
        """Create the baseline for a review from any frigate/reviews message.

        Uses ``before`` when it describes the same review (so a review first seen
        on an update or end starts from the state Frigate had before that message),
        otherwise ``after``. Call ``apply_message`` with the same payload afterwards.
        """
        after = payload.get("after", {})
        before = payload.get("before")
        if isinstance(before, Mapping) and before.get("id") == after.get("id"):
            return cls.from_snapshot(before)
        return cls.from_snapshot(after)

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> Review:
        """Create from a single Frigate review snapshot."""
        data = snapshot.get("data", {})
        return cls(
            review_id=snapshot.get("id", ""),
            camera=snapshot.get("camera", ""),
            start_time=snapshot.get("start_time", 0.0),
            end_time=snapshot.get("end_time"),
            severity=snapshot.get("severity", ""),
            detection_ids=list(data.get("detections", [])),
            objects=list(data.get("objects", [])),
            sub_labels=list(data.get("sub_labels", [])),
            zones=list(data.get("zones", [])),
        )

    def update_from_review(self, payload: Mapping[str, Any]) -> None:
        """Update from a review update/end/genai MQTT payload.

        Populates before_* fields from payload["before"]["data"] BEFORE
        overwriting the after fields, so delta computation can see what changed.
        """
        before = payload.get("before", {})
        before_data = before.get("data", {})
        self.before_zones = list(before_data.get("zones", []))
        self.before_objects = list(before_data.get("objects", []))
        self.before_sub_labels = list(before_data.get("sub_labels", []))

        after = payload.get("after", {})
        data = after.get("data", {})
        self.end_time = after.get("end_time", self.end_time)
        self.severity = after.get("severity", self.severity)
        self.detection_ids = list(data.get("detections", self.detection_ids))
        self.objects = list(data.get("objects", self.objects))
        self.sub_labels = list(data.get("sub_labels", self.sub_labels))
        self.zones = list(data.get("zones", self.zones))

        metadata = data.get("metadata")
        if metadata:
            self.genai = GenAIData.from_metadata(metadata)

    def apply_message(self, payload: Mapping[str, Any]) -> list[str]:
        """Apply a message and return the detection ids it added.

        Tracks ``latest_detection_id`` so attachments can follow the newest detection.
        """
        prev_ids = set(self.detection_ids)
        self.update_from_review(payload)
        new_ids = [det_id for det_id in self.detection_ids if det_id not in prev_ids]
        if new_ids:
            self.latest_detection_id = new_ids[-1]
        return new_ids

    def summary(self) -> dict[str, Any]:
        """Return a summary dict for logging/debugging."""
        return {
            "review_id": self.review_id,
            "camera": self.camera,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "severity": self.severity,
            "objects": self.objects,
            "sub_labels": self.sub_labels,
            "zones": self.zones,
            "genai": {
                "title": self.genai.title,
                "summary": self.genai.short_summary,
                "threat_level": self.genai.threat_level,
            }
            if self.genai
            else None,
        }


@dataclass(frozen=True)
class ReviewSnapshot:
    """What a review has contained so far, as unordered sets."""

    zones: frozenset[str]
    objects: frozenset[str]
    sub_labels: frozenset[str]
    detection_ids: frozenset[str]

    @classmethod
    def of(cls, review: Review, previous: ReviewSnapshot | None = None) -> ReviewSnapshot:
        """Snapshot a review, keeping everything ``previous`` already held.

        Frigate rewrites objects and sub-labels per detection, so a value can leave
        the payload and return; accumulating stops a returning value counting as new.
        """
        current = cls(
            zones=frozenset(review.zones),
            objects=frozenset(review.objects),
            sub_labels=frozenset(review.sub_labels),
            detection_ids=frozenset(review.detection_ids),
        )
        if previous is None:
            return current
        return cls(
            zones=current.zones | previous.zones,
            objects=current.objects | previous.objects,
            sub_labels=current.sub_labels | previous.sub_labels,
            detection_ids=current.detection_ids | previous.detection_ids,
        )


def update_reasons(review: Review, baseline: ReviewSnapshot | None) -> frozenset[UpdateTrigger]:
    """Return the triggers that are true for a review measured against a baseline."""
    if baseline is None:
        return frozenset(UpdateTrigger)
    reasons: set[UpdateTrigger] = set()
    if set(review.zones) - baseline.zones:
        reasons.add(UpdateTrigger.ZONE)
    known_names = {s.lower() for s in baseline.sub_labels}
    new_names = {s.lower() for s in review.sub_labels} - known_names
    # Recognition is carried by the name, so person and person-verified are one type.
    known_types = {o.replace("-verified", "") for o in baseline.objects}
    new_types = {o.replace("-verified", "") for o in review.objects} - known_types
    if new_names or new_types:
        reasons.add(UpdateTrigger.SUBJECT)
    if set(review.detection_ids) - baseline.detection_ids:
        reasons.add(UpdateTrigger.DETECTION)
    return frozenset(reasons)


@dataclass(frozen=True)
class SentNotification:
    """What a profile last delivered, captured before the notify call is awaited."""

    sent_at: float
    review_id: str
    camera: str
    lifecycle: Lifecycle
    phase: Phase
    title: str
    message: str
    subtitle: str
    tag: str
    group: str
    click_url: str
    service: str
    objects: tuple[str, ...]
    zones: tuple[str, ...]
    sub_labels: tuple[str, ...]
    severity: str


@dataclass
class ReviewState:
    """Per-(profile, review) notification tracking state."""

    initial_sent: bool = False
    pending_task: asyncio.Task[Any] | None = field(default=None, repr=False)
    # Baselines for update triggers and added_* variables: what has been accepted for
    # dispatch, and what has actually been delivered.
    scheduled: ReviewSnapshot | None = None
    notified: ReviewSnapshot | None = None


@dataclass
class ProfileState:
    """Per-profile cooldown tracking state."""

    last_sent_at: dict[str, float] = field(default_factory=dict)
