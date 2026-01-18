"""Sensor entity for CatLink integration."""

from homeassistant.components.sensor import SensorEntity

from .base import CatlinkEntity


class CatlinkSensorEntity(CatlinkEntity, SensorEntity):
    """Sensor entity for CatLink."""
