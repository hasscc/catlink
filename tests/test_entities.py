"""Tests for CatLink entity classes."""

from unittest.mock import AsyncMock, MagicMock

from custom_components.catlink.devices.base import Device
from custom_components.catlink.devices.litterbox import LitterBox
from custom_components.catlink.entities.base import CatlinkEntity
from custom_components.catlink.entities.binary import CatlinkBinarySensorEntity
from custom_components.catlink.entities.button import CatlinkButtonEntity
from custom_components.catlink.entities.camera import CatlinkCameraEntity
from custom_components.catlink.entities.number import CatlinkNumberEntity
from custom_components.catlink.entities.select import CatlinkSelectEntity
from custom_components.catlink.entities.sensor import CatlinkSensorEntity
from custom_components.catlink.entities.switch import CatlinkSwitchEntity
from custom_components.catlink.entities.registry import DOMAIN_ENTITY_CLASSES
from custom_components.catlink.entities.time import CatlinkTimeEntity
from datetime import time

import pytest
from pytest_homeassistant_custom_component.common import MockEntityPlatform

from custom_components.catlink.const import DOMAIN
from homeassistant.components.number import NumberMode
from homeassistant.const import STATE_OFF, STATE_ON


@pytest.fixture
def mock_device():
    """Create a mock device with required attributes."""
    device = MagicMock(spec=Device)
    device.id = "dev123"
    device.mac = "AABBCCDDEEFF"
    device.type = "LITTER_BOX_599"
    device.name = "Test Litter Box"
    device.model = "LB599"
    device.detail = {"firmwareVersion": "1.0.0"}
    device.listeners = {}
    return device


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.account = MagicMock()
    return coordinator


@pytest.fixture
def real_device(mock_coordinator):
    """Create a real LitterBox device for entity tests."""
    data = {
        "id": "dev123",
        "mac": "AA:BB:CC:DD:EE:FF",
        "model": "LB599",
        "deviceName": "Test Litter Box",
        "deviceType": "LITTER_BOX_599",
    }
    device = LitterBox(data, mock_coordinator)
    device.detail = {"firmwareVersion": "1.0.0", "currentError": "Normal"}
    device.coordinator = mock_coordinator
    return device


