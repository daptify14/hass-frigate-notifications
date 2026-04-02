"""Tests for phase configuration dataclasses."""

from custom_components.frigate_notifications.config import (
    DEFAULT_PHASE_END,
    DEFAULT_PHASE_GENAI,
    DEFAULT_PHASE_INITIAL,
    DEFAULT_PHASE_UPDATE,
)
from custom_components.frigate_notifications.const import DEFAULT_MESSAGE_TEMPLATE
from custom_components.frigate_notifications.enums import AttachmentType, InterruptionLevel


class TestDefaultPhases:
    def test_initial_defaults(self) -> None:
        p = DEFAULT_PHASE_INITIAL
        assert p.content.message_template == DEFAULT_MESSAGE_TEMPLATE
        assert p.content.subtitle_template == "merged_subjects"
        assert p.delivery.sound == "default"
        assert p.delivery.volume == 1.0
        assert p.delivery.interruption_level == InterruptionLevel.ACTIVE
        assert p.delivery.delay == 0.0
        assert p.media.attachment == AttachmentType.SNAPSHOT_CROPPED

    def test_update_defaults(self) -> None:
        p = DEFAULT_PHASE_UPDATE
        assert p.delivery.sound == "none"
        assert p.delivery.volume == 0.0
        assert p.media.attachment == AttachmentType.REVIEW_GIF
        assert p.media.use_latest_detection is True
        assert p.content.subtitle_template == "merged_subjects"

    def test_end_defaults(self) -> None:
        p = DEFAULT_PHASE_END
        assert p.delivery.sound == "none"
        assert p.delivery.volume == 0.0
        assert p.delivery.delay == 5.0
        assert p.media.attachment == AttachmentType.REVIEW_GIF
        assert p.media.use_latest_detection is True

    def test_genai_defaults(self) -> None:
        p = DEFAULT_PHASE_GENAI
        assert p.content.message_template == "genai_summary"
        assert p.content.emoji_message is False
        assert p.delivery.interruption_level == InterruptionLevel.PASSIVE
        assert p.delivery.sound == "default"
        assert p.delivery.volume == 1.0
        assert p.media.attachment == AttachmentType.REVIEW_GIF
        assert p.media.use_latest_detection is True
