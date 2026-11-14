"""Printer status reported over Bluetooth."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field, replace
from typing import Optional


class PrinterState(str, enum.Enum):
    UNKNOWN = "unknown"
    IDLE = "idle"
    PRINTING = "printing"
    FEEDING = "feeding"
    RETRACTING = "retracting"


@dataclass(frozen=True)
class PrinterStatus:
    """Snapshot of what the printer last told us. ``None`` means "not reported by this model"."""

    state: PrinterState = PrinterState.UNKNOWN
    out_of_paper: bool = False
    overheated: bool = False
    low_battery: bool = False
    cover_open: bool = False
    battery_percent: Optional[int] = None
    temperature_c: Optional[int] = None
    raw: bytes = field(default=b"", repr=False)

    @property
    def ok(self) -> bool:
        """True when nothing prevents printing."""
        return not (self.out_of_paper or self.overheated or self.low_battery or self.cover_open)

    @property
    def problems(self) -> list:
        out = []
        if self.out_of_paper:
            out.append("out of paper")
        if self.cover_open:
            out.append("cover open")
        if self.overheated:
            out.append("print head overheated")
        if self.low_battery:
            out.append("battery low")
        return out

    def merged(self, **changes: object) -> "PrinterStatus":
        return replace(self, **changes)  # type: ignore[arg-type]


@dataclass(frozen=True)
class DeviceInfo:
    """Identity data that can be queried from the printer."""

    firmware: Optional[str] = None
    serial: Optional[str] = None
    head_type: Optional[str] = None
    """V5X only: ``"high_voltage"``, ``"low_voltage"`` or ``"unknown"``."""
