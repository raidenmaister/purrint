"""purrint – print on cheap Bluetooth thermal printers from Python.

Quick start (async)::

    import asyncio, purrint

    async def main():
        async with await purrint.connect("MX10") as printer:      # or connect() for the nearest one
            await printer.print_image("photo.jpg")
            await printer.print_text("Hello from Python!", size=36, align="center")

    asyncio.run(main())

Quick start (blocking)::

    import purrint
    with purrint.connect_sync() as printer:
        printer.print_text("Hello!")
"""

from ._version import __version__
from .catalog import Family, Kind, PrinterModel, all_models, get_model, identify, normalize_name
from .exceptions import (
    ConnectionFailedError,
    LowBatteryError,
    NotConnectedError,
    OutOfPaperError,
    OverheatError,
    PrintCancelledError,
    PrinterBusyError,
    PrinterNotFoundError,
    PrinterStateError,
    PrintTimeoutError,
    PurrintError,
    UnsupportedPrinterError,
)
from .imaging import DITHER_METHODS, ImageOptions, load_image, prepare, preview, stack
from .printer import Printer, PrintResult, connect
from .progress import PrintProgress
from .simulator import SimulatedTransport, connect_simulated
from .status import DeviceInfo, PrinterState, PrinterStatus
from .sync import SyncPrinter, connect_sync, quick_print, scan_sync
from .text import render_qr, render_separator, render_text
from .transport import FoundPrinter, discover, find_printer

scan = discover
"""Alias of :func:`purrint.discover`: ``await purrint.scan()``."""

__all__ = [
    "__version__",
    # connecting
    "connect", "connect_sync", "connect_simulated", "scan", "discover", "scan_sync", "find_printer",
    "quick_print", "Printer", "SyncPrinter", "FoundPrinter", "SimulatedTransport",
    # results / status
    "PrintResult", "PrintProgress", "PrinterStatus", "PrinterState", "DeviceInfo",
    # catalog
    "Family", "Kind", "PrinterModel", "all_models", "get_model", "identify", "normalize_name",
    # imaging
    "ImageOptions", "DITHER_METHODS", "load_image", "prepare", "preview", "stack",
    "render_text", "render_qr", "render_separator",
    # errors
    "PurrintError", "PrinterNotFoundError", "UnsupportedPrinterError", "ConnectionFailedError",
    "NotConnectedError", "PrinterBusyError", "PrinterStateError", "OutOfPaperError", "OverheatError",
    "LowBatteryError", "PrintTimeoutError", "PrintCancelledError",
]
