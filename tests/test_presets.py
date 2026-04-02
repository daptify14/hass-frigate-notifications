"""Tests for built-in preset loading and cache population."""

from pathlib import Path

from homeassistant.core import HomeAssistant
import pytest
import voluptuous as vol

from custom_components.frigate_notifications.const import DOMAIN
from custom_components.frigate_notifications.presets import (
    TemplateOption,
    async_ensure_preset_cache,
    build_template_id_map,
    load_profile_presets,
    load_template_presets,
)


class TestPresetLoaders:
    """Test built-in preset and template loaders."""

    @staticmethod
    def _patch_preset_dir(hass: HomeAssistant, monkeypatch, base_dir: Path) -> None:
        """Redirect hass.config.path() to a temp preset directory."""
        monkeypatch.setattr(hass.config, "path", lambda *parts: str(base_dir.joinpath(*parts)))

    def test_load_profile_presets_includes_built_ins(self) -> None:
        """Built-in profile presets load in display order."""
        presets = load_profile_presets()
        ids = [preset.id for preset in presets]
        names = [preset.name for preset in presets]

        assert ids == [
            "simple",
            "detailed",
            "notify_on_end",
            "snapshot_pager",
            "latest_event",
            "activity_log",
        ]
        assert names == [
            "Live Alerts",
            "Rich Alerts",
            "End Only",
            "Snapshot Only",
            "Latest Only",
            "Silent Log",
        ]

    def test_detailed_preset_uses_rich_alert_layout(self) -> None:
        """The rich-alert preset seeds the richer structured layout by default."""
        preset = next(p for p in load_profile_presets() if p.id == "detailed")

        data = preset.to_profile_data()

        assert data["phases"]["initial"]["message_template"] == "phase_icon_context"
        assert data["phases"]["update"]["message_template"] == "rich_update"
        assert data["phases"]["update"]["interruption_level"] == "passive"
        assert data["phases"]["end"]["message_template"] == "genai_pending"
        assert data["phases"]["genai"]["message_template"] == "phase_icon_genai_summary"
        assert data["phases"]["genai"]["enabled"] is True

    def test_detailed_preset_applies_genai_disabled_overrides(self) -> None:
        """Disabling GenAI at preset selection switches rich alerts to a real final card."""
        preset = next(p for p in load_profile_presets() if p.id == "detailed")

        data = preset.to_profile_data(genai_available=False)

        assert data["phases"]["end"]["message_template"] == "phase_icon_context"
        assert data["phases"]["genai"]["enabled"] is False

    def test_latest_event_preset_seeds_profile_defaults_and_end_fallback(self) -> None:
        """Preset defaults and implicit end-phase fallback stay intact."""
        preset = next(p for p in load_profile_presets() if p.id == "latest_event")

        data = preset.to_profile_data()

        assert data["tag"] == "frigate-latest"
        assert data["group"] == "frigate"
        assert (
            data["phases"]["end"]["message_template"]
            == data["phases"]["update"]["message_template"]
        )

    def test_build_template_id_map_contains_all_ids(self) -> None:
        """ID map contains every content and title ID."""
        template_presets = load_template_presets()
        id_map = build_template_id_map(template_presets)

        expected_ids = {
            opt.id for cat in ("content", "titles") for opt in template_presets[cat] if opt.id
        }
        assert set(id_map.keys()) == expected_ids
        assert id_map["object_action_zone"] == "{{ object }} {{ zone_phrase }} {{ zone_alias }}"
        assert id_map["camera_time"] == "{{ camera_name }} - {{ time }}"

    def test_build_template_id_map_rejects_duplicates(self) -> None:
        """Duplicate IDs raise vol.Invalid."""
        duped: dict[str, list[TemplateOption]] = {
            "content": [
                TemplateOption(id="dupe", value="a", label="A"),
                TemplateOption(id="dupe", value="b", label="B"),
            ],
        }
        with pytest.raises(vol.Invalid, match="Duplicate template ID"):
            build_template_id_map(duped)

    def test_load_profile_presets_applies_user_override(
        self, hass: HomeAssistant, monkeypatch, tmp_path: Path
    ) -> None:
        """User presets can override a built-in preset ID."""
        self._patch_preset_dir(hass, monkeypatch, tmp_path)
        preset_dir = tmp_path / "frigate_notifications" / "presets"
        preset_dir.mkdir(parents=True)
        (preset_dir / "simple.yaml").write_text(
            """
schema_version: 1
id: simple
version: 99
name: Host Override
summary: Host override summary
sort_order: 1
phases:
  initial:
    message_template: "{{ camera_name }}"
""".strip()
        )

        presets = load_profile_presets(hass)
        preset = next(p for p in presets if p.id == "simple")

        assert preset.name == "Host Override"
        assert preset.version == 99
        assert preset.to_profile_data()["phases"]["initial"]["message_template"] == (
            "{{ camera_name }}"
        )

    def test_load_profile_presets_skips_invalid_user_files(
        self, hass: HomeAssistant, monkeypatch, tmp_path: Path, caplog
    ) -> None:
        """Invalid or too-new user preset files are skipped with warnings."""
        self._patch_preset_dir(hass, monkeypatch, tmp_path)
        preset_dir = tmp_path / "frigate_notifications" / "presets"
        preset_dir.mkdir(parents=True)
        (preset_dir / "future.yaml").write_text(
            """
schema_version: 99
id: future
version: 1
name: Future Preset
summary: Not supported yet
phases:
  initial:
    message_template: "{{ object }}"
""".strip()
        )
        (preset_dir / "broken.yaml").write_text("schema_version: [")

        presets = load_profile_presets(hass)

        assert {preset.id for preset in presets} >= {
            "simple",
            "detailed",
            "notify_on_end",
            "snapshot_pager",
            "latest_event",
            "activity_log",
        }
        assert "Skipping preset future.yaml" in caplog.text
        assert "Skipping preset broken.yaml" in caplog.text

    async def test_async_ensure_preset_cache_populates_hass_data(self, hass: HomeAssistant) -> None:
        """Preset caches are loaded into hass.data for config flows."""
        await async_ensure_preset_cache(hass)

        domain_data = hass.data[DOMAIN]
        assert [preset.id for preset in domain_data["profile_presets"]] == [
            "simple",
            "detailed",
            "notify_on_end",
            "snapshot_pager",
            "latest_event",
            "activity_log",
        ]
        assert any(
            option.value == "{{ subjects }}"
            for option in domain_data["template_presets"]["content"]
        )
        assert "template_id_map" in domain_data
        assert domain_data["template_id_map"]["object_action_zone"] == (
            "{{ object }} {{ zone_phrase }} {{ zone_alias }}"
        )
