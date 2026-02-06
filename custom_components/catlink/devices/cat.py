"""Cat device class for CatLink integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.catlink.devices.base import Device
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfMass
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from custom_components.catlink.modules.devices_coordinator import DevicesCoordinator


GENDER_LABELS: dict[int, str] = {
    1: "Male",
    2: "Female",
    3: "Neutered male",
    4: "Neutered female",
}


class CatDevice(Device):
    """Cat device class for CatLink integration."""

    def __init__(
        self,
        dat: dict,
        coordinator: DevicesCoordinator,
        additional_config: Any | None = None,
    ) -> None:
        """Initialize the cat device."""
        super().__init__(dat, coordinator, additional_config)

    async def async_init(self) -> None:
        """Initialize the device."""
        self.detail = self.data

    def update_data(self, dat: dict) -> None:
        """Update device data."""
        super().update_data(dat)
        self.detail = dat

    async def update_device_detail(self) -> dict:
        """Update device detail (cats use list payload)."""
        self.detail = self.data
        self._handle_listeners()
        return self.detail

    @property
    def pet_id(self) -> str | None:
        """Return the pet id."""
        return self.data.get("pet_id") or self.data.get("id")

    @property
    def weight(self) -> float | None:
        """Return the pet weight."""
        return self.data.get("weight")

    @property
    def age_years(self) -> int | None:
        """Return the pet age in years."""
        return self.data.get("year") or self.data.get("age")

    @property
    def age_months(self) -> int | None:
        """Return the pet age in months."""
        return self.data.get("month")

    @property
    def breed(self) -> str | None:
        """Return the pet breed."""
        return self.data.get("breedName")

    @property
    def gender_label(self) -> str | None:
        """Return the pet gender label."""
        gender = self.data.get("gender")
        if isinstance(gender, str) and gender.isdigit():
            gender = int(gender)
        if isinstance(gender, int):
            return GENDER_LABELS.get(gender)
        return None

    @property
    def birthday(self) -> str | None:
        """Return the pet birthday as ISO date."""
        birthday = self.data.get("birthday")
        if not birthday:
            return None
        return dt_util.utc_from_timestamp(birthday / 1000).date().isoformat()

    @property
    def avatar_url(self) -> str | None:
        """Return the pet avatar URL."""
        return self.data.get("avatar")

    @property
    def avatar(self) -> None:
        """Return the avatar state."""
        return None

    def _summary(self) -> dict:
        return self.data.get("summary_simple") or {}

    def _summary_section(self, name: str) -> dict:
        summary = self._summary()
        return summary.get(name) or {}

    @staticmethod
    def _to_float(value) -> float | None:
        """Convert a value to float when possible."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    @property
    def status(self) -> str | None:
        """Return the pet health status description."""
        summary = self._summary()
        return summary.get("statusDescription") or summary.get("status")

    @property
    def toilet_times(self) -> int | None:
        """Return the number of toilet visits."""
        return self._summary_section("toilet").get("times")

    @property
    def toilet_weight_avg(self) -> float | None:
        """Return the average toilet weight."""
        return self._summary_section("toilet").get("weightAvg")

    @property
    def pee_times(self) -> int | None:
        """Return the number of pee events."""
        return self._summary_section("toilet").get("peed")

    @property
    def poo_times(self) -> int | None:
        """Return the number of poo events."""
        return self._summary_section("toilet").get("pood")

    @property
    def drink_times(self) -> int | None:
        """Return the drink times."""
        return self._summary_section("drink").get("times")

    @property
    def diet_times(self) -> int | None:
        """Return the diet times."""
        return self._summary_section("diet").get("times")

    @property
    def diet_intakes(self) -> float | None:
        """Return the diet intakes."""
        return self._to_float(self._summary_section("diet").get("intakes"))

    @property
    def sport_active_duration(self) -> int | None:
        """Return the sport active duration."""
        return self._summary_section("sport").get("activeDuration")

    def cat_attrs(self) -> dict:
        """Return the cat attributes."""
        return {
            "pet_id": self.pet_id,
            "breed": self.breed,
            "gender": self.gender_label,
            "birthday": self.birthday,
            "weight": self.weight,
            "age_years": self.age_years,
            "age_months": self.age_months,
            "toilet_times": self.toilet_times,
            "toilet_weight_avg": self.toilet_weight_avg,
            "pee_times": self.pee_times,
            "poo_times": self.poo_times,
            "drink_times": self.drink_times,
            "diet_times": self.diet_times,
            "diet_intakes": self.diet_intakes,
            "sport_active_duration": self.sport_active_duration,
        }

    @property
    def hass_sensor(self) -> dict:
        """Return cat sensors."""
        return {
            "status": {
                "icon": "mdi:information",
                "state_attrs": self.cat_attrs,
            },
            "weight": {
                "icon": "mdi:scale",
                "class": SensorDeviceClass.WEIGHT,
                "state_class": SensorStateClass.MEASUREMENT,
                "unit": UnitOfMass.KILOGRAMS,
            },
            "age_years": {
                "icon": "mdi:calendar",
            },
            "age_months": {
                "icon": "mdi:calendar",
            },
            "gender_label": {
                "icon": "mdi:gender-male-female",
            },
            "breed": {
                "icon": "mdi:cat",
            },
            "birthday": {
                "icon": "mdi:cake-variant",
                "class": SensorDeviceClass.DATE,
            },
            "avatar": {
                "icon": "mdi:image",
                "entity_picture": self.avatar_url,
            },
            "toilet_times": {
                "icon": "mdi:toilet",
            },
            "toilet_weight_avg": {
                "icon": "mdi:scale",
                "class": SensorDeviceClass.WEIGHT,
                "state_class": SensorStateClass.MEASUREMENT,
                "unit": UnitOfMass.KILOGRAMS,
            },
            "pee_times": {
                "icon": "mdi:water",
            },
            "poo_times": {
                "icon": "mdi:emoticon-poop",
            },
            "drink_times": {
                "icon": "mdi:cup-water",
            },
            "diet_times": {
                "icon": "mdi:food",
            },
            "diet_intakes": {
                "icon": "mdi:food",
            },
            "sport_active_duration": {
                "icon": "mdi:run",
            },
        }

    @property
    def hass_binary_sensor(self) -> dict:
        """Return empty binary sensors for cats."""
        return {}

    @property
    def hass_switch(self) -> dict:
        """Return empty switches for cats."""
        return {}

    @property
    def hass_button(self) -> dict:
        """Return empty buttons for cats."""
        return {}

    @property
    def hass_select(self) -> dict:
        """Return empty selects for cats."""
        return {}
