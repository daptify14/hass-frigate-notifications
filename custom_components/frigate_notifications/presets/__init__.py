"""Built-in preset loaders for config flow selectors and profile seeding."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import voluptuous as vol
import yaml

from ..config import DEFAULT_PHASE_GENAI, DEFAULT_PHASE_INITIAL, DEFAULT_PHASE_UPDATE
from ..const import DOMAIN, VALID_ATTACHMENTS, VALID_INTERRUPTION_LEVELS, VALID_VIDEOS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

SUPPORTED_SCHEMA_VERSION = 1

PHASE_SCHEMA = vol.Schema(
    {
        vol.Optional("message_template"): str,
        vol.Optional("subtitle_template"): str,
        vol.Optional("emoji_message"): bool,
        vol.Optional("emoji_subtitle"): bool,
        vol.Optional("sound"): str,
        vol.Optional("volume"): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
        vol.Optional("interruption_level"): vol.In(VALID_INTERRUPTION_LEVELS),
        vol.Optional("attachment"): vol.In(VALID_ATTACHMENTS),
        vol.Optional("video"): vol.In(VALID_VIDEOS),
        vol.Optional("delay"): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=300.0)),
        vol.Optional("enabled"): bool,
        vol.Optional("critical"): bool,
        vol.Optional("use_latest_detection"): bool,
    },
    extra=vol.PREVENT_EXTRA,
)

PROFILE_DEFAULTS_SCHEMA = vol.Schema(
    {
        vol.Optional("tag"): str,
        vol.Optional("group"): str,
    },
    extra=vol.PREVENT_EXTRA,
)

PROFILE_PRESET_SCHEMA = vol.Schema(
    {
        vol.Required("schema_version"): vol.All(
            int, vol.Range(min=1, max=SUPPORTED_SCHEMA_VERSION)
        ),
        vol.Required("id"): str,
        vol.Required("version"): vol.All(int, vol.Range(min=1)),
        vol.Required("name"): str,
        vol.Required("summary"): str,
        vol.Optional("description"): str,
        vol.Optional("sort_order", default=99): int,
        vol.Optional("profile_defaults"): PROFILE_DEFAULTS_SCHEMA,
        vol.Required("phases"): vol.Schema(
            {
                vol.Required("initial"): PHASE_SCHEMA,
                vol.Optional("update"): PHASE_SCHEMA,
                vol.Optional("end"): PHASE_SCHEMA,
                vol.Optional("genai"): PHASE_SCHEMA,
            },
            extra=vol.PREVENT_EXTRA,
        ),
        vol.Optional("genai_disabled_overrides"): vol.Schema(
            {
                vol.Optional("initial"): PHASE_SCHEMA,
                vol.Optional("update"): PHASE_SCHEMA,
                vol.Optional("end"): PHASE_SCHEMA,
                vol.Optional("genai"): PHASE_SCHEMA,
            },
            extra=vol.PREVENT_EXTRA,
        ),
    },
    extra=vol.PREVENT_EXTRA,
)

TEMPLATE_OPTION_SCHEMA = vol.Schema(
    {
        vol.Optional("id"): str,
        vol.Required("value"): str,
        vol.Required("label"): str,
        vol.Optional("phases"): [str],
    },
    extra=vol.PREVENT_EXTRA,
)

TEMPLATE_PRESETS_SCHEMA = vol.Schema(
    {
        vol.Optional("content"): [TEMPLATE_OPTION_SCHEMA],
        vol.Optional("titles"): [TEMPLATE_OPTION_SCHEMA],
        vol.Optional("zone_phrases"): [TEMPLATE_OPTION_SCHEMA],
    },
    extra=vol.PREVENT_EXTRA,
)


def _flatten_phase_defaults(phase_name: str) -> dict[str, Any]:
    """Return current PhaseConfig defaults in subentry-storage format."""
    if phase_name == "initial":
        default = DEFAULT_PHASE_INITIAL
    elif phase_name == "update":
        default = DEFAULT_PHASE_UPDATE
    elif phase_name == "genai":
        default = DEFAULT_PHASE_GENAI
    else:
        return {}

    return {
        "message_template": default.content.message_template,
        "subtitle_template": default.content.subtitle_template,
        "emoji_message": default.content.emoji_message,
        "emoji_subtitle": default.content.emoji_subtitle,
        "sound": default.delivery.sound,
        "volume": default.delivery.volume,
        "interruption_level": str(default.delivery.interruption_level),
        "attachment": str(default.media.attachment),
        "video": default.media.video,
        "delay": default.delivery.delay,
        "enabled": default.delivery.enabled,
        "critical": default.delivery.critical,
        "use_latest_detection": default.media.use_latest_detection,
    }


@dataclass(frozen=True)
class TemplateOption:
    """One selectable template option."""

    id: str = ""
    value: str = ""
    label: str = ""
    phases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProfilePreset:
    """A profile preset loaded from YAML."""

    id: str
    version: int
    name: str
    summary: str
    description: str
    sort_order: int
    phases: dict[str, dict[str, Any]]
    profile_defaults: dict[str, str] = field(default_factory=dict)
    genai_disabled_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, validated: dict[str, Any]) -> ProfilePreset:
        """Build from validated YAML payload."""
        return cls(
            id=validated["id"],
            version=validated["version"],
            name=validated["name"],
            summary=validated["summary"],
            description=validated.get("description", ""),
            sort_order=validated.get("sort_order", 99),
            phases=validated.get("phases", {}),
            profile_defaults=validated.get("profile_defaults", {}),
            genai_disabled_overrides=validated.get("genai_disabled_overrides", {}),
        )

    def to_profile_data(self, *, genai_available: bool = True) -> dict[str, Any]:
        """Expand sparse preset data into stored profile-subentry shape."""
        data: dict[str, Any] = {"phases": {}}

        data["phases"]["initial"] = {
            **_flatten_phase_defaults("initial"),
            **self.phases.get("initial", {}),
        }

        resolved_update = {
            **_flatten_phase_defaults("update"),
            **self.phases.get("update", {}),
        }
        data["phases"]["update"] = resolved_update

        end_yaml = self.phases.get("end")
        if end_yaml is None:
            data["phases"]["end"] = dict(resolved_update)
        else:
            data["phases"]["end"] = {**resolved_update, **end_yaml}

        data["phases"]["genai"] = {
            **_flatten_phase_defaults("genai"),
            **self.phases.get("genai", {}),
        }

        if not genai_available:
            for phase_name, overrides in self.genai_disabled_overrides.items():
                data["phases"].setdefault(phase_name, {})
                data["phases"][phase_name].update(overrides)
            data["phases"]["genai"]["enabled"] = False

        if self.profile_defaults:
            data.update(self.profile_defaults)

        return data


_PROFILES_DIR = Path(__file__).parent / "profiles"
_TEMPLATES_FILE = Path(__file__).parent / "templates.yaml"


def _read_yaml(path: Path) -> Any:
    """Read one YAML file from disk."""
    return yaml.safe_load(path.read_text())


def load_profile_presets(hass: Any | None = None) -> list[ProfilePreset]:
    """Load built-in presets and optional user overrides."""
    presets: dict[str, ProfilePreset] = {}

    if _PROFILES_DIR.is_dir():
        for path in sorted(_PROFILES_DIR.glob("*.yaml")):
            validated = PROFILE_PRESET_SCHEMA(_read_yaml(path))
            preset = ProfilePreset.from_dict(validated)
            presets[preset.id] = preset

    if hass is not None:
        user_dir = Path(hass.config.path("frigate_notifications", "presets"))
        if user_dir.is_dir():
            for path in sorted(user_dir.glob("*.yaml")):
                raw: Any = None
                try:
                    raw = _read_yaml(path)
                    validated = PROFILE_PRESET_SCHEMA(raw)
                    preset = ProfilePreset.from_dict(validated)
                    presets[preset.id] = preset
                except vol.Invalid as err:
                    if (
                        isinstance(raw, dict)
                        and isinstance(raw.get("schema_version"), int)
                        and raw["schema_version"] > SUPPORTED_SCHEMA_VERSION
                    ):
                        _LOGGER.warning(
                            "Skipping preset %s: requires schema v%s, integration supports v%s",
                            path.name,
                            raw["schema_version"],
                            SUPPORTED_SCHEMA_VERSION,
                        )
                    else:
                        _LOGGER.warning("Skipping invalid preset %s: %s", path.name, err)
                except yaml.YAMLError as err:
                    _LOGGER.warning("Skipping preset %s (YAML parse error): %s", path.name, err)

    return sorted(presets.values(), key=lambda preset: (preset.sort_order, preset.name))


def load_template_presets() -> dict[str, list[TemplateOption]]:
    """Load built-in template selector options."""
    validated = TEMPLATE_PRESETS_SCHEMA(_read_yaml(_TEMPLATES_FILE))
    result: dict[str, list[TemplateOption]] = {}
    for category in ("content", "titles", "zone_phrases"):
        result[category] = [
            TemplateOption(
                id=item.get("id", ""),
                value=item["value"],
                label=item["label"],
                phases=tuple(item.get("phases", ())),
            )
            for item in validated.get(category, [])
        ]
    return result


def build_template_id_map(
    template_presets: dict[str, list[TemplateOption]],
) -> dict[str, str]:
    """Build a flat {id: jinja_value} map across ID-bearing categories."""
    result: dict[str, str] = {}
    for options in template_presets.values():
        for opt in options:
            if not opt.id:
                continue
            if opt.id in result:
                msg = f"Duplicate template ID: {opt.id!r}"
                raise vol.Invalid(msg)
            result[opt.id] = opt.value
    return result


async def async_ensure_preset_cache(hass: HomeAssistant) -> None:
    """Populate preset caches in hass.data once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if "profile_presets" not in domain_data:
        domain_data["profile_presets"] = await hass.async_add_executor_job(
            load_profile_presets, hass
        )
    if "template_presets" not in domain_data:
        domain_data["template_presets"] = await hass.async_add_executor_job(load_template_presets)
    if "template_id_map" not in domain_data:
        domain_data["template_id_map"] = build_template_id_map(domain_data["template_presets"])
