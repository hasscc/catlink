"""Release regressions with synthetic data only; no live network."""

import datetime
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_DEVICES
from custom_components.catlink.const import DOMAIN
from custom_components.catlink.modules.account import Account
from custom_components.catlink.modules.devices_coordinator import DevicesCoordinator
from custom_components.catlink.devices.base import Device
from custom_components.catlink.devices.visual_c07 import VisualC07Device

DATA = {
    "id": "fake-c07",
    "mac": "00:00:00:00:00:01",
    "deviceType": "VISUAL_C07",
    "deviceName": "Test C07",
    "model": "MODEL_00",
}


@pytest.fixture
async def account(hass):
    obj = Account(
        hass,
        {
            "phone": "test-phone",
            "phone_iac": "86",
            "password": "fake",
            "token": "fake-old",
        },
    )
    yield obj


@pytest.fixture
def coord(hass):
    hass.data[DOMAIN] = {"config": {"devices": []}, "devices": {}, "add_entities": {}}
    acc = MagicMock(spec=Account)
    acc.hass = hass
    acc.uid = "test-user"
    acc.update_interval = datetime.timedelta(minutes=1)
    acc.get_devices = AsyncMock(return_value=[DATA])
    acc.get_cats = AsyncMock(return_value=[])
    acc.request = AsyncMock(
        return_value={"returnCode": 0, "data": {"deviceInfo": {"online": True}}}
    )
    return DevicesCoordinator(acc, "test-entry")


@pytest.mark.asyncio
@pytest.mark.parametrize("loader", ["get_devices", "get_cats"])
async def test_empty_inventory_never_logs_payload(account, caplog, loader):
    account.request = AsyncMock(
        return_value={
            "returnCode": 4003,
            "secret": "RESPONSE-SECRET",
            "data": {},
            "url": "https://fake.aliyuncs.com/PRIVATE-GRANT",
        }
    )
    with caplog.at_level(logging.DEBUG, logger="custom_components.catlink"):
        from homeassistant.helpers.update_coordinator import UpdateFailed

        with pytest.raises(UpdateFailed):
            await getattr(account, loader)()
    assert "RESPONSE-SECRET" not in caplog.text
    assert "PRIVATE-GRANT" not in caplog.text
    assert "test-phone" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["GET", "POST", "POST_GET"])
async def test_retry_signs_fresh_copy(account, method):
    calls = []

    async def request(verb, url, **kwargs):
        key = "params" if method in ("GET", "POST_GET") else "data"
        calls.append((verb, dict(kwargs[key])))
        return MagicMock(
            json=AsyncMock(return_value={"returnCode": 1002 if len(calls) == 1 else 0})
        )

    async def login():
        account._config["token"] = "fake-new"
        return True

    payload = {"deviceId": "synthetic-id"}
    with (
        patch.object(account.http, "request", side_effect=request),
        patch.object(account, "async_login", side_effect=login),
    ):
        assert await account.request("token/test", payload, method) == {"returnCode": 0}
    assert payload == {"deviceId": "synthetic-id"}
    assert len(calls) == 2
    for verb, signed in calls:
        assert verb == ("GET" if method == "GET" else "POST")
        signature = signed.pop("sign")
        assert signature == account.params_sign(signed)
    assert calls[-1][1]["token"] == "fake-new"


@pytest.mark.asyncio
async def test_nullable_timeline_keeps_media_source(coord):
    dvc = VisualC07Device(DATA, coord)
    coord.account.request = AsyncMock(
        return_value={
            "returnCode": 0,
            "data": {
                "records": [
                    None,
                    {
                        "time": "12:00",
                        "event": "clean",
                        "firstSection": None,
                        "secondSection": None,
                        "errkey": None,
                        "picIdOfPre": "fake-pic",
                    },
                ]
            },
        }
    )
    logs = await dvc.update_logs()
    assert len(logs) == 1
    assert logs[0]["event"] == "clean"
    assert dvc._media_events[0]["picIdOfPre"] == "fake-pic"
    assert "fake-pic" not in str(dvc.last_log_attrs())


