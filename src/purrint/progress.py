"""Progress reporting.

Printers do not report which line they are printing; they only say when a job is finished. purrint
estimates the head position from the measured print speed, never lets the estimate run ahead of the
data already sent, snaps to the end when the printer confirms, and re-calibrates the speed after every
confirmed job.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class PrintProgress:
    phase: str
    """``"sending"``, ``"printing"``, ``"feeding"`` or ``"done"``."""

    lines: int
    sent: float
    """Fraction (0..1) of the job handed to Bluetooth."""

    printed: float
    """Estimated fraction (0..1) of the image already on paper."""

    copy: int = 1
    copies: int = 1

    @property
    def current_line(self) -> int:
        return int(round(self.printed * self.lines))


ProgressCallback = Callable[[PrintProgress], None]


class HeadEstimator:
    """Estimate the print head position for one job."""

    #: Default seconds per dot row, measured on an MX10 (energy 12000, speed 10).
    DEFAULT_SECONDS_PER_LINE = 0.024
    START_LATENCY = 0.6
    TAIL_SECONDS = 2.6

    def __init__(self, seconds_per_line: Optional[float] = None) -> None:
        self.seconds_per_line = seconds_per_line or self.DEFAULT_SECONDS_PER_LINE
        self.lines = 1
        self._t0 = time.monotonic()
        self._sent = 0.0
        self._finished = False
        self._shown = 0.0

    def begin(self, lines: int) -> None:
        self.lines = max(1, lines)
        self._t0 = time.monotonic()
        self._sent = 0.0
        self._finished = False
        self._shown = 0.0

    def expected_duration(self) -> float:
        return self.START_LATENCY + self.lines * self.seconds_per_line + self.TAIL_SECONDS

    def report_sent(self, fraction: float) -> None:
        self._sent = max(0.0, min(1.0, fraction))

    def finish(self, confirmed: bool) -> None:
        if self._finished:
            return
        self._finished = True
        if confirmed and self.lines >= 60:
            measured = time.monotonic() - self._t0
            spl = (measured - self.START_LATENCY - self.TAIL_SECONDS) / self.lines
            if 0.008 < spl < 0.12:
                self.seconds_per_line = self.seconds_per_line * 0.5 + spl * 0.5

    def printed_fraction(self) -> float:
        if self._finished:
            self._shown = 1.0
            return 1.0
        t = time.monotonic() - self._t0
        by_time = (t - self.START_LATENCY) / self.seconds_per_line
        by_data = self._sent * self.lines - 4
        target = max(0.0, min(1.0, min(by_time, by_data) / self.lines))
        self._shown = max(self._shown, target)
        return self._shown
