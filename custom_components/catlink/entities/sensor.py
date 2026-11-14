"""Sensor entity for CatLink integration."""

from homeassistant.components.sensor import ENTITY_ID_FORMAT, SensorEntity

from .base import CatlinkEntity


class CatlinkSensorEntity(CatlinkEntity, SensorEntity):
    """Sensor entity for CatLink."""

    _entity_id_format = ENTITY_ID_FORMAT
