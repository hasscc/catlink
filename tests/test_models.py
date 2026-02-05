"""Tests for CatLink Pydantic models and parse utilities."""

import pytest

from custom_components.catlink.models.additional_cfg import AdditionalDeviceConfig
from custom_components.catlink.models.api.device import (
    DeviceInfoBase,
    LitterDeviceInfo,
)
from custom_components.catlink.models.api.parse import parse_response


class TestAdditionalDeviceConfig:
    """Tests for AdditionalDeviceConfig model."""

    def test_default_values(self) -> None:
        """Test default values."""
        config = AdditionalDeviceConfig()
        assert config.name == ""
        assert config.mac == ""
        assert config.empty_weight == 0.0
        assert config.max_samples_litter == 24

    def test_with_values(self) -> None:
        """Test with provided values."""
        config = AdditionalDeviceConfig(
            name="Living Room",
            mac="AA:BB:CC:DD:EE:FF",
            empty_weight=1.5,
            max_samples_litter=12,
        )
        assert config.name == "Living Room"
        assert config.mac == "AA:BB:CC:DD:EE:FF"
        assert config.empty_weight == 1.5
        assert config.max_samples_litter == 12


class TestParseResponse:
    """Tests for parse_response utility."""

    def test_parse_dict_to_model(self) -> None:
        """Test parsing dict into Pydantic model."""
        data = {
            "deviceInfo": {
                "workStatus": "00",
                "firmwareVersion": "1.2.3",
                "litterCountdown": 5,
            }
        }
        result = parse_response(data, "deviceInfo", LitterDeviceInfo)
        assert isinstance(result, LitterDeviceInfo)
        assert result.workStatus == "00"
        assert result.firmwareVersion == "1.2.3"
        assert result.litterCountdown == 5

    def test_parse_missing_key_returns_default(self) -> None:
        """Test parsing when key is missing returns default."""
        data = {"other": "value"}
        result = parse_response(data, "deviceInfo", LitterDeviceInfo, default={})
        assert result == {}

    def test_parse_missing_key_no_default_returns_none(self) -> None:
        """Test parsing when key is missing and no default."""
        data = {}
        result = parse_response(data, "deviceInfo", LitterDeviceInfo)
        assert result is None

    def test_parse_list_returns_list_of_models(self) -> None:
        """Test parsing list of dicts."""
        data = {
            "items": [
                {"workStatus": "00", "firmwareVersion": "1.0"},
                {"workStatus": "01", "firmwareVersion": "2.0"},
            ]
        }
        result = parse_response(data, "items", DeviceInfoBase)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].workStatus == "00"
        assert result[1].workStatus == "01"

    def test_parse_invalid_data_returns_default(self) -> None:
        """Test parsing invalid data returns default on ValidationError."""
        data = {"deviceInfo": "not a dict"}
        result = parse_response(data, "deviceInfo", LitterDeviceInfo, default={})
        assert result == {}
