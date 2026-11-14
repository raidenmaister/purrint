"""Common frame layout shared by both families.

``[magic0 magic1] [command] [flag] [length lo] [length hi] [payload ...] [crc8(payload)] [0xFF]``

``flag`` is 0x00 for host -> printer and usually 0x01 for printer -> host.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from ..crc import crc8


@dataclass(frozen=True)
class Frame:
    magic: bytes
    command: int
    flag: int
    payload: bytes
    crc_ok: bool

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"Frame({self.magic.hex()} cmd=0x{self.command:02X} flag={self.flag} "
            f"payload={self.payload.hex()} crc_ok={self.crc_ok})"
        )


def build(magic: bytes, command: int, payload: bytes = b"\x00", flag: int = 0) -> bytes:
    n = len(payload)
    return (
        magic
        + bytes((command & 0xFF, flag & 0xFF, n & 0xFF, (n >> 8) & 0xFF))
        + payload
        + bytes((crc8(payload), 0xFF))
    )


def parse_frames(magic: bytes, data: bytes) -> Tuple[List[Frame], bytes]:
    """Split ``data`` into frames. Returns the frames and any trailing incomplete bytes."""
    frames: List[Frame] = []
    i = 0
    n = len(data)
    while i < n:
        start = data.find(magic, i)
        if start < 0:
            return frames, b""
        if n - start < 8:
            return frames, data[start:]
        length = data[start + 4] | (data[start + 5] << 8)
        end = start + 6 + length + 2
        if length > 4096:
            i = start + 2  # garbage, resync
            continue
        if end > n:
            return frames, data[start:]
        payload = bytes(data[start + 6 : start + 6 + length])
        crc = data[start + 6 + length]
        frames.append(
            Frame(
                magic=magic,
                command=data[start + 2],
                flag=data[start + 3],
                payload=payload,
                crc_ok=crc == crc8(payload),
            )
        )
        i = end
    return frames, b""
