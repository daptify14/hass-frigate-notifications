"""Tests for translation consistency."""

import ast
import json
from pathlib import Path

import pytest

INTEGRATION_ROOT = (
    Path(__file__).resolve().parent.parent / "custom_components" / "frigate_notifications"
)
EN_JSON = INTEGRATION_ROOT / "translations" / "en.json"
PLATFORM_FILES = ("sensor.py", "binary_sensor.py", "button.py", "datetime.py", "switch.py")


def _collect_translation_keys() -> list[tuple[str, str]]:
    """Scan entity platform files for (_attr_translation_key, platform) pairs."""
    results: list[tuple[str, str]] = []
    for filename in PLATFORM_FILES:
        filepath = INTEGRATION_ROOT / filename
        platform = filename.removesuffix(".py")
        tree = ast.parse(filepath.read_text())
        results.extend(
            (platform, node.value.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "_attr_translation_key"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    return results


ALL_KEYS = _collect_translation_keys()


@pytest.mark.parametrize(("platform", "key"), ALL_KEYS, ids=[f"{p}.{k}" for p, k in ALL_KEYS])
def test_translation_key_has_entity_name(platform: str, key: str) -> None:
    """Every _attr_translation_key must have a matching entity name in en.json."""
    translations = json.loads(EN_JSON.read_text())
    entity_section = translations.get("entity", {})
    platform_section = entity_section.get(platform, {})
    entry = platform_section.get(key)
    assert entry is not None, f"Missing en.json entity.{platform}.{key}"
    assert "name" in entry, f"en.json entity.{platform}.{key} has no 'name' field"
