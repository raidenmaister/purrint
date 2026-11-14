"""V5X protocol ("22 21" frames) – MXW01 board: MXW01, X1, X2, C17 and the whole V5X_S group.

Job flow::

    host -> A2 intensity                (control characteristic)
    host -> A9 print request            (lines, 0x30, mode)
    printer -> A9 ack (payload 00 = ok)
    host -> raw bitmap                  (data characteristic, chunked)
    host -> AD flush
    printer -> AA                       (job finished)

Bitmap rows are 48 bytes for 1-bit printing (left-most dot in bit 0, 1 = black) or 192 bytes for
16-level grayscale (two dots per byte, left dot in the high nibble, 0 = white .. 15 = black).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from ..status import PrinterState, PrinterStatus
from .frames import Frame, build, parse_frames

MAGIC = b"\x22\x21"

CMD_STATUS = 0xA1
CMD_INTENSITY = 0xA2
CMD_FEED = 0xA3
CMD_QUERY_COUNT = 0xA7
CMD_PRINT = 0xA9
CMD_PRINT_DONE = 0xAA
CMD_BATTERY = 0xAB
CMD_CANCEL = 0xAC
CMD_FLUSH = 0xAD
CMD_HEAD_TYPE = 0xB0
CMD_VERSION = 0xB1
CMD_LEARN_LABEL = 0xB2
CMD_CHALLENGE = 0xB3

MODE_DOT = 0x00
MODE_GRAY = 0x02
MODE_LABEL = 0x03

#: Minimum number of rows some firmwares need before they start printing.
MIN_LINES = 90

DEFAULT_INTENSITY = 93


def frame(command: int, payload: bytes = b"\x00") -> bytes:
    return build(MAGIC, command, payload)


def _u16(value: int) -> bytes:
    value = max(0, min(0xFFFF, int(value)))
    return bytes((value & 0xFF, value >> 8))


def get_status() -> bytes:
    return frame(CMD_STATUS, b"\x00")


def get_version() -> bytes:
    return frame(CMD_VERSION, b"\x00")


def get_head_type() -> bytes:
    return frame(CMD_HEAD_TYPE, b"\x00")


def get_battery() -> bytes:
    return frame(CMD_BATTERY, b"\x00")


def query_count() -> bytes:
    return frame(CMD_QUERY_COUNT, b"\x00")


def set_intensity(value: int) -> bytes:
    """Darkness 0..100 (the vendor app uses ~88-98 for text/images and ~75-98 for grayscale)."""
    return frame(CMD_INTENSITY, bytes((max(0, min(255, int(value))),)))


def print_request(lines: int, mode: int = MODE_DOT) -> bytes:
    return frame(CMD_PRINT, _u16(lines) + bytes((0x30, mode & 0xFF)))


def flush() -> bytes:
    return frame(CMD_FLUSH, b"\x00")


def cancel() -> bytes:
    return frame(CMD_CANCEL, b"\x00")


def feed(lines: int) -> bytes:
    """Advance the paper by ``lines`` dot rows."""
    return frame(CMD_FEED, _u16(lines))


def bytes_per_line(width_dots: int, gray: bool = False) -> int:
    return (width_dots + 1) // 2 if gray else (width_dots + 7) // 8


def bitmap_payload(rows: Sequence[bytes], width_dots: int, gray: bool = False, min_lines: int = MIN_LINES) -> bytes:
    """Concatenate rows and pad with blank rows up to ``min_lines``."""
    bpl = bytes_per_line(width_dots, gray)
    out = bytearray()
    for row in rows:
        row = bytes(row)[:bpl]
        out += row + b"\x00" * (bpl - len(row))
    missing = max(0, min_lines - len(rows))
    out += b"\x00" * (bpl * missing)
    return bytes(out)


def padded_line_count(rows: int, min_lines: int = MIN_LINES) -> int:
    return max(rows, min_lines)


# ------------------------------------------------------------------------------ notifications ----
KIND_STATUS = "status"
KIND_PRINT_ACK = "print_ack"
KIND_PRINT_DONE = "print_done"
KIND_VERSION = "version"
KIND_HEAD_TYPE = "head_type"
KIND_BATTERY = "battery"
KIND_COUNT = "count"
KIND_CHALLENGE = "challenge"
KIND_OTHER = "other"

_STATE = {0: PrinterState.IDLE, 1: PrinterState.PRINTING, 2: PrinterState.FEEDING, 3: PrinterState.RETRACTING}


@dataclass(frozen=True)
class Notice:
    kind: str
    frame: Frame
    status: Optional[PrinterStatus] = None
    ok: Optional[bool] = None
    code: Optional[int] = None
    text: Optional[str] = None
    value: Optional[int] = None


def decode_status(p: bytes) -> PrinterStatus:
    """Decode an ``A1`` reply payload."""

    def at(i: int) -> Optional[int]:
        return p[i] if len(p) > i else None

    state = _STATE.get(at(0) or 0, PrinterState.UNKNOWN)
    battery = at(3)
    temperature = at(4)
    flag = at(6)
    error = at(7) if flag else None
    return PrinterStatus(
        state=state,
        out_of_paper=error in (0x01, 0x09),
        overheated=error == 0x04,
        low_battery=error == 0x08,
        battery_percent=battery if battery is not None and battery <= 100 else None,
        temperature_c=temperature,
        raw=p,
    )


def decode(frame_: Frame) -> Notice:
    cmd = frame_.command
    p = frame_.payload
    if cmd == CMD_STATUS:
        return Notice(KIND_STATUS, frame_, status=decode_status(p))
    if cmd == CMD_PRINT:
        code = p[0] if p else 0
        return Notice(KIND_PRINT_ACK, frame_, ok=code == 0, code=code)
    if cmd == CMD_PRINT_DONE:
        return Notice(KIND_PRINT_DONE, frame_)
    if cmd == CMD_VERSION:
        text = p[:9].split(b"\x00", 1)[0].decode("ascii", "replace").strip()
        return Notice(KIND_VERSION, frame_, text=text or None)
    if cmd == CMD_HEAD_TYPE:
        code = p[0] if p else 0xFF
        kind = "high_voltage" if code == 0x01 else "unknown" if code == 0xFF else "low_voltage"
        return Notice(KIND_HEAD_TYPE, frame_, text=kind, code=code)
    if cmd == CMD_BATTERY:
        return Notice(KIND_BATTERY, frame_, value=p[-1] if p else None)
    if cmd == CMD_QUERY_COUNT:
        return Notice(KIND_COUNT, frame_, text=p.hex().upper())
    if cmd == CMD_CHALLENGE:
        return Notice(KIND_CHALLENGE, frame_)
    return Notice(KIND_OTHER, frame_)


def decode_stream(data: bytes, pending: bytes = b"") -> "tuple[List[Notice], bytes]":
    frames, rest = parse_frames(MAGIC, pending + bytes(data))
    return [decode(f) for f in frames], rest


def head_type_from_version(version: Optional[str]) -> Optional[str]:
    """The last character of the firmware string encodes the head: 2 = high, 1 = low voltage."""
    if not version:
        return None
    return {"2": "high_voltage", "1": "low_voltage"}.get(version[-1], "unknown")
