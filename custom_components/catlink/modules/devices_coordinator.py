"""The component."""

from typing import TYPE_CHECKING

from homeassistant.const import CONF_DEVICES
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..binary_sensor import CatlinkBinarySensorEntity
from ..const import _LOGGER, DOMAIN, SUPPORTED_DOMAINS
from ..modules.litterbox import LitterBox
from ..modules.scooper_device import ScooperDevice
from ..select import CatlinkSelectEntity
from ..sensor import CatlinkSensorEntity
from ..switch import CatlinkSwitchEntity

if TYPE_CHECKING:
    from ..modules import Device
    from .account import Account


class DevicesCoordinator(DataUpdateCoordinator):
    """Devices Coordinator for CatLink integration."""

    def __init__(self, account: "Account") -> None:
        """Initialize the devices coordinator."""
        super().__init__(
            account.hass,
            _LOGGER,
            name=f"{DOMAIN}-{account.uid}-{CONF_DEVICES}",
            update_interval=account.update_interval,
        )
        self.account = account
        self._subs = {}

    async def _async_update_data(self) -> dict:
        """Update data via API."""
        dls = await self.account.get_devices()
        for dat in dls:
            did = dat.get("id")
            if not did:
                continue
            old = self.hass.data[DOMAIN][CONF_DEVICES].get(did)
            if old:
                dvc = old
                dvc.update_data(dat)
            else:
                typ = dat.get("deviceType")
                match typ:
                    case "SCOOPER":
                        dvc = ScooperDevice(dat, self)
                    case "LITTER_BOX_599":  # SCOOPER C1
                        dvc = LitterBox(dat, self)
                    case _:
                        dvc = Device(dat, self)
                self.hass.data[DOMAIN][CONF_DEVICES][did] = dvc
            await dvc.async_init()
            for d in SUPPORTED_DOMAINS:
                await self.update_hass_entities(d, dvc)
        return self.hass.data[DOMAIN][CONF_DEVICES]

    async def update_hass_entities(self, domain, dvc) -> None:
        """Update Home Assistant entities."""
        hdk = f"hass_{domain}"
        add = self.hass.data[DOMAIN]["add_entities"].get(domain)
        if not add or not hasattr(dvc, hdk):
            return
        for k, cfg in getattr(dvc, hdk).items():
            key = f"{domain}.{k}.{dvc.id}"
            new = None
            if key in self._subs:
                pass
            elif domain == "sensor":
                new = CatlinkSensorEntity(k, dvc, cfg)
            elif domain == "binary_sensor":
                new = CatlinkBinarySensorEntity(k, dvc, cfg)
            elif domain == "switch":
                new = CatlinkSwitchEntity(k, dvc, cfg)
            elif domain == "select":
                new = CatlinkSelectEntity(k, dvc, cfg)
            if new:
                self._subs[key] = new
                add([new])
