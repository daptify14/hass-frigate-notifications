"""Tests for the extracted assemble_notification and deliver_notification functions."""

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.frigate_notifications.config import PhaseContent
from custom_components.frigate_notifications.dispatcher import (
    assemble_notification,
    deliver_notification,
)
from custom_components.frigate_notifications.enums import Lifecycle, Phase
from custom_components.frigate_notifications.models import ReviewState

from .factories import make_dispatch_request, make_genai, make_phase, make_profile, make_review


class TestAssembleNotification:
    async def test_assemble_basic_fields_populated(self, hass: HomeAssistant) -> None:
        """Basic assembly produces a RenderedNotification with all fields set."""
        rendered = assemble_notification(make_dispatch_request(hass))
        assert rendered.title
        assert rendered.message
        assert rendered.phase_name == Phase.INITIAL
        assert rendered.critical is False
        assert rendered.alert_once_silent is False
        assert rendered.ctx
        assert "detection_id" in rendered.attachment_ctx
        assert "access_token" in rendered.action_ctx

    async def test_assemble_genai_title_prefix_applied(self, hass: HomeAssistant) -> None:
        """GenAI title prefix is prepended when conditions are met."""
        rendered = assemble_notification(
            make_dispatch_request(
                hass,
                profile=make_profile(title_genai_prefixes={0: "Info", 2: "ALERT"}),
                review=make_review(genai=make_genai(threat_level=3)),
                phase=Phase.GENAI,
                lifecycle=Lifecycle.GENAI,
                is_genai=True,
                is_initial=False,
            )
        )
        assert rendered.title.startswith("ALERT ")

    async def test_assemble_genai_prefix_skipped_when_disabled(self, hass: HomeAssistant) -> None:
        """GenAI prefix is not applied when title_prefix_enabled is False."""
        rendered = assemble_notification(
            make_dispatch_request(
                hass,
                profile=make_profile(title_genai_prefixes={0: "ALERT"}),
                review=make_review(genai=make_genai(threat_level=5)),
                phase_config=make_phase(content=PhaseContent(title_prefix_enabled=False)),
                phase=Phase.GENAI,
                lifecycle=Lifecycle.GENAI,
                is_genai=True,
                is_initial=False,
            )
        )
        assert not rendered.title.startswith("ALERT ")

    async def test_assemble_alert_once_silent_on_subsequent(self, hass: HomeAssistant) -> None:
        """Alert-once marks subsequent non-critical dispatches as silent."""
        rendered = assemble_notification(
            make_dispatch_request(
                hass,
                profile=make_profile(alert_once=True),
                review_state=ReviewState(initial_sent=True),
                is_initial=False,
                phase=Phase.UPDATE,
                lifecycle=Lifecycle.UPDATE,
            )
        )
        assert rendered.alert_once_silent is True

    async def test_assemble_alert_once_not_silent_on_initial(self, hass: HomeAssistant) -> None:
        """Alert-once does not silence the initial dispatch."""
        rendered = assemble_notification(
            make_dispatch_request(
                hass,
                profile=make_profile(alert_once=True),
                review_state=ReviewState(initial_sent=False),
                is_initial=True,
            )
        )
        assert rendered.alert_once_silent is False


class TestDeliverNotification:
    async def test_deliver_calls_service(self, hass: HomeAssistant) -> None:
        """Successful delivery calls the HA notify service."""
        notify_calls = async_mock_service(hass, "notify", "mobile_app_test_phone")
        req = make_dispatch_request(hass)
        rendered = assemble_notification(req)
        result = await deliver_notification(hass, req.profile, req.review, rendered)
        assert result is True
        assert len(notify_calls) == 1

    async def test_deliver_no_target_returns_false(
        self, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Empty notify_target returns False and logs a warning."""
        req = make_dispatch_request(hass, profile=make_profile(notify_target=""))
        rendered = assemble_notification(req)
        result = await deliver_notification(hass, req.profile, req.review, rendered)
        assert result is False
        assert "No notify target" in caplog.text
