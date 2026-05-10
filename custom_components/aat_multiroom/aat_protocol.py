"""AAT Multiroom Digital — async TCP protocol client.

Implements the AAT Digital Matrix Amplifier API (TCP/Serial/IR) Rev.10,
firmware V1.17. Tested against the PMR-4, but should work with PMR-5/6/7/8
since the protocol is shared.

Message format (ASCII, case-insensitive):
    Send:    [t<seq> <CMD> [par1 [par2 ...]]]
    Reply:   [r<seq> <CMD> [par1 [par2 ...]]]
    Notify:  [n<seq> <CMD> ...]    (unsolicited, e.g. POWERDOWN)

Sequence number is 001..999, three digits. Replies echo the request seq.
Notifications use their own counter.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 5000
RESPONSE_TIMEOUT = 5.0
CONNECT_TIMEOUT = 5.0

# Per spec section 5.1: volume is 0..87 (each step = 1 dB)
VOLUME_MIN = 0
VOLUME_MAX = 87

# Per spec section 8.1: inputs 1..6 depending on model. PMR-4 has 4.
INPUT_MIN = 1
INPUT_MAX = 8  # plataforma comporta até 8


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AatError(Exception):
    """Base error for AAT communication."""


class AatConnectionError(AatError):
    """Cannot reach the device or connection dropped."""


class AatProtocolError(AatError):
    """Received a malformed or unexpected message."""


class AatTimeout(AatError):
    """Timed out waiting for a response."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ZoneState:
    zone: int
    input: int = 1
    volume: int = 0
    mute: bool = False
    standby: bool = True   # True = zone is OFF (amplifier in stand-by)
    bass: int = 7          # 0..14, 7 = 0 dB
    treble: int = 7        # 0..14, 7 = 0 dB
    balance: int = 10      # 0..20, 10 = centered
    preamp: int = 0        # 0..7 (0 dB .. +14 dB)


@dataclass
class DeviceState:
    model: str = ""
    firmware: str = ""
    power: bool = False                          # whole device on/off
    zones: dict[int, ZoneState] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parser / encoder
# ---------------------------------------------------------------------------

# Anchored at start so we only ever match a single framed message.
_MSG_RE = re.compile(r"\[\s*([trnTRN])\s*(\d{3})\s+([^\s\]]+)([^\]]*)\]")


def parse_message(raw: str) -> Optional[tuple[str, int, str, list[str]]]:
    """Parse a single framed AAT message.

    Returns (type, seq, cmd, params) or None if it doesn't match.
    type is one of "t", "r", "n" (lowercase).
    """
    m = _MSG_RE.match(raw)
    if not m:
        return None
    msg_type = m.group(1).lower()
    seq = int(m.group(2))
    cmd = m.group(3).upper()
    params_raw = m.group(4).strip()
    params = params_raw.split() if params_raw else []
    return msg_type, seq, cmd, params


def encode_command(seq: int, cmd: str, *params) -> bytes:
    """Encode an outgoing command into ASCII bytes."""
    parts = [f"[t{seq:03d}", cmd.upper()]
    parts.extend(str(p) for p in params)
    return (" ".join(parts) + "]").encode("ascii")


# ---------------------------------------------------------------------------
# Async client
# ---------------------------------------------------------------------------


