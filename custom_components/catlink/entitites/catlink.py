"""The component."""

from homeassistant.components import persistent_notification
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import _LOGGER, DOMAIN
from ..modules.device import Device


class CatlinkEntity(CoordinatorEntity):
    """CatlinkEntity."""

    def __init__(self, name, device: Device, option=None) -> None:
        """Initialize the entity."""
        self.coordinator = device.coordinator
        CoordinatorEntity.__init__(self, self.coordinator)
        self.account = self.coordinator.account
        self._name = name
        self._device = device
        self._option = option or {}
        self._attr_name = f"{device.name} {name}".strip()
        device_uid = device.id or device.mac or f"{device.type}"
        self._attr_device_id = f"{device_uid}"
        self._attr_unique_id = f"{self._attr_device_id}-{name}"
        mac = device.mac[-4:] if device.mac else device.id or device_uid
        device_type = (device.type or "device").lower()
        self.entity_id = f"{DOMAIN}.{device_type}_{mac}_{name}"
        self._attr_icon = self._option.get("icon")
        self._attr_device_class = self._option.get("class")
        self._attr_unit_of_measurement = self._option.get("unit")
        self._attr_state_class = option.get("state_class")
        device_connections = None
        if device.mac:
            device_connections = {(CONNECTION_NETWORK_MAC, device.mac)}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_device_id)},
            connections=device_connections,
            name=device.name,
            model=device.model,
            manufacturer="CatLink",
            sw_version=device.detail.get("firmwareVersion"),
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._device.listeners[self.entity_id] = self._handle_coordinator_update
        self._handle_coordinator_update()

    def _handle_coordinator_update(self):
        self.update()
        self.async_write_ha_state()

    def update(self) -> None:
        """Update the entity."""
        if hasattr(self._device, self._name):
            self._attr_state = getattr(self._device, self._name)
            _LOGGER.debug(
                "Entity update: %s", [self.entity_id, self._name, self._attr_state]
            )

        fun = self._option.get("state_attrs")
        if callable(fun):
            self._attr_extra_state_attributes = fun()

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        return self._attr_state

    async def async_request_api(self, api, params=None, method="GET", **kwargs) -> dict:
        """Request API."""
        throw = kwargs.pop("throw", None)
        rdt = await self.account.request(api, params, method, **kwargs)
        if throw:
            persistent_notification.create(
                self.hass,
                f"{rdt}",
                f"Request: {api}",
                f"{DOMAIN}-request",
            )
        return rdt
