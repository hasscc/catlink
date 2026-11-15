"""Checks that the Scooper Pro Ultra's entities have translations and icons."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from custom_components.catlink.devices import scooper_pro_ultra as spu
from custom_components.catlink.devices.scooper_pro_ultra import ScooperProUltraDevice
import pytest

BASE = Path(__file__).parent.parent / "custom_components" / "catlink"
EN = json.loads((BASE / "translations" / "en.json").read_text())
ICONS = json.loads((BASE / "icons.json").read_text())
DOMAINS = [
    "sensor", "binary_sensor", "switch", "number", "select", "button", "time",
    "camera", "media_player",
]


@pytest.fixture
def device():
    coordinator = MagicMock()
    return ScooperProUltraDevice(
        {"id": "u1", "mac": "AA:BB", "deviceType": "VISUAL_PRO_ULTRA", "iotId": "iot-1"},
        coordinator,
    )


def test_strings_and_english_match() -> None:
    """translations/en.json is the runtime copy of strings.json."""
    assert json.loads((BASE / "strings.json").read_text()) == EN


@pytest.mark.parametrize("domain", DOMAINS)
def test_every_entity_is_translated(device, domain) -> None:
    """Each entity carries its translation key and has a name in en.json."""
    entities = getattr(device, f"hass_{domain}")
    assert entities, domain
    for key, option in entities.items():
        assert option["translation_key"] == key
        assert "icon" not in option
        assert EN["entity"][domain][key]["name"], f"{domain}.{key}"


@pytest.mark.parametrize("domain", DOMAINS)
def test_icons_belong_to_entities(device, domain) -> None:
    """icons.json only names existing entities, and its state icons existing states."""
    entities = getattr(device, f"hass_{domain}")
    for key, icon in ICONS["entity"].get(domain, {}).items():
        assert key in entities, f"{domain}.{key}"
        assert icon["default"].startswith("mdi:")
        states = EN["entity"][domain][key].get("state")
        for state in icon.get("state", {}):
            assert state in ("on", "off") or (states and state in states), f"{domain}.{key}.{state}"


@pytest.mark.parametrize(
    ("domain", "key", "values"),
    [
        ("sensor", "state", [*spu.RUN_JOBS.values(), *spu.RUN_STATES.values(), "running"]),
        ("sensor", "waste_bin", spu.WASTE_BIN_LEVELS.values()),
        ("sensor", "fault", spu.FAULTS.values()),
        ("select", "mode", spu.MODES.values()),
        ("select", "camera_schedule", spu.CAMERA_SCHEDULES.values()),
        ("select", "fill_light", spu.FILL_LIGHT_MODES.values()),
        ("select", "video_quality", spu.VIDEO_QUALITIES.values()),
    ],
)
def test_states_translated(domain, key, values) -> None:
    """Every state the code can produce (besides code_N) has a translation."""
    states = EN["entity"][domain][key]["state"]
    assert set(values) <= set(states)
