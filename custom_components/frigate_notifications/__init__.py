"""Notifications for Frigate — enriched push notifications for Frigate NVR reviews."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

from .actions import setup_action_listener
from .const import (
    CLEANUP_INTERVAL,
    DEBUG_SENSOR_KEY,
    DOMAIN,
    SILENCE_DATETIMES_KEY,
    SUBENTRY_TYPE_INTEGRATION,
    SUBENTRY_TYPE_PROFILE,
)
from .data import (
    FrigateNotificationsRuntimeData,
    build_runtime_config,
    get_frigate_config,
    get_integration_subentry_id,
    get_profile_device_identifiers,
)
from .dispatcher import NotificationDispatcher
from .filters import build_default_filter_chain
from .presets import async_ensure_preset_cache
from .processor import ReviewProcessor
from .repairs import (
    delete_all_issues_for_entry,
    sync_broken_camera_issues,
    sync_stale_zone_issues,
)
from .services import register_services

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceEntry

    from .data import FrigateNotificationsConfigEntry
    from .models import Review

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.DATETIME,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.SENSOR,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Notifications for Frigate from configuration.yaml."""
    hass.data.setdefault(DOMAIN, {})
    await async_ensure_preset_cache(hass)
    register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FrigateNotificationsConfigEntry) -> bool:
    """Set up Notifications for Frigate from a config entry."""
    frigate_entry_id = entry.data["frigate_entry_id"]
    try:
        frigate_config = get_frigate_config(hass, frigate_entry_id)
    except KeyError as err:
        msg = f"Frigate entry {frigate_entry_id} not ready"
        raise ConfigEntryNotReady(msg) from err

    sync_broken_camera_issues(hass, entry)
    sync_stale_zone_issues(hass, entry)

    # Before update listener to avoid reload loop.
    _ensure_integration_subentry(hass, entry)

    runtime_config = build_runtime_config(hass, entry)
    filter_chain = build_default_filter_chain()
    dispatcher = NotificationDispatcher(hass, runtime_config, filter_chain)

    def _on_review_message(msg_type: str, payload: dict[str, Any]) -> None:
        sensor = hass.data.get(DOMAIN, {}).get(f"{DEBUG_SENSOR_KEY}_{entry.entry_id}")
        if sensor is not None:
            sensor.update_from_review(msg_type, payload)

    def _fire(coro_fn: Callable[..., Any]) -> Callable[..., None]:
        """Wrap an async dispatcher method into a fire-and-forget callback."""

        def _callback(*args: Any) -> None:
            hass.async_create_task(coro_fn(*args))

        return _callback

    def _on_review_update(review: Review, _camera: str) -> None:
        hass.async_create_task(dispatcher.on_review_update(review))

    processor = ReviewProcessor(
        on_review_new=_fire(dispatcher.on_review_new),
        on_review_update=_on_review_update,
        on_review_end=_fire(dispatcher.on_review_end),
        on_genai=_fire(dispatcher.on_genai),
        on_review_complete=dispatcher.cleanup_review,
        on_review_message=_on_review_message,
    )

    topic_prefix = frigate_config.get("mqtt", {}).get("topic_prefix", "frigate")
    mqtt_topic = f"{topic_prefix}/reviews"

    entry.runtime_data = FrigateNotificationsRuntimeData(
        processor=processor,
        dispatcher=dispatcher,
        mqtt_topic=mqtt_topic,
        integration_subentry_id=get_integration_subentry_id(entry),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await mqtt.async_wait_for_mqtt_client(hass)

    async def _mqtt_message(msg: mqtt.ReceiveMessage) -> None:
        payload = msg.payload if isinstance(msg.payload, str) else msg.payload.decode()
        await processor.handle_review_message(payload)

    unsub_mqtt = await mqtt.async_subscribe(hass, mqtt_topic, _mqtt_message, qos=0)
    entry.async_on_unload(unsub_mqtt)

    unsub_actions = setup_action_listener(hass, entry, dispatcher)
    entry.async_on_unload(unsub_actions)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    def _cleanup(_now: Any) -> None:
        processor.cleanup_stale()

    unsub_cleanup = async_track_time_interval(hass, _cleanup, timedelta(seconds=CLEANUP_INTERVAL))
    entry.async_on_unload(unsub_cleanup)

    _LOGGER.debug(
        "Setup complete for %s: %d profiles, topic=%s",
        entry.title,
        sum(len(v) for v in runtime_config.profiles.values()),
        mqtt_topic,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Notifications for Frigate config entry."""
    domain_data = hass.data.get(DOMAIN, {})
    domain_data.pop(f"{DEBUG_SENSOR_KEY}_{entry.entry_id}", None)

    silence_map = hass.data.get(SILENCE_DATETIMES_KEY, {})
    for subentry in entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_TYPE_PROFILE:
            silence_map.pop(subentry.subentry_id, None)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Allow removal of a profile device by removing its subentry."""
    for subentry in list(entry.subentries.values()):
        if subentry.subentry_type != SUBENTRY_TYPE_PROFILE:
            continue
        identifiers = get_profile_device_identifiers(entry.entry_id, subentry.subentry_id)
        if identifiers & device_entry.identifiers:
            hass.config_entries.async_remove_subentry(entry, subentry.subentry_id)
            return True
    return False


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up repair issues when entry is fully removed."""
    delete_all_issues_for_entry(hass, entry)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _ensure_integration_subentry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ensure an integration-type subentry exists for integration-level entities."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_TYPE_INTEGRATION:
            return

    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType({}),
            subentry_type=SUBENTRY_TYPE_INTEGRATION,
            title="Integration",
            unique_id=f"{entry.entry_id}_integration",
        ),
    )
