"""A virtual printer that speaks both protocols. Great for tests, CI and previews without hardware.

    printer = await purrint.connect_simulated("MX10")
    await printer.print_text("hello")
    printer.simulator.pages[-1].save("page.png")
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

from PIL import Image

from .catalog import Family, PrinterModel, generic_model, get_model
from .crc import crc8
from .protocol import v5g, v5x
from .protocol.frames import build, parse_frames
from .transport import NotifyHandler, Transport


class SimulatedTransport(Transport):
    """In-memory transport emulating a printer's replies.

    ``seconds_per_line`` controls how long the fake head takes, so completion timing can be tested.
    ``paper=False`` makes it report "out of paper"; ``overheated=True`` reports a hot head.
    """

    def __init__(
        self,
        model: PrinterModel,
        *,
        mtu: int = 247,
        seconds_per_line: float = 0.0,
        firmware: Optional[str] = None,
        paper: bool = True,
        overheated: bool = False,
        battery: int = 87,
        temperature: int = 31,
        acknowledge: bool = True,
    ) -> None:
        self.model = model
        self.name = model.label
        self.address = "00:11:22:33:44:55"
        self.mtu = mtu
        self.seconds_per_line = seconds_per_line
        self.firmware = firmware or ("1.0.11" if model.family is Family.V5G else "1.9.3.1.2")
        self.paper = paper
        self.overheated = overheated
        self.battery = battery
        self.temperature = temperature
        self.acknowledge = acknowledge
        self.pages: List[Image.Image] = []
        self.commands: List[tuple] = []
        self.settings: dict = {}
        self._handler: Optional[NotifyHandler] = None
        self._connected = True
        self._cmd = b""
        self._rows: List[bytes] = []
        self._data = bytearray()
        self._expect: Optional[tuple] = None
        self.raw_cmd = bytearray()
        self.raw_data = bytearray()

    # ------------------------------------------------------------------------- Transport API ----
    @property
    def is_connected(self) -> bool:
        return self._connected

    def set_notify_handler(self, handler: Optional[NotifyHandler]) -> None:
        self._handler = handler

    async def start(self, family: Optional[Family]) -> None:
        return

    async def close(self) -> None:
        self._connected = False

    async def write(self, data: bytes, *, channel: str = "cmd") -> None:
        if channel == "data":
            self.raw_data += data
            self._data += data
            return
        self.raw_cmd += data
        magic = v5g.MAGIC if self.model.family is Family.V5G else v5x.MAGIC
        frames, self._cmd = parse_frames(magic, self._cmd + bytes(data))
        for f in frames:
            self.commands.append((f.command, f.payload))
            if self.model.family is Family.V5G:
                self._v5g(f.command, f.payload)
            else:
                self._v5x(f.command, f.payload)

    # ----------------------------------------------------------------------------- helpers ----
    def _notify(self, magic: bytes, cmd: int, payload: bytes, delay: float = 0.0) -> None:
        packet = build(magic, cmd, payload, flag=1)
        loop = asyncio.get_running_loop()
        if self._handler is not None:
            loop.call_later(max(0.001, delay), self._handler, packet)

    def _state_flags(self) -> int:
        flags = 0
        if not self.paper:
            flags |= 0x01
        if self.overheated:
            flags |= 0x04
        return flags

    # --------------------------------------------------------------------------------- V5G ----
    def _v5g(self, cmd: int, p: bytes) -> None:
        m = v5g.MAGIC
        if cmd == v5g.CMD_GET_STATE:
            self._notify(m, cmd, bytes((self._state_flags(), 0x00, 0x35)))
        elif cmd == v5g.CMD_DEVICE_INFO:
            self._notify(m, cmd, b"\x51\x00\x00" + self.firmware.encode() + b"\x00")
        elif cmd == v5g.CMD_GET_SERIAL:
            self._notify(m, cmd, bytes.fromhex("BA724D91C128"))
        elif cmd == v5g.CMD_LATTICE and p == v5g.LATTICE_START:
            self._rows = []
        elif cmd == v5g.CMD_LINE:
            self._rows.append(p)
        elif cmd in (v5g.CMD_ENERGY, v5g.CMD_SPEED, v5g.CMD_QUALITY, v5g.CMD_DENSITY, v5g.CMD_MODE):
            self.settings[cmd] = p
        elif cmd == v5g.CMD_LATTICE and p == v5g.LATTICE_END:
            if self._rows:
                self.pages.append(_rows_to_image(self._rows, self.model.dots_per_line, gray=False))
                self._notify(m, v5g.CMD_TEMPERATURE, bytes((self.temperature,)), 0.01)
            duration = len(self._rows) * self.seconds_per_line
            self._rows = []
            self._notify(m, v5g.CMD_FLOW, b"\x00", duration + 0.02)

    # --------------------------------------------------------------------------------- V5X ----
    def _v5x(self, cmd: int, p: bytes) -> None:
        m = v5x.MAGIC
        if cmd == v5x.CMD_STATUS:
            error = 0x01 if not self.paper else 0x04 if self.overheated else 0x00
            payload = bytes((0x00, 0x00, 0x00, self.battery, self.temperature, 0x00, 0x01 if error else 0x00, error, 0x00))
            self._notify(m, cmd, payload)
        elif cmd == v5x.CMD_VERSION:
            self._notify(m, cmd, self.firmware.encode()[:9].ljust(9, b"\x00") + b"\x00\x02")
        elif cmd == v5x.CMD_HEAD_TYPE:
            self._notify(m, cmd, b"\x01")
        elif cmd == v5x.CMD_QUERY_COUNT:
            self._notify(m, cmd, bytes.fromhex("0000FFFF"))
        elif cmd == v5x.CMD_BATTERY:
            self._notify(m, cmd, bytes((self.battery,)))
        elif cmd == v5x.CMD_INTENSITY:
            self.settings[cmd] = p
        elif cmd == v5x.CMD_PRINT:
            lines = p[0] | (p[1] << 8)
            gray = len(p) > 3 and p[3] == v5x.MODE_GRAY
            self._expect = (lines, gray)
            self._data = bytearray()
            if self.acknowledge:
                code = 0x00 if self.paper and not self.overheated else 0x01
                self._notify(m, cmd, bytes((code,)))
        elif cmd == v5x.CMD_FLUSH and self._expect:
            lines, gray = self._expect
            bpl = v5x.bytes_per_line(self.model.dots_per_line, gray)
            rows = [bytes(self._data[i * bpl:(i + 1) * bpl]) for i in range(lines)]
            self.pages.append(_rows_to_image(rows, self.model.dots_per_line, gray=gray))
            self._expect = None
            self._notify(m, v5x.CMD_PRINT_DONE, b"\x00", lines * self.seconds_per_line + 0.02)


def _rows_to_image(rows: List[bytes], width: int, gray: bool) -> Image.Image:
    img = Image.new("L", (width, max(1, len(rows))), 255)
    px = img.load()
    for y, row in enumerate(rows):
        for x in range(width):
            if gray:
                byte = row[x >> 1] if (x >> 1) < len(row) else 0
                level = (byte >> 4) if not (x & 1) else (byte & 0x0F)
                px[x, y] = 255 - level * 17
            else:
                byte = row[x >> 3] if (x >> 3) < len(row) else 0
                px[x, y] = 0 if byte & (1 << (x & 7)) else 255
    return img


async def connect_simulated(model: str = "MX10", **kwargs: object):
    """A :class:`purrint.Printer` wired to a :class:`SimulatedTransport` (``printer.simulator``)."""
    from .printer import Printer

    m = get_model(model) or generic_model(model, Family.V5G)
    transport = SimulatedTransport(m, **kwargs)  # type: ignore[arg-type]
    printer = await Printer._from_transport(transport, m, m.label)
    printer.simulator = transport  # type: ignore[attr-defined]
    return printer


__all__ = ["SimulatedTransport", "connect_simulated", "crc8"]
