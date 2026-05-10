"""AAT Multiroom — device-level button entities.

Exposes five buttons for bulk/device operations that would otherwise require
multiple service calls or are not reachable via the zone entities:

  - Ligar todas as zonas    → ZTONALL   (one round-trip vs N × zone_on)
  - Desligar todas as zonas → ZSTDBYALL (one round-trip vs N × zone_off)
  - Mutar tudo              → MUTEALL
  - Desmutar tudo           → UNMUTEALL
  - Resetar dispositivo     → RESET     (remote reboot over TCP)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .aat_protocol import AatClient, AatError
from .const import DOMAIN
from .coordinator import AatCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ButtonDef:
    key: str
    name: str
    icon: str
    press: Callable[[AatClient], Coroutine[Any, Any, None]]


_DEVICE_BUTTONS: tuple[_ButtonDef, ...] = (
    _ButtonDef(
        key="zones_all_on",
        name="Ligar todas as zonas",
        icon="mdi:speaker-multiple",
        press=lambda client: client.zone_on_all(),
    ),
    _ButtonDef(
        key="zones_all_off",
        name="Desligar todas as zonas",
        icon="mdi:speaker-off",
        press=lambda client: client.zone_off_all(),
    ),
    _ButtonDef(
        key="mute_all",
        name="Mutar tudo",
        icon="mdi:volume-mute",
        press=lambda client: client.mute_all(),
    ),
    _ButtonDef(
        key="unmute_all",
        name="Desmutar tudo",
        icon="mdi:volume-high",
        press=lambda client: client.unmute_all(),
    ),
    _ButtonDef(
        key="reset",
        name="Resetar dispositivo",
        icon="mdi:restart",
        press=lambda client: client.reset(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AatCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AatDeviceButton(coordinator, entry, defn) for defn in _DEVICE_BUTTONS
    )


class AatDeviceButton(CoordinatorEntity[AatCoordinator], ButtonEntity):
    """Device-level button (bulk zone commands and reset)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AatCoordinator,
        entry: ConfigEntry,
        defn: _ButtonDef,
    ) -> None:
        super().__init__(coordinator)
        self._host = entry.data[CONF_HOST]
        self._defn = defn
        self._attr_unique_id = f"{self._host}_{defn.key}"
        self._attr_name = defn.name
        self._attr_icon = defn.icon

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
            name=f"AAT Multiroom ({self._host})",
            manufacturer="Advanced Audio Technologies",
            model=self.coordinator.data.model if self.coordinator.data else "AAT Multiroom",
            sw_version=self.coordinator.data.firmware if self.coordinator.data else None,
        )

    async def async_press(self) -> None:
        try:
            await self._defn.press(self.coordinator.client)
        except AatError as err:
            _LOGGER.error("AAT button %s failed: %s", self._defn.key, err)
            raise
        await self.coordinator.async_request_refresh()
