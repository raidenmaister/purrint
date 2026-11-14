"""Exception hierarchy. Every error raised on purpose by purrint derives from :class:`PurrintError`."""

from __future__ import annotations


class PurrintError(Exception):
    """Base class for all purrint errors."""


class PrinterNotFoundError(PurrintError):
    """No matching printer was found while scanning."""


class UnsupportedPrinterError(PurrintError):
    """The device is not a known printer and no protocol could be chosen."""


class ConnectionFailedError(PurrintError):
    """Bluetooth connection or GATT discovery failed."""


class NotConnectedError(PurrintError):
    """An operation needs a connected printer."""


class PrinterBusyError(PurrintError):
    """Another job is still running on this printer."""


class PrinterStateError(PurrintError):
    """The printer reported a condition that prevents printing.

    ``status`` holds the :class:`purrint.PrinterStatus` that triggered it.
    """

    def __init__(self, message: str, status: object = None) -> None:
        super().__init__(message)
        self.status = status


class OutOfPaperError(PrinterStateError):
    """The printer reported it has no paper (or the cover is open)."""


class OverheatError(PrinterStateError):
    """The print head reported it is too hot."""


class LowBatteryError(PrinterStateError):
    """The printer battery is too low to print."""


class PrintTimeoutError(PurrintError):
    """The printer did not acknowledge or finish a job in time."""


class PrintCancelledError(PurrintError):
    """The job was cancelled before it finished."""
