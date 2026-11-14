"""CRC-8 used by both printer protocols (polynomial 0x07, init 0x00, no reflection, no final XOR)."""

from __future__ import annotations

from typing import Iterable


def _build_table() -> bytes:
    table = bytearray(256)
    for i in range(256):
        c = i
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
        table[i] = c
    return bytes(table)


_TABLE = _build_table()


def crc8(data: Iterable[int]) -> int:
    """Return the CRC-8/SMBUS checksum of ``data``."""
    c = 0
    for b in data:
        c = _TABLE[c ^ (b & 0xFF)]
    return c
