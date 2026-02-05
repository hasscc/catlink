"""Logs mixin for devices with log support."""

import datetime
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ...const import _LOGGER, DOMAIN
from ...models.api.logs import LogEntry
from ...models.api.parse import parse_response


class LogsMixin:
    """Mixin providing logs, coordinator_logs, _last_log, last_log_attrs and log coordinator setup."""

    logs: list
    coordinator_logs: DataUpdateCoordinator | None

    async def _async_init_logs(self) -> None:
        """Initialize the logs coordinator. Call from async_init after super().async_init()."""
        self.logs = []
        self.coordinator_logs = DataUpdateCoordinator(
            self.account.hass,
            _LOGGER,
            name=f"{DOMAIN}-{self.id}-logs",
            update_method=self.update_logs,
            update_interval=datetime.timedelta(minutes=1),
        )
        await self.coordinator_logs.async_refresh()

    @property
    def _last_log(self) -> dict[str, Any]:
        """Return the last log entry as a dict."""
        log: dict[str, Any] = {}
        if self.logs:
            log = self.logs[0] or {}
        return log

    @property
    def last_log(self) -> str | None:
        """Return the last log as a formatted string."""
        log = self._last_log
        if not log:
            return None
        return f"{log.get('time')} {log.get('event')}"

    def last_log_attrs(self) -> dict[str, Any]:
        """Return the last log attributes for entity extra state."""
        log = self._last_log
        return {
            **log,
            "logs": self.logs,
        }

    async def _fetch_logs(self, api: str, response_key: str) -> list:
        """Fetch logs from API. Subclasses call this from update_logs with their api path and response key."""
        pms = {"deviceId": self.id}
        rsp = None
        try:
            rsp = await self.account.request(api, pms)
            data = rsp.get("data", {})
            parsed = parse_response(data, response_key, LogEntry, [])
            if isinstance(parsed, list) and parsed and hasattr(parsed[0], "model_dump"):
                rdt = [p.model_dump() for p in parsed]
            elif isinstance(parsed, list):
                rdt = parsed
            else:
                rdt = data.get(response_key) or []
        except (TypeError, ValueError) as exc:
            rdt = []
            _LOGGER.error("Got device logs for %s failed: %s", self.name, exc)
        if not rdt:
            _LOGGER.warning("Got device logs for %s failed: %s", self.name, rsp)
        self.logs = rdt
        self._handle_listeners()
        return rdt