class TestCatlinkEntity:
    """Tests for CatlinkEntity base class."""

    @pytest.mark.parametrize(
        ("option", "coordinator_ok", "expected"),
        [
            ({}, True, True),
            ({}, False, False),
            ({"available": lambda: True}, True, True),
            ({"available": lambda: False}, True, False),
            ({"available": lambda: True}, False, False),
        ],
    )
    def test_available_option(
        self, mock_device, mock_coordinator, option, coordinator_ok, expected
    ) -> None:
        """The "available" option can only make an entity unavailable."""
        mock_device.coordinator = mock_coordinator
        mock_coordinator.last_update_success = coordinator_ok
        entity = CatlinkEntity("error", mock_device, option)

        assert entity.available is expected

    def test_entity_initialization(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test CatlinkEntity initializes with correct attributes."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkEntity("error", mock_device, {"icon": "mdi:alert"})
        entity.coordinator = mock_coordinator
        entity.hass = hass

        assert entity._name == "error"
        assert entity._device == mock_device
        assert entity._attr_icon == "mdi:alert"
        assert "Test Litter Box" in entity._attr_name
        assert "error" in entity._attr_name
        assert entity._attr_device_id == "LITTER_BOX_599_AABBCCDDEEFF"
        assert entity._attr_unique_id == "LITTER_BOX_599_AABBCCDDEEFF-error"

    def test_entity_device_info(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test CatlinkEntity device_info."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkEntity("state", mock_device)
        entity.coordinator = mock_coordinator
        entity.hass = hass

        info = entity._attr_device_info
        assert info["identifiers"] == {
            ("catlink", "LITTER_BOX_599_AABBCCDDEEFF")
        }
        assert info["name"] == "Test Litter Box"
        assert info["model"] == "LB599"
        assert info["manufacturer"] == "CatLink"
        assert info["sw_version"] == "1.0.0"

    def test_entity_update_from_device(
        self, hass, real_device, mock_coordinator
    ) -> None:
        """Test entity update reads state from device."""
        real_device.coordinator = mock_coordinator
        entity = CatlinkSensorEntity("error", real_device)
        entity.coordinator = mock_coordinator
        entity.hass = hass

        entity.update()
        assert entity._attr_state == "Normal"

    def test_entity_unique_id_format(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test entity unique_id format."""
        mock_device.coordinator = mock_coordinator
        mock_device.mac = "1122"
        mock_device.id = "dev456"
        entity = CatlinkEntity("litter_weight", mock_device)
        entity.coordinator = mock_coordinator
        entity.hass = hass

        assert entity._attr_unique_id.endswith("-litter_weight")
        assert "LITTER_BOX_599" in entity._attr_unique_id

    def test_entity_picture_static(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test entity picture supports static value."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkEntity(
            "status", mock_device, {"entity_picture": "https://example.com/cat.jpg"}
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        assert entity._attr_entity_picture == "https://example.com/cat.jpg"

    def test_entity_picture_callable_updates(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test entity picture supports callable updates."""
        mock_device.coordinator = mock_coordinator
        mock_device.avatar_url = "https://example.com/cat1.jpg"
        entity = CatlinkEntity(
            "status", mock_device, {"entity_picture": lambda: mock_device.avatar_url}
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        assert entity._attr_entity_picture == "https://example.com/cat1.jpg"

        mock_device.avatar_url = "https://example.com/cat2.jpg"
        entity.update()
        assert entity._attr_entity_picture == "https://example.com/cat2.jpg"


class TestCatlinkBinarySensorEntity:
    """Tests for CatlinkBinarySensorEntity."""

    def test_binary_sensor_initialization(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test CatlinkBinarySensorEntity initializes with is_on False."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkBinarySensorEntity("occupied", mock_device)
        entity.coordinator = mock_coordinator
        entity.hass = hass

        assert entity._attr_is_on is False

    def test_binary_sensor_update_from_device(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test binary sensor update sets is_on from device attribute."""
        mock_device.coordinator = mock_coordinator
        mock_device.occupied = True
        entity = CatlinkBinarySensorEntity("occupied", mock_device)
        entity.coordinator = mock_coordinator
        entity.hass = hass

        entity.update()
        assert entity._attr_is_on is True
        assert entity.state == STATE_ON

    def test_binary_sensor_is_on_option_wins(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """An "is_on" callable in the options takes precedence over the attribute."""
        mock_device.coordinator = mock_coordinator
        mock_device.occupied = True
        entity = CatlinkBinarySensorEntity(
            "occupied", mock_device, {"is_on": lambda: False}
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        entity.update()
        assert entity._attr_is_on is False

    def test_binary_sensor_update_off(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test binary sensor state is OFF when device attribute is falsy."""
        mock_device.coordinator = mock_coordinator
        mock_device.occupied = False
        entity = CatlinkBinarySensorEntity("occupied", mock_device)
        entity.coordinator = mock_coordinator
        entity.hass = hass

        entity.update()
        assert entity._attr_is_on is False
        assert entity.state == STATE_OFF


class TestCatlinkButtonEntity:
    """Tests for CatlinkButtonEntity."""

    async def test_button_press_calls_option(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test async_press calls option's async_press when callable."""
        mock_device.coordinator = mock_coordinator
        mock_press = AsyncMock(return_value=True)
        entity = CatlinkButtonEntity(
            "action",
            mock_device,
            {"async_press": mock_press},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        result = await entity.async_press()
        assert result is True
        mock_press.assert_called_once()

    async def test_button_press_no_option_returns_false(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test async_press returns False when option has no async_press."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkButtonEntity("action", mock_device, {})
        entity.coordinator = mock_coordinator
        entity.hass = hass

        result = await entity.async_press()
        assert result is False


class TestCatlinkSelectEntity:
    """Tests for CatlinkSelectEntity."""

    def test_select_initialization(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test CatlinkSelectEntity initializes with options from config."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkSelectEntity(
            "mode",
            mock_device,
            {"options": ["auto", "manual"]},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        assert entity._attr_options == ["auto", "manual"]
        assert entity._attr_current_option is None

    def test_select_update_sets_current_option(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test select update sets current_option from state."""
        mock_device.coordinator = mock_coordinator
        mock_device.mode = "auto"
        entity = CatlinkSelectEntity(
            "mode",
            mock_device,
            {"options": ["auto", "manual"]},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        entity.update()
        assert entity._attr_current_option == "auto"

    async def test_select_option_calls_async_select(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test async_select_option calls option's async_select."""
        mock_device.coordinator = mock_coordinator
        mock_device.mode = "manual"
        mock_select = AsyncMock(return_value=True)
        entity = CatlinkSelectEntity(
            "mode",
            mock_device,
            {"options": ["auto", "manual"], "async_select": mock_select},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        result = await entity.async_select_option("manual")
        assert result is True
        mock_select.assert_called_once_with("manual", entity=entity)
        assert entity._attr_current_option == "manual"


class TestCatlinkSensorEntity:
    """Tests for CatlinkSensorEntity."""

    def test_sensor_initialization(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test CatlinkSensorEntity initializes with sensor config."""
        mock_device.coordinator = mock_coordinator
        mock_device.error = "Normal"
        entity = CatlinkSensorEntity(
            "error",
            mock_device,
            {"icon": "mdi:alert", "state_attrs": lambda: {"key": "val"}},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        assert entity._name == "error"
        assert entity._attr_icon == "mdi:alert"

    def test_sensor_update_sets_state_and_attrs(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test sensor update sets state and extra_state_attributes."""
        mock_device.coordinator = mock_coordinator
        mock_device.litter_remaining_days = 5
        state_attrs = {"days_left": 5}

        def get_attrs():
            return state_attrs

        entity = CatlinkSensorEntity(
            "litter_remaining_days",
            mock_device,
            {"unit": "days", "state_attrs": get_attrs},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        entity.update()
        assert entity._attr_state == 5
        assert entity._attr_extra_state_attributes == {"days_left": 5}
        assert entity._attr_native_unit_of_measurement == "days"

    def test_sensor_update_without_state_attrs(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test sensor update when option has no state_attrs."""
        mock_device.coordinator = mock_coordinator
        mock_device.litter_weight = 2.5
        entity = CatlinkSensorEntity(
            "litter_weight",
            mock_device,
            {"unit": "kg"},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        entity.update()
        assert entity._attr_state == 2.5
        assert entity._attr_native_unit_of_measurement == "kg"


class TestCatlinkSwitchEntity:
    """Tests for CatlinkSwitchEntity."""

    def test_switch_initialization(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test CatlinkSwitchEntity initializes."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkSwitchEntity(
            "key_lock",
            mock_device,
            {"async_turn_on": None, "async_turn_off": None},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        assert entity._attr_is_on is False

    async def test_switch_turn_on_calls_option(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test async_turn_on calls option's async_turn_on."""
        mock_device.coordinator = mock_coordinator
        mock_device.key_lock = True
        mock_turn_on = AsyncMock(return_value=True)
        entity = CatlinkSwitchEntity(
            "key_lock",
            mock_device,
            {"async_turn_on": mock_turn_on, "async_turn_off": MagicMock()},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass

        await entity.async_turn_on()
        assert entity._attr_is_on is True
        mock_turn_on.assert_called_once()

    async def test_switch_turn_off_calls_option(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Test async_turn_off calls option's async_turn_off."""
        mock_device.coordinator = mock_coordinator
        mock_turn_off = AsyncMock(return_value=True)
        entity = CatlinkSwitchEntity(
            "key_lock",
            mock_device,
            {"async_turn_on": MagicMock(), "async_turn_off": mock_turn_off},
        )
        entity.coordinator = mock_coordinator
        entity.hass = hass
        entity._attr_is_on = True

        await entity.async_turn_off()
        assert entity._attr_is_on is False
        mock_turn_off.assert_called_once()


class TestTranslationKeyOption:
    """Tests for the opt-in "translation_key" entity option."""

    def test_translated_name(self, mock_device, mock_coordinator) -> None:
        """With a translation key HA builds the name from the device and translations."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkSensorEntity("litter_level", mock_device, {"translation_key": "litter_level"})

        assert entity.has_entity_name is True
        assert entity.translation_key == "litter_level"
        assert not hasattr(entity, "_attr_name") or entity._attr_name is None
        assert entity.entity_id.endswith("_litter_level")

    def test_plain_name_without_option(self, mock_device, mock_coordinator) -> None:
        """Without it the old "<device> <key>" name stays."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkSensorEntity("litter_level", mock_device, {})

        assert entity.has_entity_name is False
        assert entity._attr_name == "Test Litter Box litter_level"


class TestCatlinkNumberEntity:
    """Tests for CatlinkNumberEntity."""

    def _entity(self, hass, mock_device, mock_coordinator, option):
        mock_device.coordinator = mock_coordinator
        entity = CatlinkNumberEntity("portions", mock_device, option)
        entity.coordinator = mock_coordinator
        entity.hass = hass
        return entity

    def test_number_initialization(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Range, step and mode come from the option; mode defaults to auto."""
        entity = self._entity(
            hass, mock_device, mock_coordinator, {"min": 1, "max": 30, "step": 1}
        )
        assert entity._attr_native_min_value == 1
        assert entity._attr_native_max_value == 30
        assert entity._attr_native_step == 1
        assert entity._attr_mode == NumberMode.AUTO

        boxed = self._entity(
            hass, mock_device, mock_coordinator, {"mode": NumberMode.BOX}
        )
        assert boxed._attr_mode == NumberMode.BOX

    async def test_set_value_without_option_stores_on_device(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Without "async_set_value" the value is only stored on the device (feeder portions)."""
        mock_device.portions = 1
        entity = self._entity(hass, mock_device, mock_coordinator, {"min": 1, "max": 10})

        await entity.async_set_native_value(3.0)

        assert mock_device.portions == 3

    async def test_set_value_calls_option(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """With "async_set_value" the value goes through it and the state refreshes."""
        mock_device.portions = 1
        mock_set = AsyncMock(return_value=True)

        def applied(value, **kwargs):
            mock_device.portions = int(value)
            return True

        mock_set.side_effect = applied
        entity = self._entity(
            hass, mock_device, mock_coordinator, {"async_set_value": mock_set}
        )

        await entity.async_set_native_value(5.0)

        mock_set.assert_awaited_once_with(5.0, entity=entity)
        assert entity._attr_state == 5

    async def test_set_value_failure_keeps_state(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """A failed write leaves the device value and entity state alone."""
        mock_device.portions = 2
        mock_set = AsyncMock(return_value=False)
        entity = self._entity(
            hass, mock_device, mock_coordinator, {"async_set_value": mock_set}
        )
        entity.update()

        await entity.async_set_native_value(7.0)

        assert mock_device.portions == 2
        assert entity._attr_state == 2


class TestCatlinkTimeEntity:
    """Tests for CatlinkTimeEntity."""

    def _entity(self, hass, mock_device, mock_coordinator, option):
        mock_device.coordinator = mock_coordinator
        entity = CatlinkTimeEntity("quiet_start", mock_device, option)
        entity.coordinator = mock_coordinator
        entity.hass = hass
        entity.entity_id = "time.test_quiet_start"
        return entity

    def test_value_from_device(self, hass, mock_device, mock_coordinator) -> None:
        """The device attribute becomes the value, formatted like HA's time entities."""
        mock_device.quiet_start = time(23, 0)
        entity = self._entity(hass, mock_device, mock_coordinator, {})

        entity.update()

        assert entity.native_value == time(23, 0)
        assert entity.state == "23:00:00"

    def test_unknown_value(self, hass, mock_device, mock_coordinator) -> None:
        """None or a non-time value reads as unknown."""
        mock_device.quiet_start = None
        entity = self._entity(hass, mock_device, mock_coordinator, {})
        entity.update()
        assert entity.state is None

        mock_device.quiet_start = "23:00"
        entity.update()
        assert entity.state is None

    async def test_set_value_calls_option(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """A new time goes through "async_set_value" and the state refreshes."""
        mock_device.quiet_start = time(23, 0)

        async def applied(value, **kwargs):
            mock_device.quiet_start = value
            return True

        mock_set = AsyncMock(side_effect=applied)
        entity = self._entity(
            hass, mock_device, mock_coordinator, {"async_set_value": mock_set}
        )
        entity.async_write_ha_state = MagicMock()

        await entity.async_set_value(time(22, 30))

        mock_set.assert_awaited_once_with(time(22, 30), entity=entity)
        assert entity.native_value == time(22, 30)

    async def test_set_value_failure_keeps_state(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """A failed write leaves the value alone."""
        mock_device.quiet_start = time(23, 0)
        entity = self._entity(
            hass, mock_device, mock_coordinator,
            {"async_set_value": AsyncMock(return_value=False)},
        )
        entity.update()

        await entity.async_set_value(time(1, 0))

        assert entity.native_value == time(23, 0)

    async def test_read_only_without_option(
        self, hass, mock_device, mock_coordinator
    ) -> None:
        """Without "async_set_value" the time can't be changed."""
        mock_device.quiet_start = time(23, 0)
        entity = self._entity(hass, mock_device, mock_coordinator, {})

        with pytest.raises(NotImplementedError):
            await entity.async_set_value(time(1, 0))


class TestEntityIds:
    """Entity ids use the entity's own platform domain, not "catlink"."""

    @pytest.mark.parametrize(
        ("entity_cls", "platform"),
        [
            (CatlinkSensorEntity, "sensor"),
            (CatlinkBinarySensorEntity, "binary_sensor"),
            (CatlinkSwitchEntity, "switch"),
            (CatlinkSelectEntity, "select"),
            (CatlinkButtonEntity, "button"),
            (CatlinkNumberEntity, "number"),
            (CatlinkTimeEntity, "time"),
            (CatlinkCameraEntity, "camera"),
        ],
    )
    def test_object_id_keeps_its_platform(
        self, mock_device, mock_coordinator, entity_cls, platform
    ) -> None:
        """The object id is unchanged; only the domain is the platform's."""
        mock_device.coordinator = mock_coordinator

        entity = entity_cls("litter_level", mock_device, {})

        assert entity.entity_id == f"{platform}.litter_box_599_eeff_litter_level"

    def test_every_platform_class_is_covered(self) -> None:
        """No platform may fall back to the integration's domain."""
        for platform, entity_cls in DOMAIN_ENTITY_CLASSES.items():
            assert entity_cls._entity_id_format == f"{platform}.{{}}"

    async def test_adding_an_entity_keeps_its_id(
        self, hass, mock_device, mock_coordinator, caplog
    ) -> None:
        """Added through a platform, the entity keeps that exact id."""
        mock_device.coordinator = mock_coordinator
        entity = CatlinkSensorEntity("litter_level", mock_device, {})
        platform = MockEntityPlatform(hass, domain="sensor", platform_name=DOMAIN)

        await platform.async_add_entities([entity])
        await hass.async_block_till_done()

        assert entity.entity_id == "sensor.litter_box_599_eeff_litter_level"
        assert hass.states.get(entity.entity_id) is not None
        assert "entity ID" not in caplog.text
