"""Polling coordinator for AAT Multiroom.

The AAT does not push state changes (other than POWERDOWN), so we keep state
fresh with a periodic GETALL — relatively cheap because it returns everything
in one round-trip.

We also cache the AatClient on the coordinator so all entities share one TCP
connection, and we reconnect on demand if the link drops.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .aat_protocol import AatClient, AatError, DeviceState
from .const import CONF_NUM_ZONES, DEFAULT_NUM_ZONES, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AatCoordinator(DataUpdateCoordinator[DeviceState]):
    """Coordinator that polls the AAT and shares one TCP client."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.client = AatClient(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            num_zones=entry.data.get(CONF_NUM_ZONES, DEFAULT_NUM_ZONES),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{entry.data[CONF_HOST]}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> DeviceState:
        try:
            return await self.client.get_all()
        except AatError as err:
            raise UpdateFailed(f"AAT poll failed: {err}") from err

    async def async_shutdown(self) -> None:
        """Close TCP connection on integration unload."""
        await self.client.disconnect()

    # Convenience: kick off an immediate refresh after a control command.
    async def async_request_refresh_soon(self) -> None:
        await self.async_request_refresh()
