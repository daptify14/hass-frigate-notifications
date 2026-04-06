"""Typed read-only view of the Frigate config used by this integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@dataclass(frozen=True)
class FrigateCameraView:
    """Read-only view of one Frigate camera config."""

    name: str
    zones: tuple[str, ...]
    tracked_objects: tuple[str, ...]
    genai_enabled: bool


@dataclass(frozen=True)
class FrigateConfigView:
    """Read-only typed view of the Frigate config used by this integration."""

    entry_id: str
    cameras: dict[str, FrigateCameraView]
    topic_prefix: str

    def camera_names(self) -> set[str]:
        """Return available camera names."""
        return set(self.cameras)

    def get_camera(self, name: str) -> FrigateCameraView | None:
        """Return one camera view if present."""
        return self.cameras.get(name)

    def get_camera_zones(self, name: str) -> tuple[str, ...]:
        """Return zones for one camera or an empty tuple."""
        camera = self.get_camera(name)
        return camera.zones if camera is not None else ()

    def get_tracked_objects(self, name: str) -> tuple[str, ...]:
        """Return tracked objects for one camera or an empty tuple."""
        camera = self.get_camera(name)
        return camera.tracked_objects if camera is not None else ()

    def camera_supports_genai(self, name: str) -> bool:
        """Return whether a camera has GenAI enabled."""
        camera = self.get_camera(name)
        return camera.genai_enabled if camera is not None else False

    def any_genai_enabled(self) -> bool:
        """Return whether any camera has GenAI enabled."""
        return any(camera.genai_enabled for camera in self.cameras.values())


def get_frigate_config_view(hass: HomeAssistant, frigate_entry_id: str) -> FrigateConfigView | None:
    """Build a typed view over the Frigate config stored in hass.data."""
    raw = hass.data.get("frigate", {}).get(frigate_entry_id, {}).get("config")
    if not isinstance(raw, dict):
        return None

    raw_cameras = raw.get("cameras", {})
    if not isinstance(raw_cameras, dict):
        raw_cameras = {}

    cameras: dict[str, FrigateCameraView] = {}
    for name, cam_data in raw_cameras.items():
        if not isinstance(name, str):
            continue
        safe_cam = _safe_dict(cam_data)
        objects = _safe_dict(safe_cam.get("objects"))
        review = _safe_dict(safe_cam.get("review"))
        genai = _safe_dict(review.get("genai"))
        cameras[name] = FrigateCameraView(
            name=name,
            zones=_coerce_str_keys(safe_cam.get("zones")),
            tracked_objects=_coerce_str_list(objects.get("track")),
            genai_enabled=bool(genai.get("enabled", False)),
        )

    mqtt = _safe_dict(raw.get("mqtt"))
    topic_prefix = mqtt.get("topic_prefix", "frigate")
    if not isinstance(topic_prefix, str):
        topic_prefix = "frigate"

    return FrigateConfigView(entry_id=frigate_entry_id, cameras=cameras, topic_prefix=topic_prefix)


def _safe_dict(value: Any) -> dict[str, Any]:
    """Return value if it's a dict, otherwise empty dict."""
    return value if isinstance(value, dict) else {}


def _coerce_str_keys(value: Any) -> tuple[str, ...]:
    """Extract string keys from a dict (for zone dicts where keys are zone names)."""
    if not isinstance(value, dict):
        return ()
    return tuple(k for k in value if isinstance(k, str))


def _coerce_str_list(value: Any) -> tuple[str, ...]:
    """Normalize a list-like field into a tuple of strings."""
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))
