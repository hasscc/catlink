"""The component."""

import asyncio

from homeassistant.const import CONF_DEVICES
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .account import Account
from ..const import _LOGGER, CONF_DEVICE_IDS, DOMAIN, SUPPORTED_DOMAINS
from ..devices.registry import create_device
from ..entities.registry import DOMAIN_ENTITY_CLASSES
from ..models.additional_cfg import AdditionalDeviceConfig


class DevicesCoordinator(DataUpdateCoordinator):
    """Devices Coordinator for CatLink integration."""

    def __init__(
        self,
        account: "Account",
        config_entry_id: str,
        device_ids: list[str] | None = None,
    ) -> None:
        """Initialize the devices coordinator."""
        super().__init__(
            account.hass,
            _LOGGER,
            name=f"{DOMAIN}-{account.uid}-{CONF_DEVICES}",
            update_interval=account.update_interval,
        )
        self.account = account
        self.config_entry_id = config_entry_id
        self._subs = {}
        self._device_ids = device_ids
        self.additional_config = self.hass.data[DOMAIN]["config"].get(CONF_DEVICES, {})
        self.additional_config = [
            AdditionalDeviceConfig(**cfg) for cfg in self.additional_config
        ]

    async def _async_update_data(self) -> dict:
        """Update data via API."""
        dls = await self.account.get_devices()
        for dat in dls:
            did = dat.get("id")
            if not did:
                continue
            if self._device_ids is not None and did not in self._device_ids:
                continue
            additional_config = next(
                (cfg for cfg in self.additional_config if cfg.mac == dat.get("mac")),
                None,
            )
            old = self.hass.data[DOMAIN][CONF_DEVICES].get(did)
            if old:
                dvc = old
                dvc.update_data(dat)
            else:
                dvc = create_device(dat, self, additional_config)
                self.hass.data[DOMAIN][CONF_DEVICES][did] = dvc
            await dvc.async_init()
            for d in SUPPORTED_DOMAINS:
                await self.update_hass_entities(d, dvc)
        cats = await self.account.get_cats(self.hass.config.time_zone)
        if cats:
            timezone_id = self.hass.config.time_zone
            date = dt_util.now().date().isoformat()
            requests = [
                self.account.get_cat_summary_simple(
                    cat.get("id"), date, timezone_id
                )
                for cat in cats
                if cat.get("id")
            ]
            summaries = (
                await asyncio.gather(*requests) if requests else []
            )
        else:
            summaries = []

        summary_map = {
            cat.get("id"): summary
            for cat, summary in zip(cats, summaries, strict=False)
            if cat.get("id")
        }
        for cat in cats:
            pet_id = cat.get("id")
            if not pet_id:
                continue
            cat_data = {**cat}
            cat_data["pet_id"] = pet_id
            cat_data["id"] = f"cat-{pet_id}"
            cat_data["mac"] = f"cat-{pet_id}"
            cat_data["deviceType"] = "CAT"
            cat_data["deviceName"] = cat_data.get("petName") or f"Cat {pet_id}"
            cat_data.setdefault("model", cat_data.get("breedName") or "Cat")
            cat_data["summary_simple"] = summary_map.get(pet_id, {})
            did = cat_data["id"]
            old = self.hass.data[DOMAIN][CONF_DEVICES].get(did)
            if old:
                dvc = old
                dvc.update_data(cat_data)
            else:
                dvc = create_device(cat_data, self, None)
                self.hass.data[DOMAIN][CONF_DEVICES][did] = dvc
            await dvc.async_init()
            for d in SUPPORTED_DOMAINS:
                await self.update_hass_entities(d, dvc)
        return self.hass.data[DOMAIN][CONF_DEVICES]

    async def update_hass_entities(self, domain, dvc) -> None:
        """Update Home Assistant entities."""
        hdk = f"hass_{domain}"
        add_entities = self.hass.data[DOMAIN].get("add_entities", {})
        add = add_entities.get(self.config_entry_id, {}).get(domain)
        if not add or not hasattr(dvc, hdk):
            return
        added_entity_ids: list[str] = []
        entity_cls = DOMAIN_ENTITY_CLASSES.get(domain)
        for k, cfg in getattr(dvc, hdk).items():
            key = f"{domain}.{k}.{dvc.id}"
            new = None
            if key in self._subs:
                pass
            elif entity_cls is not None:
                new = entity_cls(k, dvc, cfg)
            if new:
                self._subs[key] = new
                add([new])
                added_entity_ids.append(new.entity_id)
        if added_entity_ids:
            _LOGGER.info(
                "Device %s entities: %s",
                dvc.name,
                added_entity_ids,
            )
