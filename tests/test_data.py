"""Tests for data module — runtime config assembly."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.frigate_notifications.config import (
    DEFAULT_PHASE_END,
    DEFAULT_PHASE_GENAI,
    DEFAULT_PHASE_INITIAL,
    DEFAULT_PHASE_UPDATE,
    PhaseDelivery,
)
from custom_components.frigate_notifications.const import (
    DEFAULT_EMOJI_MAP,
    DEFAULT_PHASE_EMOJI_MAP,
    DEFAULT_TITLE_GENAI_PREFIXES,
)
from custom_components.frigate_notifications.data import (
    _build_global_genai_prefixes,
    _build_phases,
    _expand_urgency,
    build_emoji_map,
    build_phase_emoji_map,
    build_runtime_config,
    get_frigate_camera_device,
    resolve_guard_entity,
    resolve_presence,
    resolve_state_filter,
    resolve_time_filter,
)
from custom_components.frigate_notifications.enums import (
    AttachmentType,
    GuardMode,
    Phase,
    Provider,
    RecognitionMode,
    Severity,
    TimeFilterMode,
)
from custom_components.frigate_notifications.providers.models import (
    AndroidTvConfig,
    MobileAppConfig,
)

from .factories import make_phase, make_profile


@pytest.mark.parametrize(
    ("profile_data", "global_opts", "expected_mode", "expected_start", "expected_end"),
    [
        (
            {},
            {
                "shared_time_filter_mode": "notify_only_during",
                "shared_time_filter_start": "08:00",
                "shared_time_filter_end": "22:00",
            },
            TimeFilterMode.ONLY_DURING,
            "08:00",
            "22:00",
        ),
        (
            {
                "time_filter_override": "custom",
                "time_filter_mode": "do_not_notify_during",
                "time_filter_start": "23:00",
                "time_filter_end": "06:00",
            },
            {},
            TimeFilterMode.NOT_DURING,
            "23:00",
            "06:00",
        ),
        (
            {"time_filter_override": "disabled"},
            {"shared_time_filter_mode": "notify_only_during"},
            TimeFilterMode.DISABLED,
            "",
            "",
        ),
        (
            {},
            {},
            TimeFilterMode.DISABLED,
            "",
            "",
        ),
    ],
    ids=["inherit-uses-global", "custom-uses-profile", "disabled", "missing-defaults-to-inherit"],
)
def test_resolve_time_filter(
    profile_data: dict,
    global_opts: dict,
    expected_mode: TimeFilterMode,
    expected_start: str,
    expected_end: str,
) -> None:
    mode, start, end = resolve_time_filter(profile_data, global_opts)
    assert mode == expected_mode
    assert start == expected_start
    assert end == expected_end


@pytest.mark.parametrize(
    ("profile_data", "global_opts", "expected_mode", "expected_entity"),
    [
        (
            {},
            {"shared_guard_entity": "input_boolean.guard"},
            GuardMode.INHERIT,
            "input_boolean.guard",
        ),
        (
            {"guard_mode": "custom", "guard_entity": "input_boolean.profile_guard"},
            {},
            GuardMode.CUSTOM,
            "input_boolean.profile_guard",
        ),
        (
            {"guard_mode": "disabled"},
            {},
            GuardMode.DISABLED,
            None,
        ),
    ],
    ids=["inherit-uses-global", "custom-uses-profile", "disabled"],
)
def test_resolve_guard_entity(
    profile_data: dict,
    global_opts: dict,
    expected_mode: GuardMode,
    expected_entity: str | None,
) -> None:
    mode, entity = resolve_guard_entity(profile_data, global_opts)
    assert mode == expected_mode
    assert entity == expected_entity


@pytest.mark.parametrize(
    ("profile_data", "global_opts", "expected"),
    [
        (
            {},
            {"shared_presence_entities": ["person.alice", "person.bob"]},
            ("person.alice", "person.bob"),
        ),
        ({"presence_mode": "disabled"}, {"shared_presence_entities": ["person.x"]}, ()),
        (
            {"presence_mode": "custom", "presence_entities": ["person.alice"]},
            {"shared_presence_entities": ["person.bob"]},
            ("person.alice",),
        ),
        (
            {"presence_mode": "custom", "presence_entities": []},
            {"shared_presence_entities": ["person.bob"]},
            (),
        ),
    ],
    ids=[
        "inherit-uses-global",
        "disabled",
        "custom-uses-profile-entities",
        "custom-empty-returns-empty",
    ],
)
def test_resolve_presence(
    profile_data: dict,
    global_opts: dict,
    expected: tuple,
) -> None:
    assert resolve_presence(profile_data, global_opts) == expected


@pytest.mark.parametrize(
    ("profile_data", "global_opts", "expected_entity", "expected_states"),
    [
        (
            {},
            {"shared_state_entity": "sensor.mode", "shared_state_filter_states": ["home", "away"]},
            "sensor.mode",
            ("home", "away"),
        ),
        (
            {
                "state_filter_mode": "custom",
                "state_entity": "sensor.profile_mode",
                "state_filter_states": ["armed"],
            },
            {},
            "sensor.profile_mode",
            ("armed",),
        ),
        (
            {"state_filter_mode": "disabled"},
            {},
            None,
            (),
        ),
    ],
    ids=["inherit-uses-global", "custom-uses-profile", "disabled"],
)
def test_resolve_state_filter(
    profile_data: dict,
    global_opts: dict,
    expected_entity: str | None,
    expected_states: tuple,
) -> None:
    entity, states = resolve_state_filter(profile_data, global_opts)
    assert entity == expected_entity
    assert states == expected_states


class TestBuildEmojiMap:
    """Tests for build_emoji_map."""

    def test_default_only(self) -> None:
        """No overrides returns DEFAULT_EMOJI_MAP."""
        result = build_emoji_map({})
        assert result == DEFAULT_EMOJI_MAP

    def test_global_overrides_default(self) -> None:
        """Global emoji_map overrides default for same key."""
        result = build_emoji_map({"emoji_map": {"person": "G"}})
        assert result["person"] == "G"
        assert result["car"] == DEFAULT_EMOJI_MAP["car"]


class TestBuildPhaseEmojiMap:
    """Tests for build_phase_emoji_map."""

    def test_default_only(self) -> None:
        """No overrides returns DEFAULT_PHASE_EMOJI_MAP."""
        result = build_phase_emoji_map({})
        assert result == DEFAULT_PHASE_EMOJI_MAP

    def test_global_overrides_merge(self) -> None:
        """Global phase_emoji_map overrides one key, others unchanged."""
        result = build_phase_emoji_map({"phase_emoji_map": {"initial": "X"}})
        assert result["initial"] == "X"
        assert result["update"] == DEFAULT_PHASE_EMOJI_MAP["update"]
        assert result["end"] == DEFAULT_PHASE_EMOJI_MAP["end"]
        assert result["genai"] == DEFAULT_PHASE_EMOJI_MAP["genai"]

    def test_enable_emojis_false_suppresses(self) -> None:
        """enable_emojis=False returns all empty strings."""
        result = build_phase_emoji_map({"enable_emojis": False})
        assert all(v == "" for v in result.values())
        assert set(result.keys()) == set(DEFAULT_PHASE_EMOJI_MAP.keys())


class TestBuildEmojiMapDisabled:
    """Tests for emoji maps when globally disabled."""

    def test_build_emoji_map_disabled_returns_empty(self) -> None:
        """build_emoji_map returns empty dict when enable_emojis=False."""
        result = build_emoji_map({"enable_emojis": False})
        assert result == {}

    def test_build_phase_emoji_map_disabled_returns_blank_values(self) -> None:
        """build_phase_emoji_map returns blank values when enable_emojis=False."""
        result = build_phase_emoji_map({"enable_emojis": False})
        assert all(v == "" for v in result.values())
        assert set(result.keys()) == set(DEFAULT_PHASE_EMOJI_MAP.keys())

    def test_build_emoji_map_enabled_merges_custom(self) -> None:
        """Custom emoji_map overrides merge correctly when enabled."""
        result = build_emoji_map({"enable_emojis": True, "emoji_map": {"person": "X"}})
        assert result["person"] == "X"
        assert result["car"] == DEFAULT_EMOJI_MAP["car"]


class TestBuildGlobalGenaiPrefixes:
    """Tests for _build_global_genai_prefixes two-tier merge."""

    def test_default_only(self) -> None:
        """No global overrides returns system defaults."""
        result = _build_global_genai_prefixes({})
        assert result == DEFAULT_TITLE_GENAI_PREFIXES

    def test_global_overrides_default(self) -> None:
        """Global prefixes override system defaults."""
        result = _build_global_genai_prefixes({"title_genai_prefixes": {1: "X "}})
        assert result[1] == "X "
        assert result[2] == DEFAULT_TITLE_GENAI_PREFIXES[2]

    def test_global_level_0_stored_when_set(self) -> None:
        """Level 0 is included when explicitly set in global options."""
        result = _build_global_genai_prefixes({"title_genai_prefixes": {0: "INFO "}})
        assert result[0] == "INFO "
        assert result[1] == DEFAULT_TITLE_GENAI_PREFIXES[1]


class TestProfileRuntime:
    """Tests for ProfileRuntime behavior."""

    def test_get_phase_explicit(self) -> None:
        """get_phase returns explicit phase when configured."""
        custom = make_phase(delivery=PhaseDelivery(sound="custom"))
        profile = make_profile(phases={Phase.INITIAL: custom})
        assert profile.get_phase(Phase.INITIAL) is custom

    def test_get_phase_end_inherits_update(self) -> None:
        """get_phase END falls back to UPDATE when END not configured."""
        update_phase = make_phase(delivery=PhaseDelivery(sound="update_sound"))
        profile = make_profile(phases={Phase.UPDATE: update_phase})
        assert profile.get_phase(Phase.END) is update_phase

    def test_get_phase_defaults_when_unconfigured(self) -> None:
        """get_phase returns defaults when no phases configured."""
        profile = make_profile(phases={})
        assert profile.get_phase(Phase.INITIAL) == DEFAULT_PHASE_INITIAL
        assert profile.get_phase(Phase.UPDATE) == DEFAULT_PHASE_UPDATE
        assert profile.get_phase(Phase.END) == DEFAULT_PHASE_END
        assert profile.get_phase(Phase.GENAI) == DEFAULT_PHASE_GENAI

    def test_get_phase_end_default_when_no_update(self) -> None:
        """get_phase END returns DEFAULT_PHASE_END when neither END nor UPDATE configured."""
        profile = make_profile(phases={Phase.INITIAL: make_phase()})
        assert profile.get_phase(Phase.END) == DEFAULT_PHASE_END


class TestBuildPhases:
    """Tests for _build_phases."""

    def test_composed_phase_config_from_raw_data(self) -> None:
        """Raw data produces composed PhaseConfig with sub-configs."""
        data = {
            "initial": {
                "sound": "custom_sound",
                "volume": 0.8,
                "message_template": "{{ object }} detected",
                "attachment": "snapshot_bbox",
            }
        }
        result = _build_phases(data)
        assert Phase.INITIAL in result
        pc = result[Phase.INITIAL]
        assert pc.delivery.sound == "custom_sound"
        assert pc.delivery.volume == 0.8
        assert pc.content.message_template == "{{ object }} detected"
        assert pc.media.attachment == AttachmentType.SNAPSHOT_BBOX

    def test_missing_keys_use_sub_config_defaults(self) -> None:
        """Missing keys in raw data use sub-config defaults."""
        result = _build_phases({"update": {}})
        pc = result[Phase.UPDATE]
        assert pc.content.message_template == ""
        assert pc.delivery.sound == "default"
        assert pc.delivery.volume == 1.0
        assert pc.media.attachment == AttachmentType.SNAPSHOT_CROPPED
        assert pc.tv.fontsize == "medium"

    def test_all_four_phases_built(self) -> None:
        """All four phase keys are converted to Phase enum keys."""
        data = {
            "initial": {"sound": "a"},
            "update": {"sound": "b"},
            "end": {"sound": "c"},
            "genai": {"sound": "d"},
        }
        result = _build_phases(data)
        assert set(result.keys()) == {
            Phase.INITIAL,
            Phase.UPDATE,
            Phase.END,
            Phase.GENAI,
        }
        assert result[Phase.INITIAL].delivery.sound == "a"
        assert result[Phase.GENAI].delivery.sound == "d"

    def test_tv_overlay_fields_mapped(self) -> None:
        """Android TV overlay fields are correctly mapped."""
        data = {
            "initial": {
                "tv_fontsize": "large",
                "tv_position": "center",
                "tv_duration": 10,
                "tv_transparency": "50%",
                "tv_interrupt": True,
                "tv_timeout": 60,
                "tv_color": "#FF0000",
            }
        }
        result = _build_phases(data)
        tv = result[Phase.INITIAL].tv
        assert tv.fontsize == "large"
        assert tv.position == "center"
        assert tv.duration == 10
        assert tv.transparency == "50%"
        assert tv.interrupt is True
        assert tv.timeout == 60
        assert tv.color == "#FF0000"


class TestBuildPhasesAndroidDelivery:
    """Tests for per-phase Android delivery fields in _build_phases."""

    def test_android_fields_read_from_phase_data(self) -> None:
        """Android urgency fields are read from phase data."""
        data = {"initial": {"importance": "max", "priority": "low", "ttl": 30}}
        result = _build_phases(data)
        d = result[Phase.INITIAL].delivery
        assert d.importance == "max"
        assert d.priority == "low"
        assert d.ttl == 30


class TestExpandUrgency:
    """Tests for urgency expansion to concrete platform fields."""

    def test_no_urgency_returns_defaults(self) -> None:
        """Empty urgency returns standard defaults."""
        result = _expand_urgency({})
        assert result["importance"] == "high"
        assert result["priority"] == "high"
        assert result["ttl"] == 0
        assert result["sound"] == "default"

    def test_urgent_expands_correctly(self) -> None:
        """urgency=urgent expands to time-sensitive iOS and high Android."""
        result = _expand_urgency({"urgency": "urgent"})
        assert result["sound"] == "default"
        assert result["interruption_level"] == "time-sensitive"
        assert result["importance"] == "high"
        assert result["priority"] == "high"
        assert result["ttl"] == 0

    def test_quiet_expands_correctly(self) -> None:
        """urgency=quiet expands to passive iOS and low Android."""
        result = _expand_urgency({"urgency": "quiet"})
        assert result["sound"] == "none"
        assert result["interruption_level"] == "passive"
        assert result["importance"] == "low"
        assert result["priority"] == "default"

    def test_normal_expands_correctly(self) -> None:
        """urgency=normal expands to active iOS and default Android."""
        result = _expand_urgency({"urgency": "normal"})
        assert result["sound"] == "default"
        assert result["interruption_level"] == "active"
        assert result["importance"] == "default"
        assert result["priority"] == "default"

    def test_explicit_field_overrides_urgency(self) -> None:
        """Explicit concrete field takes precedence over urgency expansion."""
        result = _expand_urgency({"urgency": "urgent", "importance": "low"})
        assert result["importance"] == "low"
        assert result["priority"] == "high"


class TestFrigateHelpers:
    """Tests for Frigate integration helpers."""

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_get_camera_device_returns_device(self, mock_dr_get: MagicMock) -> None:
        """get_frigate_camera_device returns device for valid camera."""
        hass = MagicMock()
        hass.data = {"frigate": {"fid": {"config": {"cameras": {"cam1": {}}}}}}
        mock_device = MagicMock()
        mock_dr_get.return_value.async_get_device.return_value = mock_device
        result = get_frigate_camera_device(hass, "fid", "cam1")
        assert result is mock_device

    def test_get_camera_device_returns_none_for_missing(self) -> None:
        """get_frigate_camera_device returns None for camera not in config."""
        hass = MagicMock()
        hass.data = {"frigate": {"fid": {"config": {"cameras": {"cam1": {}}}}}}
        result = get_frigate_camera_device(hass, "fid", "cam_missing")
        assert result is None


def _mock_hass(
    cameras: list[str] | None = None,
    external_url: str = "https://ha.test",
    frigate_entries: list[Any] | None = None,
) -> MagicMock:
    """Create a mock hass with Frigate data."""
    hass = MagicMock()
    hass.data = {
        "frigate": {
            "frigate_test_id": {"config": {"cameras": {c: {} for c in (cameras or ["driveway"])}}}
        }
    }
    hass.config.external_url = external_url
    hass.config_entries.async_entries.return_value = frigate_entries or []
    entries_by_id = {fe.entry_id: fe for fe in (frigate_entries or [])}
    hass.config_entries.async_get_entry.side_effect = entries_by_id.get
    return hass


def _mock_entry(
    global_opts: dict[str, Any] | None = None,
    profiles: list[dict[str, Any]] | None = None,
    entry_data: dict[str, Any] | None = None,
) -> Any:
    """Create a mock config entry with profile subentries."""
    entry = SimpleNamespace(
        entry_id="test_entry_id",
        data=entry_data or {"frigate_entry_id": "frigate_test_id"},
        options=global_opts or {},
        subentries={},
    )
    for i, profile_data in enumerate(profiles or []):
        se_id = f"profile_{i}"
        entry.subentries[se_id] = SimpleNamespace(
            subentry_id=se_id,
            subentry_type="profile",
            data=profile_data,
        )
    return entry


def _minimal_profile(cameras: list[str] | None = None, **overrides: Any) -> dict[str, Any]:
    """Return minimal profile subentry data."""
    data: dict[str, Any] = {
        "name": "Test Profile",
        "cameras": cameras or ["driveway"],
        "provider": "apple",
    }
    data.update(overrides)
    return data


class TestBuildRuntimeConfig:
    """Integration tests for build_runtime_config."""

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_single_profile_built(self, mock_dr: MagicMock) -> None:
        """Single profile subentry produces one ProfileRuntime."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(profiles=[_minimal_profile()])
        result = build_runtime_config(hass, entry)
        assert "driveway" in result.profiles
        assert len(result.profiles["driveway"]) == 1
        p = result.profiles["driveway"][0]
        assert p.cameras == ("driveway",)
        assert p.provider == Provider.APPLE
        assert p.severity == Severity.ALERT

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_missing_camera_skipped(self, mock_dr: MagicMock) -> None:
        """Profile for missing camera is skipped with warning."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass(cameras=["backyard"])
        entry = _mock_entry(profiles=[_minimal_profile(cameras=["driveway"])])
        result = build_runtime_config(hass, entry)
        assert "driveway" not in result.profiles

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_cooldown_override_takes_precedence(self, mock_dr: MagicMock) -> None:
        """Profile cooldown_override takes precedence over global."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(
            global_opts={"cooldown_seconds": 60},
            profiles=[_minimal_profile(cooldown_override=120)],
        )
        result = build_runtime_config(hass, entry)
        assert result.profiles["driveway"][0].cooldown_seconds == 120

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_cooldown_inherits_from_global(self, mock_dr: MagicMock) -> None:
        """Profile without cooldown_override inherits from global."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(
            global_opts={"cooldown_seconds": 45},
            profiles=[_minimal_profile()],
        )
        result = build_runtime_config(hass, entry)
        assert result.profiles["driveway"][0].cooldown_seconds == 45

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_notify_target_from_device_id(self, mock_dr: MagicMock) -> None:
        """Device ID resolved to notify.mobile_app_{slugify(name)}."""
        mock_device = MagicMock()
        mock_device.name = "Test Phone"
        mock_dr.return_value.async_get.return_value = mock_device
        hass = _mock_hass()
        entry = _mock_entry(profiles=[_minimal_profile(notify_device="device_123")])
        result = build_runtime_config(hass, entry)
        assert result.profiles["driveway"][0].notify_target == ("notify.mobile_app_test_phone")

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_notify_target_from_service_name(self, mock_dr: MagicMock) -> None:
        """Fallback to notify_service when no device ID."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(profiles=[_minimal_profile(notify_service="notify.my_service")])
        result = build_runtime_config(hass, entry)
        assert result.profiles["driveway"][0].notify_target == "notify.my_service"

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_zone_aliases_from_global(self, mock_dr: MagicMock) -> None:
        """Zone aliases resolved from global options for camera."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(
            global_opts={
                "zone_aliases": {
                    "driveway": {"front_zone": "Front"},
                    "backyard": {"back_zone": "Back"},
                }
            },
            profiles=[_minimal_profile()],
        )
        result = build_runtime_config(hass, entry)
        assert result.profiles["driveway"][0].zone_aliases == {"front_zone": "Front"}

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_sub_label_overrides_from_global(self, mock_dr: MagicMock) -> None:
        """Sub-label overrides come from global options only."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(
            global_opts={"sub_label_overrides": {"Alice": "A", "Bob": "B"}},
            profiles=[_minimal_profile()],
        )
        result = build_runtime_config(hass, entry)
        overrides = result.profiles["driveway"][0].sub_label_overrides
        assert overrides == {"Alice": "A", "Bob": "B"}

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_initial_delay_from_global(self, mock_dr: MagicMock) -> None:
        """RuntimeConfig.initial_delay comes from global options."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(
            global_opts={"initial_delay": 2.5},
            profiles=[_minimal_profile()],
        )
        result = build_runtime_config(hass, entry)
        assert result.initial_delay == 2.5

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_android_tv_provider_config(self, mock_dr: MagicMock) -> None:
        """android_tv provider produces AndroidTvConfig."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(profiles=[_minimal_profile(provider="android_tv")])
        result = build_runtime_config(hass, entry)
        assert isinstance(result.profiles["driveway"][0].provider_config, AndroidTvConfig)

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_mobile_app_provider_config(self, mock_dr: MagicMock) -> None:
        """iOS provider produces MobileAppConfig with overrides."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(
            profiles=[
                _minimal_profile(
                    android_channel="alerts",
                    android_sticky=True,
                )
            ]
        )
        result = build_runtime_config(hass, entry)
        pc = result.profiles["driveway"][0].provider_config
        assert isinstance(pc, MobileAppConfig)
        assert pc.channel == "alerts"
        assert pc.sticky is True

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_non_profile_subentries_skipped(self, mock_dr: MagicMock) -> None:
        """Subentries with type != 'profile' are skipped."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(profiles=[_minimal_profile()])
        # Add a non-profile subentry
        entry.subentries["integration_sub"] = SimpleNamespace(
            subentry_id="integration_sub",
            subentry_type="integration",
            data={"some": "data"},
        )
        result = build_runtime_config(hass, entry)
        assert len(result.profiles["driveway"]) == 1

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_phases_built_with_enum_keys(self, mock_dr: MagicMock) -> None:
        """Profile phases are keyed by Phase enum."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(
            profiles=[
                _minimal_profile(phases={"initial": {"sound": "chime"}, "end": {"delay": 10.0}})
            ]
        )
        result = build_runtime_config(hass, entry)
        p = result.profiles["driveway"][0]
        assert Phase.INITIAL in p.phases
        assert Phase.END in p.phases
        assert p.phases[Phase.INITIAL].delivery.sound == "chime"
        assert p.phases[Phase.END].delivery.delay == 10.0

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_notify_target_device_not_found_returns_empty(self, mock_dr: MagicMock) -> None:
        """Missing device in registry returns empty notify target."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(profiles=[_minimal_profile(notify_device="bad_id")])
        result = build_runtime_config(hass, entry)
        assert result.profiles["driveway"][0].notify_target == ""

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_title_template_override_from_profile(self, mock_dr: MagicMock) -> None:
        """Profile-level title_template takes precedence over global."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(
            global_opts={"title_template": "Global Title"},
            profiles=[_minimal_profile(title_template="Profile Title")],
        )
        result = build_runtime_config(hass, entry)
        assert result.profiles["driveway"][0].title_template == "Profile Title"

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_title_template_inherits_from_global(self, mock_dr: MagicMock) -> None:
        """Profile without title_template inherits from global."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(
            global_opts={"title_template": "Global Title"},
            profiles=[_minimal_profile()],
        )
        result = build_runtime_config(hass, entry)
        assert result.profiles["driveway"][0].title_template == "Global Title"

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_unknown_tap_action_preset_does_not_abort_setup(
        self,
        mock_dr: MagicMock,
    ) -> None:
        """Unknown tap_action preset degrades gracefully at runtime."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(profiles=[_minimal_profile(tap_action={"preset": "unknown"})])
        result = build_runtime_config(hass, entry)
        assert result.profiles["driveway"][0].tap_action == {"preset": "unknown"}

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_unknown_action_config_preset_does_not_abort_setup(
        self,
        mock_dr: MagicMock,
    ) -> None:
        """Unknown action button preset degrades gracefully at runtime."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(
            profiles=[
                _minimal_profile(action_config=[{"preset": "view_clip"}, {"preset": "unknown"}])
            ]
        )
        result = build_runtime_config(hass, entry)
        actions = result.profiles["driveway"][0].action_config
        assert actions[1] == {"preset": "unknown"}

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_client_id_resolved_for_multi_instance(self, mock_dr: MagicMock) -> None:
        """client_id resolved from Frigate config entry for multi-instance."""
        mock_dr.return_value.async_get.return_value = None
        frigate_ce = SimpleNamespace(
            entry_id="frigate_test_id",
            data={"client_id": "my-instance"},
        )
        hass = _mock_hass(frigate_entries=[frigate_ce])
        entry = _mock_entry(profiles=[_minimal_profile()])
        result = build_runtime_config(hass, entry)
        assert result.profiles["driveway"][0].client_id == "/my-instance"

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_client_id_empty_for_single_instance(self, mock_dr: MagicMock) -> None:
        """client_id is empty when Frigate entry has no client_id."""
        mock_dr.return_value.async_get.return_value = None
        frigate_ce = SimpleNamespace(
            entry_id="frigate_test_id",
            data={},
        )
        hass = _mock_hass(frigate_entries=[frigate_ce])
        entry = _mock_entry(profiles=[_minimal_profile()])
        result = build_runtime_config(hass, entry)
        assert result.profiles["driveway"][0].client_id == ""


