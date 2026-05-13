"""AAT Multiroom — device-level power switch.

Exposes a single switch entity that maps to the AAT's master power state
(PWRON / PWROFF / PWRGET). This is different from per-zone stand-by:

    PWRON/PWROFF   — global on/off of the whole amplifier. When OFF, no zone
                     can produce sound regardless of its own stand-by state.
    ZSTDBYON/OFF   — per-zone amp stand-by, exposed via the media_player
                     turn_on / turn_off on each zone entity.
    MUTEON/OFF     — per-zone mute (amp stays on, audio silenced), exposed
                     via volume_mute on each zone entity.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .aat_protocol import AatError
from .const import DOMAIN
from .coordinator import AatCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AatCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        AatPowerSwitch(coordinator, entry),
        AatMuteAllSwitch(coordinator, entry),
    ])


class AatPowerSwitch(CoordinatorEntity[AatCoordinator], SwitchEntity):
    """Master power switch for the AAT amplifier (PWRON / PWROFF)."""

    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator: AatCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._host = entry.data[CONF_HOST]
        self._attr_unique_id = f"{self._host}_power"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
            name=f"AAT Multiroom ({self._host})",
            manufacturer="Advanced Audio Technologies",
            model=self.coordinator.data.model if self.coordinator.data else "AAT Multiroom",
            sw_version=self.coordinator.data.firmware if self.coordinator.data else None,
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.power

    async def async_turn_on(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.power_on()
        except AatError as err:
            _LOGGER.error("PWRON failed: %s", err)
            raise
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.power_off()
        except AatError as err:
            _LOGGER.error("PWROFF failed: %s", err)
            raise
        await self.coordinator.async_request_refresh()


class AatMuteAllSwitch(CoordinatorEntity[AatCoordinator], SwitchEntity):
    """Global mute switch: ON = all zones muted, OFF = all zones unmuted."""

    _attr_has_entity_name = True
    _attr_name = "Mute All"
    _attr_icon = "mdi:volume-off"

    def __init__(self, coordinator: AatCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._host = entry.data[CONF_HOST]
        self._attr_unique_id = f"{self._host}_mute_all"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
            name=f"AAT Multiroom ({self._host})",
            manufacturer="Advanced Audio Technologies",
            model=self.coordinator.data.model if self.coordinator.data else "AAT Multiroom",
            sw_version=self.coordinator.data.firmware if self.coordinator.data else None,
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        zones = self.coordinator.data.zones
        if not zones:
            return False
        return all(zs.mute for zs in zones.values())

    async def async_turn_on(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.mute_all()
        except AatError as err:
            _LOGGER.error("MUTEALL failed: %s", err)
            raise
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.unmute_all()
        except AatError as err:
            _LOGGER.error("UNMUTEALL failed: %s", err)
            raise
        await self.coordinator.async_request_refresh()
