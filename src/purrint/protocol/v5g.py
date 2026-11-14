"""V5G protocol ("51 78" frames) – MX10, MX06, MX05, GB0x-style and most cheap cat printers.

Job layout (as sent by the vendor app and verified on real hardware)::

    F2 density   A3 get-state   A4 quality   A6 lattice-start   AF energy   BE mode   BD speed
    A2 <line> x N
    BD feed-speed   A1 feed   A6 lattice-end   A3 get-state

The printer prints lines as they arrive. If its buffer fills it notifies ``AE 10`` (pause) and later
``AE 00`` (resume). After the last line it notifies ``AE 00`` once the paper has physically stopped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from ..status import PrinterState, PrinterStatus
from .frames import Frame, build, parse_frames

MAGIC = b"\x51\x78"

# Command identifiers
CMD_RETRACT = 0xA0
CMD_FEED = 0xA1
CMD_LINE = 0xA2
CMD_GET_STATE = 0xA3
CMD_QUALITY = 0xA4
CMD_LATTICE = 0xA6
CMD_DEVICE_INFO = 0xA8
CMD_FLOW = 0xAE
CMD_ENERGY = 0xAF
CMD_GET_SERIAL = 0xBB
CMD_SPEED = 0xBD
CMD_MODE = 0xBE
CMD_OVERHEAT = 0xD2
CMD_TEMPERATURE = 0xD3
CMD_CHALLENGE = 0xD6
CMD_DENSITY = 0xF2

LATTICE_START = bytes((0xAA, 0x55, 0x17, 0x38, 0x44, 0x5F, 0x5F, 0x5F, 0x44, 0x38, 0x2C))
LATTICE_END = bytes((0xAA, 0x55, 0x17, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x17))

MODE_IMAGE = 0x00
MODE_TEXT = 0x01

#: Seven heat levels used by the vendor app (light .. darkest). Level 4 (12000) is the app default.
ENERGY_LEVELS = (5000, 7000, 9500, 12000, 15000, 18000, 20000)

DEFAULT_SPEED = 0x0A
FEED_SPEED = 0x19
DEFAULT_QUALITY = 3
DEFAULT_FEED_LINES = 48


def frame(command: int, payload: bytes = b"\x00") -> bytes:
    return build(MAGIC, command, payload)


def _u16(value: int) -> bytes:
    value = max(0, min(0xFFFF, int(value)))
    return bytes((value & 0xFF, value >> 8))


# ---------------------------------------------------------------------------------- commands ----
def get_state() -> bytes:
    return frame(CMD_GET_STATE, b"\x00")


def get_device_info() -> bytes:
    return frame(CMD_DEVICE_INFO, b"\x00")


def get_serial() -> bytes:
    return frame(CMD_GET_SERIAL, b"\x01")


def set_density(value: int) -> bytes:
    """Model specific darkness value (see :class:`purrint.catalog.DensityProfile`)."""
    return frame(CMD_DENSITY, bytes((0x01, max(0, min(255, int(value))))))


def set_quality(level: int) -> bytes:
    """Print quality 1..5 (sent as 0x31..0x35)."""
    level = max(1, min(5, int(level)))
    return frame(CMD_QUALITY, bytes((0x30 + level,)))


def set_energy(energy: int) -> bytes:
    """Heat applied per dot (roughly 5000..20000; higher is darker and hotter)."""
    return frame(CMD_ENERGY, _u16(energy))


def set_speed(speed: int) -> bytes:
    """Motor speed divisor (smaller is faster). 10 for images, 25 for feeding."""
    return frame(CMD_SPEED, bytes((max(1, min(255, int(speed))),)))


def set_mode(mode: int = MODE_IMAGE) -> bytes:
    return frame(CMD_MODE, bytes((mode & 0xFF,)))


def lattice_start() -> bytes:
    return frame(CMD_LATTICE, LATTICE_START)


def lattice_end() -> bytes:
    return frame(CMD_LATTICE, LATTICE_END)


def feed(lines: int) -> bytes:
    """Advance the paper by ``lines`` dot rows (8 rows = 1 mm)."""
    return frame(CMD_FEED, _u16(lines))


def retract(lines: int) -> bytes:
    """Pull the paper back by ``lines`` dot rows (not supported by every firmware)."""
    return frame(CMD_RETRACT, _u16(lines))


def line(row: bytes) -> bytes:
    """One raster row, already packed with the left-most dot in bit 0 (1 = black)."""
    return frame(CMD_LINE, bytes(row))


def energy_for_level(level: int) -> int:
    level = max(1, min(len(ENERGY_LEVELS), int(level)))
    return ENERGY_LEVELS[level - 1]


@dataclass(frozen=True)
class JobSettings:
    energy: int = ENERGY_LEVELS[3]
    density_value: int = 120
    quality: int = DEFAULT_QUALITY
    speed: int = DEFAULT_SPEED
    feed_lines: int = DEFAULT_FEED_LINES
    mode: int = MODE_IMAGE


def build_job(rows: Sequence[bytes], settings: JobSettings = JobSettings()) -> bytes:
    """Complete print job for packed 1-bit rows."""
    out = bytearray()
    out += set_density(settings.density_value)
    out += get_state()
    out += set_quality(settings.quality)
    out += lattice_start()
    out += set_energy(settings.energy)
    out += set_mode(settings.mode)
    out += set_speed(settings.speed)
    for row in rows:
        out += line(row)
    out += set_speed(FEED_SPEED)
    if settings.feed_lines > 0:
        out += feed(settings.feed_lines)
    out += lattice_end()
    out += get_state()
    return bytes(out)


def build_feed_job(lines: int) -> bytes:
    return get_state() + lattice_start() + set_speed(FEED_SPEED) + feed(lines) + lattice_end() + get_state()


def build_cancel() -> bytes:
    """Close an interrupted job cleanly (closes the lattice, restores defaults, feeds a little)."""
    return (
        get_state()
        + set_quality(4)
        + lattice_end()
        + set_energy(ENERGY_LEVELS[3])
        + set_mode(MODE_IMAGE)
        + set_speed(DEFAULT_SPEED)
        + feed(DEFAULT_FEED_LINES)
    )


def bytes_per_line(width_dots: int) -> int:
    return (width_dots + 7) // 8


# ------------------------------------------------------------------------------ notifications ----
@dataclass(frozen=True)
class Notice:
    """Decoded printer notification. ``kind`` is one of the ``KIND_*`` constants."""

    kind: str
    frame: Frame
    status: Optional[PrinterStatus] = None
    temperature_c: Optional[int] = None
    text: Optional[str] = None


KIND_STATUS = "status"
KIND_BUFFER_FULL = "buffer_full"
KIND_BUFFER_FREE = "buffer_free"
KIND_TEMPERATURE = "temperature"
KIND_FIRMWARE = "firmware"
KIND_SERIAL = "serial"
KIND_OVERHEAT = "overheat"
KIND_CHALLENGE = "challenge"
KIND_OTHER = "other"


def decode_state(flags: int, raw: bytes) -> PrinterStatus:
    """Decode the first byte of an ``A3`` reply."""
    if flags == 0xD2:
        return PrinterStatus(state=PrinterState.UNKNOWN, overheated=True, raw=raw)
    return PrinterStatus(
        state=PrinterState.PRINTING if flags & 0x80 else PrinterState.IDLE,
        out_of_paper=bool(flags & 0x01),
        cover_open=bool(flags & 0x02),
        overheated=bool(flags & 0x04),
        low_battery=bool(flags & 0x08),
        raw=raw,
    )


def decode(frame_: Frame) -> Notice:
    cmd = frame_.command
    p = frame_.payload
    if cmd == CMD_GET_STATE and p:
        return Notice(KIND_STATUS, frame_, status=decode_state(p[0], p))
    if cmd == CMD_FLOW:
        if p and p[0] == 0x10:
            return Notice(KIND_BUFFER_FULL, frame_)
        return Notice(KIND_BUFFER_FREE, frame_)
    if cmd == CMD_TEMPERATURE and p:
        value = p[0]
        return Notice(KIND_TEMPERATURE, frame_, temperature_c=None if value >= 0xFE else value)
    if cmd == CMD_DEVICE_INFO and len(p) > 3:
        version = p[3:].split(b"\x00", 1)[0].decode("ascii", "replace").strip()
        return Notice(KIND_FIRMWARE, frame_, text=version or None)
    if cmd == CMD_GET_SERIAL and p:
        return Notice(KIND_SERIAL, frame_, text=p.hex().upper())
    if cmd == CMD_OVERHEAT:
        return Notice(KIND_OVERHEAT, frame_, status=PrinterStatus(overheated=True, raw=p))
    if cmd == CMD_CHALLENGE:
        return Notice(KIND_CHALLENGE, frame_)
    return Notice(KIND_OTHER, frame_)


def decode_stream(data: bytes, pending: bytes = b"") -> "tuple[List[Notice], bytes]":
    frames, rest = parse_frames(MAGIC, pending + bytes(data))
    return [decode(f) for f in frames], rest


def iter_notices(chunks: Iterable[bytes]) -> List[Notice]:
    pending = b""
    out: List[Notice] = []
    for chunk in chunks:
        notices, pending = decode_stream(chunk, pending)
        out.extend(notices)
    return out
