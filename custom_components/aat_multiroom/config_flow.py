"""Config flow for the AAT Multiroom integration.

Two-step user flow:
  1. Connection — host, port, number of zones. Validates by connecting and
     issuing MODEL/VER, so we know we're really talking to an AAT.
  2. Naming    — friendly names for each zone and each input/source.

Options flow lets the user re-edit the names later without losing config.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback

from .aat_protocol import AatClient, AatError
from .const import (
    CONF_NUM_ZONES,
    CONF_SOURCES,
    CONF_ZONE_NAMES,
    DEFAULT_NUM_ZONES,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


CONNECTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Optional(CONF_NUM_ZONES, default=DEFAULT_NUM_ZONES): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=6)
        ),
    }
)


async def _async_test_connection(
    host: str, port: int, num_zones: int
) -> tuple[str, str]:
    """Try to talk to the AAT. Returns (model, firmware) or raises AatError."""
    client = AatClient(host, port, num_zones=num_zones)
    try:
        await client.connect()
        model = await client.get_model()
        firmware = await client.get_firmware()
        return model, firmware
    finally:
        await client.disconnect()


def _default_zone_names(num_zones: int) -> dict[str, str]:
    return {str(i): f"Zona {i}" for i in range(1, num_zones + 1)}


def _default_sources() -> dict[str, str]:
    """Default source names — the user customizes per their actual hookup."""
    return {
        "1": "Entrada 1",
        "2": "Entrada 2",
        "3": "Entrada 3",
        "4": "Entrada 4",
    }


class AatConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            num_zones = user_input[CONF_NUM_ZONES]

            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            try:
                model, firmware = await _async_test_connection(host, port, num_zones)
            except AatError as err:
                _LOGGER.warning("AAT connection test failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                self._connection = {
                    CONF_HOST: host,
                    CONF_PORT: port,
                    CONF_NUM_ZONES: num_zones,
                    "model": model,
                    "firmware": firmware,
                }
                return await self.async_step_naming()

        return self.async_show_form(
            step_id="user",
            data_schema=CONNECTION_SCHEMA,
            errors=errors,
        )

    async def async_step_naming(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect friendly names for zones and sources."""
        num_zones = self._connection[CONF_NUM_ZONES]

        if user_input is not None:
            zone_names = {
                str(i): user_input[f"zone_{i}"] for i in range(1, num_zones + 1)
            }
            sources = {
                str(i): user_input[f"source_{i}"]
                for i in range(1, 5)
                if user_input.get(f"source_{i}", "").strip()
            }
            title = self._connection.get("model") or "AAT Multiroom"
            data = {
                CONF_HOST: self._connection[CONF_HOST],
                CONF_PORT: self._connection[CONF_PORT],
                CONF_NUM_ZONES: num_zones,
            }
            options = {
                CONF_ZONE_NAMES: zone_names,
                CONF_SOURCES: sources,
            }
            return self.async_create_entry(title=title, data=data, options=options)

        zone_defaults = _default_zone_names(num_zones)
        source_defaults = _default_sources()

        schema_dict: dict[Any, Any] = {}
        for i in range(1, num_zones + 1):
            schema_dict[
                vol.Required(f"zone_{i}", default=zone_defaults[str(i)])
            ] = str
        # Always offer 4 source slots; blanks are dropped.
        for i in range(1, 5):
            schema_dict[
                vol.Optional(f"source_{i}", default=source_defaults[str(i)])
            ] = str

        return self.async_show_form(
            step_id="naming",
            data_schema=vol.Schema(schema_dict),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AatOptionsFlow(config_entry)


class AatOptionsFlow(OptionsFlow):
    """Edit zone names and sources after initial setup."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        num_zones = self.config_entry.data[CONF_NUM_ZONES]
        current_zone_names: dict[str, str] = (
            self.config_entry.options.get(CONF_ZONE_NAMES) or _default_zone_names(num_zones)
        )
        current_sources: dict[str, str] = (
            self.config_entry.options.get(CONF_SOURCES) or _default_sources()
        )

        if user_input is not None:
            zone_names = {
                str(i): user_input[f"zone_{i}"] for i in range(1, num_zones + 1)
            }
            sources = {
                str(i): user_input[f"source_{i}"]
                for i in range(1, 5)
                if user_input.get(f"source_{i}", "").strip()
            }
            return self.async_create_entry(
                title="",
                data={
                    CONF_ZONE_NAMES: zone_names,
                    CONF_SOURCES: sources,
                },
            )

        schema_dict: dict[Any, Any] = {}
        for i in range(1, num_zones + 1):
            schema_dict[
                vol.Required(
                    f"zone_{i}", default=current_zone_names.get(str(i), f"Zona {i}")
                )
            ] = str
        for i in range(1, 5):
            schema_dict[
                vol.Optional(f"source_{i}", default=current_sources.get(str(i), ""))
            ] = str

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema_dict))
