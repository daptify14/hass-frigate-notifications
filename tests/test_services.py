"""Tests for service registration and handlers."""

import copy
import json
from typing import Any
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.frigate_notifications.const import DOMAIN
from custom_components.frigate_notifications.review_history import ReviewHistory

from .conftest import get_profile_subentry_id, setup_integration
from .payloads import REVIEW_NEW_PAYLOAD, REVIEW_UPDATE_VERIFIED_PAYLOAD

pytestmark = pytest.mark.usefixtures("mqtt_mock_no_linger")


class TestServiceRegistration:
    """Tests for service registration."""

    async def test_services_idempotent(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Registering services twice does not raise."""
        await setup_integration(hass, mock_config_entry)
        from custom_components.frigate_notifications.services import register_services

        # Should not raise.
        register_services(hass)
        assert hass.services.has_service(DOMAIN, "silence_profile")


class TestSilenceProfileService:
    """Tests for the silence_profile service."""

    async def test_silence_profile_valid(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Silencing a valid profile activates the datetime entity."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        await hass.services.async_call(
            DOMAIN,
            "silence_profile",
            {"profile_id": sub_id, "duration": 15},
            blocking=True,
        )
        await hass.async_block_till_done()

        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]
        assert dt_entity.native_value is not None

        # Default duration also activates successfully.
        dt_entity.clear()
        await hass.services.async_call(
            DOMAIN,
            "silence_profile",
            {"profile_id": sub_id},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert dt_entity.native_value is not None

    async def test_silence_profile_invalid_raises(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Silencing an invalid profile_id raises ServiceValidationError with translation key."""
        await setup_integration(hass, mock_config_entry)

        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "silence_profile",
                {"profile_id": "nonexistent_profile"},
                blocking=True,
            )
        assert exc_info.value.translation_key == "profile_not_found"
        assert exc_info.value.translation_domain == DOMAIN

    async def test_silence_entity_error_raises_ha_error(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Exception in entity.activate() is wrapped in HomeAssistantError."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]
        with (
            patch.object(dt_entity, "activate", side_effect=HomeAssistantError("boom")),
            pytest.raises(HomeAssistantError) as exc_info,
        ):
            await hass.services.async_call(
                DOMAIN,
                "silence_profile",
                {"profile_id": sub_id, "duration": 15},
                blocking=True,
            )
        assert exc_info.value.translation_key == "silence_failed"
        assert exc_info.value.translation_domain == DOMAIN


class TestClearSilenceService:
    """Tests for the clear_silence service."""

    async def test_clear_silence_valid(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Clearing silence for a valid profile works."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        # First silence.
        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]
        dt_entity.activate()
        await hass.async_block_till_done()

        await hass.services.async_call(
            DOMAIN,
            "clear_silence",
            {"profile_id": sub_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert dt_entity.native_value is None

    async def test_clear_entity_error_raises_ha_error(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Exception in entity.clear() is wrapped in HomeAssistantError."""
        await setup_integration(hass, mock_config_entry)
        sub_id = get_profile_subentry_id(mock_config_entry)

        dt_entity = mock_config_entry.runtime_data.silence_datetimes[sub_id]
        with (
            patch.object(dt_entity, "clear", side_effect=HomeAssistantError("boom")),
            pytest.raises(HomeAssistantError) as exc_info,
        ):
            await hass.services.async_call(
                DOMAIN,
                "clear_silence",
                {"profile_id": sub_id},
                blocking=True,
            )
        assert exc_info.value.translation_key == "clear_silence_failed"
        assert exc_info.value.translation_domain == DOMAIN

    async def test_clear_silence_invalid_raises(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Clearing silence for invalid profile_id raises with translation key."""
        await setup_integration(hass, mock_config_entry)

        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "clear_silence",
                {"profile_id": "bad_id"},
                blocking=True,
            )
        assert exc_info.value.translation_key == "profile_not_found"
        assert exc_info.value.translation_domain == DOMAIN


def _profile_switch_entity_id(entry: MockConfigEntry) -> str:
    sub_id = get_profile_subentry_id(entry)
    return str(entry.runtime_data.enabled_switches[sub_id].entity_id)


def _new_on(camera: str, review_id: str) -> dict[str, Any]:
    payload = copy.deepcopy(REVIEW_NEW_PAYLOAD)
    payload["after"]["camera"] = camera
    payload["after"]["id"] = review_id
    return payload


async def _preview(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    response = await hass.services.async_call(
        DOMAIN, "preview_notification", data, blocking=True, return_response=True
    )
    assert response is not None
    return dict(response)


class TestPreviewNotificationService:
    """Tests for the preview_notification action."""

    async def test_preview_returns_rows_without_sending(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """The newest review replays into rows and no notify call is made."""
        await setup_integration(hass, mock_config_entry)
        notify_calls = async_mock_service(hass, "notify", "mobile_app_test_phone")
        history = mock_config_entry.runtime_data.review_history
        assert history is not None
        history.record(REVIEW_NEW_PAYLOAD, 1.0)
        history.record(REVIEW_UPDATE_VERIFIED_PAYLOAD, 2.0)

        response = await _preview(hass, {"entity_id": _profile_switch_entity_id(mock_config_entry)})

        assert response["filters"] == "none"
        (review,) = response["reviews"]
        assert review["review_id"] == REVIEW_NEW_PAYLOAD["after"]["id"]
        assert review["truncated"] is False
        first, second = review["rows"]
        assert first["outcome"] == "rendered"
        assert first["phase"] == "initial"
        assert first["service"] == "notify.mobile_app_test_phone"
        assert first["title"]
        assert isinstance(first["service_data"], dict)
        assert second["outcome"] == "rendered"
        assert second["phase"] == "update"
        json.dumps(response)
        assert notify_calls == []

    async def test_preview_with_filters_and_overrides(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Filters are labelled in the response and overrides reach the rendered rows."""
        await setup_integration(hass, mock_config_entry)
        history = mock_config_entry.runtime_data.review_history
        assert history is not None
        history.record(REVIEW_NEW_PAYLOAD, 1.0)

        response = await _preview(
            hass,
            {
                "entity_id": _profile_switch_entity_id(mock_config_entry),
                "run_filters": True,
                "title_template": "Custom {{ camera }}",
            },
        )
        assert response["filters"] == "evaluated_now"
        (row,) = response["reviews"][0]["rows"]
        assert row["title"] == "Custom driveway"

    async def test_preview_last_returns_newest_first_and_flags_truncation(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Several reviews come back newest first; a capped record is flagged."""
        await setup_integration(hass, mock_config_entry)
        history = ReviewHistory(max_steps=1)
        mock_config_entry.runtime_data.review_history = history
        history.record(_new_on("driveway", "older"), 1.0)
        older_update = copy.deepcopy(REVIEW_UPDATE_VERIFIED_PAYLOAD)
        older_update["after"]["id"] = "older"
        history.record(older_update, 2.0)
        history.record(_new_on("driveway", "newer"), 3.0)
        history.record(_new_on("backyard", "elsewhere"), 4.0)

        response = await _preview(
            hass, {"entity_id": _profile_switch_entity_id(mock_config_entry), "last": 5}
        )
        reviews = response["reviews"]
        assert [r["review_id"] for r in reviews] == ["newer", "older"]
        assert reviews[1]["truncated"] is True

    async def test_preview_review_id_must_be_on_profile_camera(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """An unknown id or one from another camera is rejected."""
        await setup_integration(hass, mock_config_entry)
        history = mock_config_entry.runtime_data.review_history
        assert history is not None
        history.record(_new_on("backyard", "elsewhere"), 1.0)
        entity_id = _profile_switch_entity_id(mock_config_entry)

        for review_id in ("elsewhere", "missing"):
            with pytest.raises(ServiceValidationError) as exc:
                await _preview(hass, {"entity_id": entity_id, "review_id": review_id})
            assert exc.value.translation_key == "review_not_found"

    async def test_preview_without_history_raises(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Empty history and disabled retention each raise a distinct error."""
        await setup_integration(hass, mock_config_entry)
        entity_id = _profile_switch_entity_id(mock_config_entry)

        with pytest.raises(ServiceValidationError) as exc:
            await _preview(hass, {"entity_id": entity_id})
        assert exc.value.translation_key == "no_review_history"

        mock_config_entry.runtime_data.review_history = None
        with pytest.raises(ServiceValidationError) as exc:
            await _preview(hass, {"entity_id": entity_id})
        assert exc.value.translation_key == "review_history_disabled"

    async def test_preview_rejects_non_profile_entity(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """An entity that is not a profile switch is reported as profile not found."""
        await setup_integration(hass, mock_config_entry)
        with pytest.raises(ServiceValidationError) as exc:
            await _preview(hass, {"entity_id": "switch.something_else"})
        assert exc.value.translation_key == "profile_not_found"
