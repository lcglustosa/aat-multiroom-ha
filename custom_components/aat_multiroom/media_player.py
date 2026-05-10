"""Media player entities for AAT Multiroom — one per zone."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
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
    CONF_SOURCES,
    CONF_ZONE_NAMES,
    DEFAULT_NUM_ZONES,
    DOMAIN,
)
from .coordinator import AatCoordinator

_LOGGER = logging.getLogger(__name__)


SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    # VOLUME_MUTE intentionally omitted: when present, the HomeKit Bridge
    # exposes a separate Mute toggle which Apple Home renders as a duplicate
    # power-like tile, confusing the layout. Mute via the AAT MUTEON/OFF
    # protocol command is still available — just not surfaced through the
    # media_player entity. Use volume_set 0 if you need silence.
    | MediaPlayerEntityFeature.SELECT_SOURCE
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AatCoordinator = hass.data[DOMAIN][entry.entry_id]
    num_zones = entry.data.get(CONF_NUM_ZONES, DEFAULT_NUM_ZONES)
    zone_names: dict[str, str] = entry.options.get(CONF_ZONE_NAMES, {}) or {}
    sources: dict[str, str] = entry.options.get(CONF_SOURCES, {}) or {}

    entities = [
        AatZoneMediaPlayer(
            coordinator=coordinator,
            entry=entry,
            zone=z,
            zone_name=zone_names.get(str(z)) or f"Zona {z}",
            sources=sources,
        )
        for z in range(1, num_zones + 1)
    ]
    async_add_entities(entities)


class AatZoneMediaPlayer(CoordinatorEntity[AatCoordinator], MediaPlayerEntity):
    """One media_player entity per AAT zone."""

    _attr_has_entity_name = True
    _attr_supported_features = SUPPORTED_FEATURES
    # Use TV class so HomeKit Bridge exposes each zone as a Television
    # accessory in Apple Home — that's the only HA media-player rendering
    # that includes a real volume slider in the Casa tile. SPEAKER class
    # falls back to a basic on/off switch with no volume slider.
    _attr_device_class = MediaPlayerDeviceClass.TV

    def __init__(
        self,
        coordinator: AatCoordinator,
        entry: ConfigEntry,
        zone: int,
        zone_name: str,
        sources: dict[str, str],
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._zone = zone
        self._host = entry.data[CONF_HOST]
        self._sources_map = dict(sources)  # input number (str) -> friendly name
        self._sources_inverse = {v: int(k) for k, v in self._sources_map.items()}

        self._attr_unique_id = f"{self._host}_zone_{zone}"
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

    # --- helpers ------------------------------------------------------------

    @property
    def _zone_state(self):
        if not self.coordinator.data:
            return None
        return self.coordinator.data.zones.get(self._zone)

    async def _run_and_refresh(self, coro) -> None:
        """Run a control command, then refresh state."""
        try:
            await coro
        except AatError as err:
            _LOGGER.error("AAT command failed for zone %s: %s", self._zone, err)
            raise
        await self.coordinator.async_request_refresh()

    # --- properties ---------------------------------------------------------

    @property
    def available(self) -> bool:
        return super().available and self._zone_state is not None

    @property
    def state(self) -> MediaPlayerState | None:
        zs = self._zone_state
        if zs is None:
            return None
        if not self.coordinator.data.power:
            return MediaPlayerState.OFF
        if zs.standby:
            return MediaPlayerState.OFF
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        zs = self._zone_state
        if zs is None:
            return None
        return zs.volume / AAT_VOLUME_MAX

    @property
    def is_volume_muted(self) -> bool | None:
        zs = self._zone_state
        return None if zs is None else zs.mute

    @property
    def source(self) -> str | None:
        zs = self._zone_state
        if zs is None:
            return None
        return self._sources_map.get(str(zs.input)) or f"Entrada {zs.input}"

    @property
    def source_list(self) -> list[str]:
        # Show only configured sources; fall back to all four if nothing was set.
        if self._sources_map:
            return list(self._sources_map.values())
        return [f"Entrada {i}" for i in range(1, 5)]

    # --- commands -----------------------------------------------------------

    async def async_turn_on(self) -> None:
        # Make sure the device itself is powered up first.
        if self.coordinator.data and not self.coordinator.data.power:
            try:
                await self.coordinator.client.power_on()
            except AatError as err:
                _LOGGER.error("PWRON failed: %s", err)
                raise
        await self._run_and_refresh(self.coordinator.client.zone_on(self._zone))

    async def async_turn_off(self) -> None:
        await self._run_and_refresh(self.coordinator.client.zone_off(self._zone))

    async def async_set_volume_level(self, volume: float) -> None:
        aat_vol = round(max(0.0, min(1.0, volume)) * AAT_VOLUME_MAX)
        await self._run_and_refresh(
            self.coordinator.client.set_volume(self._zone, aat_vol)
        )

    async def async_volume_up(self) -> None:
        await self._run_and_refresh(self.coordinator.client.send("VOL+", self._zone))

    async def async_volume_down(self) -> None:
        await self._run_and_refresh(self.coordinator.client.send("VOL-", self._zone))

    async def async_mute_volume(self, mute: bool) -> None:
        if mute:
            await self._run_and_refresh(self.coordinator.client.mute_on(self._zone))
        else:
            await self._run_and_refresh(self.coordinator.client.mute_off(self._zone))

    async def async_select_source(self, source: str) -> None:
        # Resolve friendly name -> input number; also accept "Entrada N" fallbacks.
        input_num = self._sources_inverse.get(source)
        if input_num is None and source.lower().startswith("entrada"):
            try:
                input_num = int(source.split()[-1])
            except ValueError:
                pass
        if input_num is None:
            _LOGGER.warning("Unknown source %r for zone %s", source, self._zone)
            return
        await self._run_and_refresh(
            self.coordinator.client.set_input(self._zone, input_num)
        )