class TestRecognitionConfig:
    """Tests for recognition mode reading in build_runtime_config."""

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_reads_recognition_fields(self, mock_dr: MagicMock) -> None:
        """Recognition mode and sub-label lists are read from subentry data."""
        mock_dr.return_value.async_get.return_value = None
        profile = _minimal_profile()
        profile["recognition_mode"] = RecognitionMode.REQUIRE_RECOGNIZED
        profile["include_sub_labels"] = ["Alice", "Bob"]
        profile["exclude_sub_labels"] = ["Charlie"]

        hass = _mock_hass()
        entry = _mock_entry(profiles=[profile])
        result = build_runtime_config(hass, entry)
        p = result.profiles["driveway"][0]
        assert p.recognition_mode == RecognitionMode.REQUIRE_RECOGNIZED
        assert p.required_sub_labels == ("Alice", "Bob")
        assert p.excluded_sub_labels == ("Charlie",)

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_defaults_when_absent(self, mock_dr: MagicMock) -> None:
        """Recognition fields default to disabled/empty when not in subentry."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(profiles=[_minimal_profile()])
        result = build_runtime_config(hass, entry)
        p = result.profiles["driveway"][0]
        assert p.recognition_mode == RecognitionMode.DISABLED
        assert p.required_sub_labels == ()
        assert p.excluded_sub_labels == ()


class TestMultiCameraProfile:
    """Tests for multi-camera profile support."""

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_multi_camera_indexes_all_cameras(self, mock_dr: MagicMock) -> None:
        """Multi-camera profile appears in all camera buckets."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass(cameras=["driveway", "backyard"])
        entry = _mock_entry(profiles=[_minimal_profile(cameras=["driveway", "backyard"])])
        result = build_runtime_config(hass, entry)
        assert "driveway" in result.profiles
        assert "backyard" in result.profiles
        assert result.profiles["driveway"][0] is result.profiles["backyard"][0]

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_multi_camera_partial_unavailable(self, mock_dr: MagicMock) -> None:
        """Unavailable cameras are filtered out, valid ones kept."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass(cameras=["driveway"])
        entry = _mock_entry(profiles=[_minimal_profile(cameras=["driveway", "ghost_cam"])])
        result = build_runtime_config(hass, entry)
        assert "driveway" in result.profiles
        assert "ghost_cam" not in result.profiles
        p = result.profiles["driveway"][0]
        assert p.cameras == ("driveway",)

    def test_profile_device_name_returns_profile_name(self) -> None:
        """Profile device name is the profile name without prefix."""
        from custom_components.frigate_notifications.data import get_profile_device_name

        assert get_profile_device_name("Alerts") == "Alerts"
        assert get_profile_device_name("Driveway") == "Driveway"

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_zone_aliases_empty_for_multi_camera(self, mock_dr: MagicMock) -> None:
        """Multi-camera profile gets empty zone_aliases."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass(cameras=["driveway", "backyard"])
        entry = _mock_entry(
            global_opts={"zone_aliases": {"driveway": {"z1": "Zone1"}}},
            profiles=[_minimal_profile(cameras=["driveway", "backyard"])],
        )
        result = build_runtime_config(hass, entry)
        p = result.profiles["driveway"][0]
        assert p.zone_aliases == {}

    @patch("custom_components.frigate_notifications.data.dr.async_get")
    def test_global_zone_aliases_populated(self, mock_dr: MagicMock) -> None:
        """RuntimeConfig.global_zone_aliases populated from global options."""
        mock_dr.return_value.async_get.return_value = None
        hass = _mock_hass()
        entry = _mock_entry(
            global_opts={"zone_aliases": {"driveway": {"z1": "Zone1"}}},
            profiles=[_minimal_profile()],
        )
        result = build_runtime_config(hass, entry)
        assert result.global_zone_aliases == {"driveway": {"z1": "Zone1"}}
