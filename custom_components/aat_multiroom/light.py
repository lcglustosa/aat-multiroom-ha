"""AAT Multiroom — zones exposed as Light entities (brightness = volume).

This is a deliberate "abuse" of the Light primitive so that Apple Home (via
HomeKit Bridge) renders each zone with a visible brightness slider — which
is the only way to get a visible volume slider for HA-bridged audio in iOS
Casa.

Mapping:
    Light on / off       <-> ZSTDBYOFF / ZSTDBYON  (zone amp out of / into stand-by)
    Light brightness 0..100%  <->  AAT volume 0..87 (1 dB per step)

Recommended use: expose ``light.aat_multiroom_<host>_<zone>`` plus
``switch.aat_multiroom_<host>_power`` (master) in the ``homekit:`` include
list. The media_player and switch zone entities still exist for the HA UI
and for voice control.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .aat_protocol import AatError
from .const import (
    AAT_VOLUME_MAX,
    CONF_NUM_ZONES,
    CONF_ZONE_NAMES,
    DEFAULT_NUM_ZONES,
    DOMAIN,
)
from .coordinator import AatCoordinator

_LOGGER = logging.getLogger(__name__)


def _volume_to_brightness(volume: int) -> int:
    """AAT 0..87 -> HA brightness 0..255."""
    if volume <= 0:
        return 0
    return max(1, round(volume / AAT_VOLUME_MAX * 255))


def _brightness_to_volume(brightness: int) -> int:
    """HA brightness 1..255 -> AAT 1..87."""
    if brightness <= 0:
        return 0
    return max(1, round(brightness / 255 * AAT_VOLUME_MAX))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AatCoordinator = hass.data[DOMAIN][entry.entry_id]
    num_zones = entry.data.get(CONF_NUM_ZONES, DEFAULT_NUM_ZONES)
    zone_names: dict[str, str] = entry.options.get(CONF_ZONE_NAMES, {}) or {}

    async_add_entities(
        AatZoneLight(
            coordinator,
            entry,
            zone,
            zone_names.get(str(zone)) or f"Zona {zone}",
        )
        for zone in range(1, num_zones + 1)
    )


class AatZoneLight(CoordinatorEntity[AatCoordinator], LightEntity):
    """Zone exposed as a Light: on/off + brightness (= volume)."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:speaker"
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(
        self,
        coordinator: AatCoordinator,
        entry: ConfigEntry,
        zone: int,
        zone_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._zone = zone
        self._host = entry.data[CONF_HOST]
        self._attr_unique_id = f"{self._host}_zone_{zone}_light"
        self._attr_name = zone_name

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
        if not self.coordinator.data.power:
            return False
        zs = self.coordinator.data.zones.get(self._zone)
        if zs is None:
            return None
        return not zs.standby

    @property
    def brightness(self) -> int | None:
        if self.coordinator.data is None:
            return None
        zs = self.coordinator.data.zones.get(self._zone)
        if zs is None:
            return None
        return _volume_to_brightness(zs.volume)

    async def async_turn_on(self, **kwargs: Any) -> None:
        # Bring the master up first if it's off.
        if self.coordinator.data and not self.coordinator.data.power:
            try:
                await self.coordinator.client.power_on()
            except AatError as err:
                _LOGGER.error("PWRON failed: %s", err)
                raise

        try:
            await self.coordinator.client.zone_on(self._zone)
        except AatError as err:
            _LOGGER.error("zone_on(%s) failed: %s", self._zone, err)
            raise

        if ATTR_BRIGHTNESS in kwargs:
            volume = _brightness_to_volume(kwargs[ATTR_BRIGHTNESS])
            try:
                await self.coordinator.client.set_volume(self._zone, volume)
            except AatError as err:
                _LOGGER.error("set_volume(%s) failed: %s", self._zone, err)
                raise

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.zone_off(self._zone)
        except AatError as err:
            _LOGGER.error("zone_off(%s) failed: %s", self._zone, err)
            raise
        await self.coordinator.async_request_refresh()
