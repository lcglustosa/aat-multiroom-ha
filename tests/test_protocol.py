"""Quick local sanity tests for the AAT protocol parser/encoder.

Run from the repo root:
    python tests/test_protocol.py

These tests use only the standard library so they work without HA installed.
"""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

# Allow running without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "custom_components" / "aat_multiroom"))

from aat_protocol import (  # noqa: E402
    AatClient,
    DeviceState,
    encode_command,
    parse_message,
)


def _check(label: str, got, expected) -> None:
    status = "OK " if got == expected else "FAIL"
    print(f"  [{status}] {label}: got={got!r} expected={expected!r}")
    if got != expected:
        sys.exit(1)


def test_encode() -> None:
    print("encode_command:")
    _check("PWRON",   encode_command(1, "PWRON"),                b"[t001 PWRON]")
    _check("PWRTOG",  encode_command(2, "PWRTOG"),               b"[t002 PWRTOG]")
    _check("VOLSET",  encode_command(1, "VOLSET", 1, 15),        b"[t001 VOLSET 1 15]")
    _check("VOLGET",  encode_command(2, "VOLGET", 4),            b"[t002 VOLGET 4]")
    _check("INPSET",  encode_command(1, "INPSET", 1, 1),         b"[t001 INPSET 1 1]")
    _check("ZSTDBYON", encode_command(7, "ZSTDBYON", 1),         b"[t007 ZSTDBYON 1]")
    _check("seq=999", encode_command(999, "PWRON"),              b"[t999 PWRON]")


def test_parse() -> None:
    print("parse_message:")

    _check("PWRON reply",
           parse_message("[r001 PWRON]"),
           ("r", 1, "PWRON", []))

    _check("PWRTOG ON",
           parse_message("[r001 PWRTOG ON]"),
           ("r", 1, "PWRTOG", ["ON"]))

    _check("VOLGET",
           parse_message("[r002 VOLGET 4 40]"),
           ("r", 2, "VOLGET", ["4", "40"]))

    _check("VOLSET",
           parse_message("[r001 VOLSET 1 15]"),
           ("r", 1, "VOLSET", ["1", "15"]))

    _check("ZSTDBYGET ON",
           parse_message("[r001 ZSTDBYGET 4 ON]"),
           ("r", 1, "ZSTDBYGET", ["4", "ON"]))

    _check("MUTEGET",
           parse_message("[r002 MUTEGET 4 OFF]"),
           ("r", 2, "MUTEGET", ["4", "OFF"]))

    _check("notification POWERDOWN",
           parse_message("[n001 POWERDOWN]"),
           ("n", 1, "POWERDOWN", []))

    _check("MODEL",
           parse_message("[R001 MODEL PMR4]"),
           ("r", 1, "MODEL", ["PMR4"]))

    _check("VER (multi-token reply)",
           parse_message("[R001 VER Multiroom V1.13]"),
           ("r", 1, "VER", ["Multiroom", "V1.13"]))

    _check("Lowercase type",
           parse_message("[t005 VOLSET 1 15]"),
           ("t", 5, "VOLSET", ["1", "15"]))

    _check("Garbage returns None", parse_message("not a message"), None)


# Spec example 10.2 for PMR-7 (6 zones):
SPEC_PMR7_GETALL = (
    "PMR7 V1.13 OFF 12345 60 "
    "6 30 OFF 14 14 20 7 "  # zone 1
    "5 30 OFF 14 14 20 7 "  # zone 2
    "5 30 OFF 14 14 20 7 "  # zone 3
    "5 30 OFF 14 14 20 7 "  # zone 4
    "5 30 OFF 14 14 20 7 "  # zone 5
    "5 30 OFF 14 14 20 7"   # zone 6
)


class _FakeStream:
    """Minimal asyncio stream pair that replays canned responses."""

    def __init__(self, replies: list[bytes]) -> None:
        self._replies = replies
        self._writes: list[bytes] = []
        self._buf = b""

    # Writer side
    def write(self, data: bytes) -> None:
        self._writes.append(data)
        # Pop the next canned reply into the read buffer.
        if self._replies:
            self._buf += self._replies.pop(0)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        pass

    def is_closing(self) -> bool:
        return False

    async def wait_closed(self) -> None:
        return None

    # Reader side
    async def read(self, n: int) -> bytes:
        if not self._buf:
            # Block forever — but tests should always have data ready.
            await asyncio.sleep(0.001)
            return b""
        chunk = self._buf[:n]
        self._buf = self._buf[n:]
        return chunk


def test_getall_parsing() -> None:
    print("get_all (PMR-7 spec example):")

    async def run() -> DeviceState:
        client = AatClient("dummy", num_zones=6)
        # Reply uses the seq from the request, which starts at 1.
        reply = f"[r001 GETALL {SPEC_PMR7_GETALL}]".encode("ascii")
        # Plus 6 ZSTDBYGET replies (zones 1..6, all OFF = playing)
        zstdby_replies = [
            f"[r{i + 2:03d} ZSTDBYGET {i + 1} OFF]".encode("ascii")
            for i in range(6)
        ]
        stream = _FakeStream([reply, *zstdby_replies])
        client._reader = stream  # type: ignore[assignment]
        client._writer = stream  # type: ignore[assignment]
        return await client.get_all()

    state = asyncio.run(run())

    _check("model",    state.model,    "PMR7")
    _check("firmware", state.firmware, "V1.13")
    _check("power",    state.power,    False)
    _check("zones #",  len(state.zones), 6)

    z1 = state.zones[1]
    _check("zone1 input",   z1.input,   6)
    _check("zone1 volume",  z1.volume,  30)
    _check("zone1 mute",    z1.mute,    False)
    _check("zone1 bass",    z1.bass,    14)
    _check("zone1 treble",  z1.treble,  14)
    _check("zone1 balance", z1.balance, 20)
    _check("zone1 preamp",  z1.preamp,  7)
    _check("zone1 standby (from ZSTDBYGET)", z1.standby, False)

    z6 = state.zones[6]
    _check("zone6 input",  z6.input,  5)
    _check("zone6 volume", z6.volume, 30)


if __name__ == "__main__":
    test_encode()
    test_parse()
    test_getall_parsing()
    print("\nAll protocol tests passed.")
