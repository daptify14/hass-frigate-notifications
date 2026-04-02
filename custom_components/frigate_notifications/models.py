"""Data models for Notifications for Frigate."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


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
    def from_review_mqtt(cls, payload: Mapping[str, Any]) -> Review:
        """Create from frigate/reviews MQTT payload (type: new)."""
        after = payload.get("after", {})
        data = after.get("data", {})
        return cls(
            review_id=after.get("id", ""),
            camera=after.get("camera", ""),
            start_time=after.get("start_time", 0.0),
            end_time=after.get("end_time"),
            severity=after.get("severity", ""),
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


@dataclass
class ReviewState:
    """Per-(profile, review) notification tracking state."""

    initial_sent: bool = False
    pending_task: asyncio.Task | None = field(default=None, repr=False)


@dataclass
class ProfileState:
    """Per-profile cooldown tracking state."""

    last_sent_at: dict[str, float] = field(default_factory=dict)