class AatClient:
    """Async TCP client for the AAT Multiroom Digital line."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        num_zones: int = 4,
    ) -> None:
        self._host = host
        self._port = port
        self._num_zones = num_zones
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._seq = 0
        self._lock = asyncio.Lock()
        self._buffer = ""

    # --- connection lifecycle -----------------------------------------------

    async def connect(self) -> None:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=CONNECT_TIMEOUT,
            )
            _LOGGER.debug("Connected to %s:%s", self._host, self._port)
        except (asyncio.TimeoutError, OSError) as err:
            raise AatConnectionError(
                f"Cannot connect to {self._host}:{self._port}: {err}"
            ) from err

    async def disconnect(self) -> None:
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except OSError:
                pass
        self._reader = None
        self._writer = None
        self._buffer = ""

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    # --- internal helpers ---------------------------------------------------

    def _next_seq(self) -> int:
        self._seq = (self._seq % 999) + 1
        return self._seq

    async def _read_message(self) -> tuple[str, int, str, list[str]]:
        """Read exactly one framed message from the socket."""
        assert self._reader is not None

        while True:
            # If we already have a full frame in the buffer, return it.
            start = self._buffer.find("[")
            if start != -1:
                end = self._buffer.find("]", start)
                if end != -1:
                    raw = self._buffer[start : end + 1]
                    self._buffer = self._buffer[end + 1 :]
                    parsed = parse_message(raw)
                    if parsed is None:
                        raise AatProtocolError(f"Cannot parse message: {raw!r}")
                    return parsed

            # Otherwise pull more bytes.
            try:
                chunk = await self._reader.read(4096)
            except OSError as err:
                raise AatConnectionError(f"Read failed: {err}") from err

            if not chunk:
                raise AatConnectionError("Connection closed by remote")
            self._buffer += chunk.decode("ascii", errors="ignore")

    async def send(self, cmd: str, *params) -> list[str]:
        """Send a command, await the matching reply, return reply params."""
        async with self._lock:
            if not self.connected:
                await self.connect()

            seq = self._next_seq()
            data = encode_command(seq, cmd, *params)
            _LOGGER.debug("AAT TX: %s", data)

            try:
                self._writer.write(data)
                await self._writer.drain()
            except OSError as err:
                # Drop the socket so the next call reconnects.
                await self.disconnect()
                raise AatConnectionError(f"Write failed: {err}") from err

            loop = asyncio.get_event_loop()
            deadline = loop.time() + RESPONSE_TIMEOUT
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise AatTimeout(f"No response for {cmd}")
                try:
                    msg_type, msg_seq, msg_cmd, params_out = await asyncio.wait_for(
                        self._read_message(), timeout=remaining
                    )
                except asyncio.TimeoutError as err:
                    raise AatTimeout(f"No response for {cmd}") from err

                _LOGGER.debug(
                    "AAT RX: type=%s seq=%d cmd=%s params=%s",
                    msg_type,
                    msg_seq,
                    msg_cmd,
                    params_out,
                )

                if msg_type == "n":
                    # Unsolicited (e.g. POWERDOWN). Log and keep waiting.
                    _LOGGER.info("AAT notification: %s %s", msg_cmd, params_out)
                    continue
                if msg_type == "r" and msg_seq == seq:
                    return params_out
                # Unexpected reply — drop it but keep waiting for ours.
                _LOGGER.warning(
                    "Discarding unexpected message type=%s seq=%d cmd=%s",
                    msg_type,
                    msg_seq,
                    msg_cmd,
                )

    # --- high-level commands ------------------------------------------------

    async def power_on(self) -> None:
        """Turn the whole MD on."""
        await self.send("PWRON")

    async def power_off(self) -> None:
        """Turn the whole MD off."""
        await self.send("PWROFF")

    async def get_power(self) -> bool:
        params = await self.send("PWRGET")
        return bool(params) and params[0].upper() == "ON"

    async def zone_on(self, zone: int) -> None:
        """Take zone out of stand-by (zone is now playing)."""
        await self.send("ZSTDBYOFF", zone)

    async def zone_off(self, zone: int) -> None:
        """Put zone in stand-by (amp powered down, line/sub muted)."""
        await self.send("ZSTDBYON", zone)

    async def zone_get_standby(self, zone: int) -> bool:
        """Return True if zone is in stand-by (i.e., the zone is OFF)."""
        params = await self.send("ZSTDBYGET", zone)
        return len(params) >= 2 and params[1].upper() == "ON"

    async def set_volume(self, zone: int, volume: int) -> None:
        v = max(VOLUME_MIN, min(VOLUME_MAX, int(volume)))
        await self.send("VOLSET", zone, v)

    async def get_volume(self, zone: int) -> int:
        params = await self.send("VOLGET", zone)
        return int(params[1]) if len(params) >= 2 else 0

    async def set_input(self, zone: int, input_num: int) -> None:
        await self.send("INPSET", zone, int(input_num))

    async def get_input(self, zone: int) -> int:
        params = await self.send("INPGET", zone)
        return int(params[1]) if len(params) >= 2 else 1

    async def mute_on(self, zone: int) -> None:
        await self.send("MUTEON", zone)

    async def mute_off(self, zone: int) -> None:
        await self.send("MUTEOFF", zone)

    async def get_mute(self, zone: int) -> bool:
        params = await self.send("MUTEGET", zone)
        return len(params) >= 2 and params[1].upper() == "ON"

    async def get_model(self) -> str:
        params = await self.send("MODEL")
        return params[0] if params else ""

    async def get_firmware(self) -> str:
        params = await self.send("VER")
        # Reply is e.g. "Multiroom V1.13" — return the joined tail.
        return " ".join(params) if params else ""

    async def get_all(self) -> DeviceState:
        """Read MODEL/VER/POWER + per-zone state in one call.

        Per spec section 10.2 the reply layout is:
            MODEL VER POWER TCPPORT TCPTIMEOUT
            then per zone (in order): INPUT VOLUME MUTE BASS TREBLE BALANCE PREAMP

        Note: the spec table has typos (PAR11/PAR12 say BALANÇO2/PRE-AMP2 but
        they are zone 1's; the example confirms 7 fields per zone in zone order).

        GETALL does NOT include zone stand-by, so we follow up with one
        ZSTDBYGET per zone.
        """
        params = await self.send("GETALL")
        if len(params) < 5:
            raise AatProtocolError(f"GETALL response too short: {params}")

        state = DeviceState(
            model=params[0],
            firmware=params[1],
            power=params[2].upper() == "ON",
        )

        idx = 5  # skip model, ver, power, tcpport, tcptimeout
        per_zone = 7
        zone = 1
        while zone <= self._num_zones and idx + per_zone <= len(params):
            try:
                zs = ZoneState(
                    zone=zone,
                    input=int(params[idx + 0]),
                    volume=int(params[idx + 1]),
                    mute=params[idx + 2].upper() == "ON",
                    bass=int(params[idx + 3]),
                    treble=int(params[idx + 4]),
                    balance=int(params[idx + 5]),
                    preamp=int(params[idx + 6]),
                )
            except (ValueError, IndexError) as err:
                raise AatProtocolError(
                    f"Bad GETALL zone {zone} fields at idx {idx}: {params[idx:idx + per_zone]}"
                ) from err
            state.zones[zone] = zs
            idx += per_zone
            zone += 1

        # Stand-by is not returned by GETALL — pull it per zone.
        for z_num in state.zones:
            try:
                state.zones[z_num].standby = await self.zone_get_standby(z_num)
            except AatError as err:
                _LOGGER.warning("Could not read standby for zone %s: %s", z_num, err)

        return state
