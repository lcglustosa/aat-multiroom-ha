"""AAT Multiroom — zone parameter number entities (bass, treble, balance, preamp).

Each zone exposes four sliders:
  - Graves (bass):   0..14  (7 = 0 dB, steps of 2 dB, range ±14 dB)
  - Agudos (treble): 0..14  (7 = 0 dB, steps of 2 dB, range ±14 dB)
  - Balanço (balance): 0..20 (10 = center, 0 = full left, 20 = full right)
  - Pré-Amp (preamp gain): 0..7 (0 = 0 dB, 7 = +14 dB)

Values come from GETALL polling — no extra round-trips needed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .aat_protocol import AatClient, AatError, ZoneState
from .const import (
    CONF_NUM_ZONES,
    CONF_ZONE_NAMES,
    DEFAULT_NUM_ZONES,
    DOMAIN,
)
from .coordinator import AatCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _NumberDef:
    key: str
    name: str
    icon: str
    native_min: float
    native_max: float
    get_value: Callable[[ZoneState], int]
    set_value: Callable[[AatClient, int, int], Coroutine[Any, Any, None]]


_ZONE_NUMBERS: tuple[_NumberDef, ...] = (
    _NumberDef(
        key="bass",
        name="Graves",
        icon="mdi:equalizer",
        native_min=0,
        native_max=14,
        get_value=lambda zs: zs.bass,
        set_value=lambda client, zone, v: client.set_bass(zone, v),
    ),
    _NumberDef(
        key="treble",
        name="Agudos",
        icon="mdi:equalizer-outline",
        native_min=0,
        native_max=14,
        get_value=lambda zs: zs.treble,
        set_value=lambda client, zone, v: client.set_treble(zone, v),
    ),
    _NumberDef(
        key="balance",
        name="Balanço",
        icon="mdi:pan-horizontal",
        native_min=0,
        native_max=20,
        get_value=lambda zs: zs.balance,
        set_value=lambda client, zone, v: client.set_balance(zone, v),
    ),
    _NumberDef(
        key="preamp",
        name="Pré-Amp",
        icon="mdi:amplifier",
        native_min=0,
        native_max=7,
        get_value=lambda zs: zs.preamp,
        set_value=lambda client, zone, v: client.set_preamp(zone, v),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AatCoordinator = hass.data[DOMAIN][entry.entry_id]
    num_zones = entry.data.get(CONF_NUM_ZONES, DEFAULT_NUM_ZONES)
    zone_names: dict[str, str] = entry.options.get(CONF_ZONE_NAMES, {}) or {}

    async_add_entities(
        AatZoneNumber(
            coordinator=coordinator,
            entry=entry,
            zone=zone,
            zone_name=zone_names.get(str(zone)) or f"Zona {zone}",
            defn=defn,
        )
        for zone in range(1, num_zones + 1)
        for defn in _ZONE_NUMBERS
    )


class AatZoneNumber(CoordinatorEntity[AatCoordinator], NumberEntity):
    """Zone parameter exposed as a number slider."""

    _attr_has_entity_name = True
    _attr_native_step = 1.0
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: AatCoordinator,
        entry: ConfigEntry,
        zone: int,
        zone_name: str,
        defn: _NumberDef,
    ) -> None:
        super().__init__(coordinator)
        self._zone = zone
        self._defn = defn
        self._host = entry.data[CONF_HOST]
        self._attr_unique_id = f"{self._host}_zone_{zone}_{defn.key}"
        self._attr_name = f"{zone_name} {defn.name}"
        self._attr_icon = defn.icon
        self._attr_native_min_value = defn.native_min
        self._attr_native_max_value = defn.native_max

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
        return (
            super().available
            and self.coordinator.data is not None
            and self._zone in self.coordinator.data.zones
        )

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        zs = self.coordinator.data.zones.get(self._zone)
        return float(self._defn.get_value(zs)) if zs is not None else None

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self._defn.set_value(self.coordinator.client, self._zone, int(value))
        except AatError as err:
            _LOGGER.error("AAT %s set failed for zone %s: %s", self._defn.key, self._zone, err)
            raise
        await self.coordinator.async_request_refresh()