@pytest.mark.asyncio
async def test_reload_replaces_old_generic_object(coord):
    old_coord = MagicMock()
    old = Device(DATA, old_coord)
    coord.hass.data[DOMAIN][CONF_DEVICES][DATA["id"]] = old
    with patch.object(VisualC07Device, "async_init", new_callable=AsyncMock):
        devices = await coord._async_update_data()
    assert isinstance(devices[DATA["id"]], VisualC07Device)
    assert devices[DATA["id"]].coordinator is coord
    assert devices[DATA["id"]].account is coord.account


@pytest.mark.asyncio
async def test_refresh_returns_only_current_account_devices(coord):
    other = Device({**DATA, "id": "other-device"}, MagicMock())
    coord.hass.data[DOMAIN][CONF_DEVICES][other.id] = other
    with patch.object(VisualC07Device, "async_init", new_callable=AsyncMock):
        devices = await coord._async_update_data()
        assert set(devices) == {DATA["id"]}
        coord.account.get_devices.return_value = []
        assert await coord._async_update_data() == {}
    assert coord.hass.data[DOMAIN][CONF_DEVICES][other.id] is other
    assert DATA["id"] not in coord.hass.data[DOMAIN][CONF_DEVICES]


@pytest.mark.asyncio
async def test_unload_failure_keeps_runtime(coord):
    from custom_components.catlink import async_unload_entry

    entry = MagicMock(entry_id="test-entry", data={"phone_iac": "86", "phone": "test"})
    domain = coord.hass.data[DOMAIN]
    domain.update(
        {
            "entry_coordinators": {entry.entry_id: coord},
            "accounts": {},
            "coordinators": {coord.name: coord},
        }
    )
    with patch.object(
        coord.hass.config_entries,
        "async_unload_platforms",
        new_callable=AsyncMock,
        return_value=False,
    ):
        assert await async_unload_entry(coord.hass, entry) is False
    assert domain["entry_coordinators"][entry.entry_id] is coord


@pytest.mark.asyncio
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_real_entry_rediscovers_after_last_entity_disappears(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from custom_components.catlink import async_setup

    await async_setup(hass, {})
    acc = MagicMock(spec=Account)
    acc.hass = hass
    acc.uid = "86-synthetic"
    acc.update_interval = datetime.timedelta(seconds=60)
    acc.async_check_auth = AsyncMock()
    acc.get_devices = AsyncMock(return_value=[DATA])
    acc.get_cats = AsyncMock(return_value=[])
    acc.request = AsyncMock(
        return_value={
            "returnCode": 0,
            "data": {
                "deviceInfo": {"online": True, "workStatus": "00"},
                "info": {},
                "records": [],
            },
        }
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"phone_iac": "86", "phone": "synthetic"},
        options={"device_ids": [DATA["id"]]},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.catlink.Account", return_value=acc):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coord = hass.data[DOMAIN]["entry_coordinators"][entry.entry_id]
        assert len(coord._subs) == 22
        original = coord.data[DATA["id"]]
        acc.get_devices.side_effect = UpdateFailed("temporary outage")
        await coord.async_refresh()
        assert not coord.last_update_success
        assert coord.data[DATA["id"]] is original and len(coord._subs) == 22
        acc.get_devices.side_effect = None
        acc.get_devices.return_value = []
        await coord.async_refresh()
        await hass.async_block_till_done()
        assert coord.data == {} and coord._subs == {}
        assert coord._listeners and coord._unsub_refresh is not None
        acc.get_devices.return_value = [DATA]
        await coord.async_refresh()
        await hass.async_block_till_done()
        assert DATA["id"] in coord.data and len(coord._subs) == 22
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert coord._unsub_refresh is None
        assert not hass.data[DOMAIN]["devices"]
