"""Catalog of known printer names and the protocol family each one speaks.

The printers are sold under hundreds of brand names, but almost all of them run one of two firmware
families:

* ``V5G`` – the classic "cat printer" protocol (frames start with ``51 78``). MX10, MX06, MX05, GB01-style.
* ``V5X`` – the MXW01-board protocol (frames start with ``22 21``). MXW01, X1, C17 and the large
  ``V5X_S`` ("simplified") group, which speaks exactly the same protocol.

A printer is identified by the Bluetooth name it advertises. Names are compared ignoring case and
whitespace, the same way the official apps do (``"CYLO BT PRINTER"`` == ``"CYLOBTPRINTER"``).
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Tuple


class Family(str, enum.Enum):
    """Wire protocol spoken by a printer."""

    V5G = "V5G"
    """``51 78`` frames, one command per raster line, flow control on the notify channel."""

    V5X = "V5X"
    """``22 21`` frames, whole bitmap streamed on a separate data channel (MXW01 board)."""

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class Kind(str, enum.Enum):
    """Product kind as grouped by the vendor app."""

    MINI_PRINTER = "mini_printer"
    AI_PRINTER = "ai_printer"
    AI_PRINTER_WITH_SCREEN = "ai_printer_with_screen"
    AI_CAMERA = "ai_camera"


_MODULE_KIND = {
    "P0": Kind.MINI_PRINTER,
    "P1": Kind.AI_PRINTER,
    "P3": Kind.AI_PRINTER_WITH_SCREEN,
    "Z1": Kind.AI_CAMERA,
}


@dataclass(frozen=True)
class DensityLevels:
    """Low / medium / high raw values of a density scale (``max`` is the top of the scale)."""

    low: int
    middle: int
    high: int
    max: int

    def at(self, level: int, levels: int = 7) -> int:
        """Interpolate a 1..``levels`` density level onto low..middle..high."""
        level = max(1, min(levels, level))
        mid = (levels + 1) / 2
        if level <= mid:
            t = (level - 1) / (mid - 1) if mid > 1 else 1.0
            value = self.low + (self.middle - self.low) * t
        else:
            t = (level - mid) / (levels - mid)
            value = self.middle + (self.high - self.middle) * t
        return int(round(min(self.max, value)))


@dataclass(frozen=True)
class DensityProfile:
    """Per-model density tuning (V5G ``F2`` value or V5X intensity) for text and images."""

    text: DensityLevels
    image: DensityLevels
    gray: Optional[DensityLevels] = None


@dataclass(frozen=True)
class PrinterModel:
    """Static description of a printer model."""

    name: str
    """Normalised Bluetooth name (upper case, no spaces)."""

    family: Family
    """Protocol family used to talk to it."""

    vendor_model: str
    """Model code used by the vendor app (``V5G``, ``V5X`` or ``V5X_S``)."""

    kind: Kind = Kind.MINI_PRINTER
    simplified: bool = False
    """The vendor app shows a reduced feature set for this model."""

    display_name: Optional[str] = None
    dots_per_line: int = 384
    """Printable width in dots (384 dots = 48 mm at 203 dpi)."""

    dpi: int = 203
    density: Optional[DensityProfile] = None
    reports_overheat_d2: bool = False
    """Sends the dedicated ``51 78 D2`` overheat notification."""

    reports_low_battery: bool = False
    supports_gray: bool = False
    """Can print 16-level grayscale (V5X family)."""

    aliases: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def label(self) -> str:
        return self.display_name or self.name

    @property
    def mxw01_board(self) -> bool:
        """True for every V5X/V5X_S device (they share the MXW01 board protocol)."""
        return self.family is Family.V5X


# --------------------------------------------------------------------------------------------------
# Raw catalog: (normalised name, vendor model, vendor module, simplified)
# --------------------------------------------------------------------------------------------------
_RAW: Tuple[Tuple[str, str, str, bool], ...] = (
    ("MX01", "V5G", "P0", False),
    ("MX02", "V5G", "P0", False),
    ("MX03", "V5G", "P0", False),
    ("MX05", "V5G", "P0", False),
    ("MX06", "V5G", "P0", False),
    ("MINIPRINTER", "V5G", "P0", False),
    ("JL-BR22", "V5G", "P0", False),
    ("MX07", "V5G", "P0", False),
    ("MX08", "V5G", "P0", False),
    ("MX09", "V5G", "P0", False),
    ("URBANWORXKIDSCAMERA", "V5G", "P0", False),
    ("CYLOBTPRINTER", "V5G", "P0", False),
    ("MXTP-100", "V5G", "P0", False),
    ("AZ-P2108X", "V5G", "P0", False),
    ("MX10", "V5G", "P0", False),
    ("MX11", "V5G", "P0", False),
    ("MX12", "V5G", "P0", False),
    ("PD01", "V5G", "P0", True),
    ("MINISO-M1", "V5G", "P0", True),
    ("LP212", "V5G", "P0", False),
    ("XOPOPPY", "V5G", "P0", False),
    ("MX13", "V5G", "P0", False),
    ("BQ01", "V5G", "P0", False),
    ("BQ02", "V5G", "P0", False),
    ("EWTTOET-Z0499", "V5G", "P0", False),
    ("BQ05", "V5G", "P0", False),
    ("BQ06", "V5G", "P0", False),
    ("BQ07", "V5G", "P0", False),
    ("BQ7A", "V5G", "P0", False),
    ("BQ7B", "V5G", "P0", False),
    ("BQ08", "V5G", "P0", False),
    ("BQ95", "V5G", "P0", False),
    ("BQ96", "V5G", "P0", False),
    ("MXW009", "V5G", "P0", False),
    ("MXW010", "V5G", "P0", False),
    ("EWTTOET-N3689", "V5G", "P0", False),
    ("EWTTOET-N3687", "V5G", "P0", False),
    ("MXPC-100", "V5G", "P0", False),
    ("GV-MA211", "V5G", "P0", False),
    ("KP-IM606", "V5G", "P0", False),
    ("BQ95B", "V5G", "P0", False),
    ("BQ03", "V5G", "P0", False),
    ("BQ95C", "V5G", "P0", False),
    ("BQ06B", "V5G", "P0", False),
    ("X6", "V5G", "P0", False),
    ("K06", "V5G", "P0", False),
    ("BQ17", "V5G", "P0", False),
    ("IM.17", "V5G", "P0", True),
    ("C18", "V5G", "P0", False),
    ("MINISO-M12", "V5G", "P0", True),
    ("MXW01", "V5X", "P0", False),
    ("X1", "V5X", "P0", False),
    ("X2", "V5X", "P0", False),
    ("C17", "V5X", "P0", False),
    ("MXW-W5", "V5X", "P0", True),
    ("MXW01-1", "V5X", "P0", False),
    ("PORTABLEPRINTER", "V5X_S", "P0", False),
    ("INSTANTPRINTPLUS", "V5X_S", "P0", False),
    ("REKA", "V5X_S", "P0", False),
    ("HDMDT-00", "V5X_S", "P0", False),
    ("JK01", "V5X_S", "P0", False),
    ("BH03", "V5X_S", "P0", False),
    ("BHSZY", "V5X_S", "P0", False),
    ("PD03", "V5X_S", "P0", True),
    ("FLYINGTIGER097", "V5X_S", "P0", False),
    ("LP215", "V5X_S", "P0", False),
    ("KERUI", "V5X_S", "P1", False),
    ("AI01", "V5X_S", "P1", False),
    ("M8HZ", "V5X_S", "P1", False),
    ("HZ-M8", "V5X_S", "P1", False),
    ("Q15", "V5X_S", "P3", False),
    ("M13", "V5X_S", "P3", False),
    ("Q15A", "V5X_S", "P3", False),
    ("Q15B", "V5X_S", "P3", False),
    ("Q15C", "V5X_S", "P3", False),
    ("Q15D", "V5X_S", "P3", False),
    ("Q15E", "V5X_S", "P3", False),
    ("Q15Z", "V5X_S", "P3", False),
    ("STICKERMATE", "V5X_S", "P3", False),
    ("Q17", "V5X_S", "P3", False),
    ("MXW13", "V5X_S", "P3", False),
    ("MXW18", "V5X_S", "P3", False),
    ("ADQ19", "V5X_S", "P3", False),
    ("QD01", "V5X_S", "P3", False),
    ("JME13", "V5X_S", "P3", False),
    ("JME15", "V5X_S", "P3", False),
    ("LP28AI", "V5X_S", "P3", False),
    ("BQTLY", "V5X_S", "P3", False),
    ("STERENIA-PRINT", "V5X_S", "P3", False),
    ("LEAPOM", "V5X_S", "P3", False),
    ("IHEARTYARD", "V5X_S", "P3", False),
    ("ELECOUTEK", "V5X_S", "P3", False),
    ("Q25SZY", "V5X_S", "P3", False),
    ("TCM747736", "V5X_S", "P3", False),
    ("P4", "V5X_S", "P3", False),
    ("RS6301985", "V5X_S", "P3", False),
    ("M13SZY", "V5X_S", "P3", False),
    ("TK914", "V5X_S", "P3", False),
    ("TK894", "V5X_S", "P3", False),
    ("D20", "V5X_S", "P3", False),
    ("Q20", "V5X_S", "P3", False),
    ("Q16SZY", "V5X_S", "P3", False),
    ("OHELLAATP01", "V5X_S", "P3", False),
    ("Q5", "V5X_S", "Z1", False),
    ("Q6", "V5X_S", "Z1", False),
    ("JME05", "V5X_S", "Z1", False),
    ("Q10", "V5X_S", "Z1", False),
)

# Human readable names for entries whose advertised name contains spaces.
_DISPLAY: Mapping[str, str] = {
    "MINIPRINTER": "MINI PRINTER",
    "URBANWORXKIDSCAMERA": "URBANWORX KIDS CAMERA",
    "CYLOBTPRINTER": "CYLO BT PRINTER",
    "XOPOPPY": "XO POPPY",
    "EWTTOET-Z0499": "EWTTO ET-Z0499",
    "EWTTOET-N3689": "EWTTO ET-N3689",
    "EWTTOET-N3687": "EWTTO ET-N3687",
    "PORTABLEPRINTER": "Portable Printer",
    "INSTANTPRINTPLUS": "Instant Print Plus",
}

# Density tables of the vendor app (V5G "F2" raw value, 0..max).
_L = DensityLevels
_V5G_DENSITY: Mapping[str, DensityProfile] = {
    "MX05": DensityProfile(text=_L(100, 130, 150, 200), image=_L(150, 180, 200, 200)),
    "MX06": DensityProfile(text=_L(100, 130, 150, 200), image=_L(150, 180, 200, 200)),
    "MX11": DensityProfile(text=_L(100, 130, 150, 200), image=_L(100, 130, 150, 200)),
    "XOPOPPY": DensityProfile(text=_L(60, 80, 100, 200), image=_L(60, 80, 100, 200)),
    "MX07": DensityProfile(text=_L(70, 90, 110, 200), image=_L(60, 80, 100, 200)),
    "MX08": DensityProfile(text=_L(50, 70, 100, 100), image=_L(60, 90, 110, 110)),
    "MX09": DensityProfile(text=_L(80, 100, 120, 120), image=_L(100, 120, 140, 140)),
    "BQ02": DensityProfile(text=_L(70, 100, 180, 200), image=_L(100, 150, 200, 200)),
}
# Models that share a table with another one in the vendor app.
_V5G_DENSITY_ALIAS: Mapping[str, str] = {
    "MX12": "MX11", "PD01": "MX11", "IM.17": "MX11", "MINISO-M1": "MX11",
    "LP212": "MX11", "MINISO-M12": "MX11", "MX13": "XOPOPPY",
}
# Fallback for V5G models without a table (value used successfully on an MX10).
V5G_DEFAULT_DENSITY = DensityProfile(text=_L(90, 120, 150, 200), image=_L(90, 120, 150, 200))

# V5X intensity (0-100) per head type, as used by the vendor app.
V5X_DENSITY_HIGH_VOLTAGE = DensityProfile(
    text=_L(88, 93, 98, 100), image=_L(88, 93, 98, 100), gray=_L(75, 88, 98, 100)
)
V5X_DENSITY_LOW_VOLTAGE = DensityProfile(
    text=_L(90, 93, 98, 100), image=_L(90, 93, 98, 100), gray=_L(75, 85, 98, 100)
)

_D2_OVERHEAT = {"MX06", "MX08", "MX09"}
_LOW_BATTERY = {"MX09"}


def normalize_name(name: str) -> str:
    """Normalise an advertised name the way the vendor apps do (upper case, no whitespace)."""
    return re.sub(r"\s+", "", name or "").upper()


def _build() -> Dict[str, PrinterModel]:
    models: Dict[str, PrinterModel] = {}
    for name, vendor_model, module, simplified in _RAW:
        family = Family.V5G if vendor_model == "V5G" else Family.V5X
        if family is Family.V5G:
            density = _V5G_DENSITY.get(name) or _V5G_DENSITY.get(_V5G_DENSITY_ALIAS.get(name, ""))
        else:
            density = None  # chosen at runtime from the reported head type
        models[name] = PrinterModel(
            name=name,
            family=family,
            vendor_model=vendor_model,
            kind=_MODULE_KIND.get(module, Kind.MINI_PRINTER),
            simplified=simplified,
            display_name=_DISPLAY.get(name),
            density=density,
            reports_overheat_d2=name in _D2_OVERHEAT,
            reports_low_battery=name in _LOW_BATTERY,
            supports_gray=family is Family.V5X,
        )
    return models


_MODELS: Dict[str, PrinterModel] = _build()


def all_models(family: Optional[Family] = None) -> List[PrinterModel]:
    """Every known model, optionally filtered by protocol family, in catalog order."""
    return [m for m in _MODELS.values() if family is None or m.family is family]


def get_model(name: str) -> Optional[PrinterModel]:
    """Exact (normalised) catalog lookup."""
    return _MODELS.get(normalize_name(name))


def _manufacturer_says_v5x(manufacturer_data: Optional[Mapping[int, bytes]]) -> bool:
    """Some boards advertise a V5G name but speak V5X; the vendor app tells them apart by the
    advertisement payload (10 or 7 bytes ending in 0x59)."""
    if not manufacturer_data:
        return False
    for company_id, payload in manufacturer_data.items():
        for blob in (bytes(payload), company_id.to_bytes(2, "little") + bytes(payload)):
            if len(blob) in (7, 10) and blob[-1] == 0x59:
                return True
    return False


def identify(
    name: Optional[str],
    manufacturer_data: Optional[Mapping[int, bytes]] = None,
) -> Optional[PrinterModel]:
    """Find the model for an advertised Bluetooth name.

    Tries, in order: exact match, the name without hyphens/dots, and the longest catalog name that is
    a prefix of the advertised one (``"MX10-1A2B"`` -> ``MX10``). Returns ``None`` for unknown names.
    """
    if not name:
        return None
    norm = normalize_name(name)
    model = _MODELS.get(norm)
    if model is None:
        loose = re.sub(r"[-_.]", "", norm)
        for key, candidate in _MODELS.items():
            if re.sub(r"[-_.]", "", key) == loose:
                model = candidate
                break
    if model is None:
        best: Optional[PrinterModel] = None
        for key, candidate in _MODELS.items():
            if len(key) >= 3 and norm.startswith(key) and (best is None or len(key) > len(best.name)):
                best = candidate
        model = best
    if model is not None and model.family is Family.V5G and _manufacturer_says_v5x(manufacturer_data):
        model = PrinterModel(
            name=model.name,
            family=Family.V5X,
            vendor_model="V5X_S",
            kind=model.kind,
            simplified=model.simplified,
            display_name=model.display_name,
            supports_gray=True,
        )
    return model


def generic_model(name: str, family: Family) -> PrinterModel:
    """A model description for a device that is not in the catalog but answered a protocol probe."""
    return PrinterModel(
        name=normalize_name(name) or "UNKNOWN",
        family=family,
        vendor_model=family.value,
        display_name=name or None,
        supports_gray=family is Family.V5X,
    )
