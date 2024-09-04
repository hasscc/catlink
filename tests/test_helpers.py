from custom_components.catlink.helpers import Helper

from datetime import timedelta
from homeassistant.core import HomeAssistant
from custom_components.catlink import const
from unittest.mock import MagicMock, AsyncMock
class TestHelper:


    async def test_calculate_update_interval(self) -> None:

        assert Helper.calculate_update_interval("00:11:00") == timedelta(hours=0, minutes=11, seconds=0)
        # test default value
        assert Helper.calculate_update_interval(None) == timedelta(minutes=10)

    
    async def test_async_setup_accounts(cls, hass: HomeAssistant) -> None:
        hass.data = {}
        mocked_coordinator = MagicMock()
        mocked_coordinator.update_hass_entities = AsyncMock()
        mocked_coordinator.data = MagicMock(return_value={})
        hass.data[const.DOMAIN] = {
            'coordinators': {
                'coordinator_1': mocked_coordinator
            }
        }
        assert Helper.async_setup_accounts(hass, {})