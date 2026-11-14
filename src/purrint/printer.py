"""High level asynchronous API."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence, Union

from PIL import Image

from . import imaging
from .catalog import (
    V5G_DEFAULT_DENSITY,
    V5X_DENSITY_HIGH_VOLTAGE,
    V5X_DENSITY_LOW_VOLTAGE,
    DensityLevels,
    Family,
    PrinterModel,
    generic_model,
    get_model,
)
from .drivers import Driver, V5GDriver, V5XDriver, make_driver
from .exceptions import (
    NotConnectedError,
    OutOfPaperError,
    OverheatError,
    UnsupportedPrinterError,
)
from .imaging import ImageOptions, ImageSource
from .progress import PrintProgress, ProgressCallback
from .protocol import v5g, v5x
from .status import DeviceInfo, PrinterStatus
from .text import FontLike, render_qr, render_separator, render_text
from .transport import BleTransport, FoundPrinter, Transport, find_printer

log = logging.getLogger("purrint")

EventCallback = Callable[[str, object], None]

DENSITY_LEVELS = 7
DEFAULT_DENSITY = 4


@dataclass(frozen=True)
class PrintResult:
    lines: int
    copies: int
    confirmed: bool
    """The printer itself reported that the paper finished printing."""

    seconds: float
    status: PrinterStatus


class Printer:
    """A connected printer. Create it with :func:`purrint.connect` (or ``await Printer.connect(...)``).

    Use it as an async context manager to disconnect automatically::

        async with await purrint.connect("MX10") as printer:
            await printer.print_image("photo.jpg")
    """

    def __init__(self, transport: Transport, model: PrinterModel, driver: Driver) -> None:
        self._t = transport
        self.model = model
        self._driver = driver
        self._lock = asyncio.Lock()

    # ---------------------------------------------------------------------------- lifecycle ----
    @classmethod
    async def connect(
        cls,
        target: Union[str, FoundPrinter, None] = None,
        *,
        timeout: float = 12.0,
        model: Optional[str] = None,
        family: Union[Family, str, None] = None,
    ) -> "Printer":
        """Find and connect to a printer.

        ``target`` is a name fragment (``"MX10"``), a Bluetooth address, a :class:`FoundPrinter` from
        :func:`purrint.scan`, or ``None`` for the strongest supported printer in range.
        ``model`` / ``family`` force the protocol for devices that are missing from the catalog.
        """
        found = target if isinstance(target, FoundPrinter) else await find_printer(target, timeout)
        chosen: Optional[PrinterModel] = None
        if model:
            chosen = get_model(model)
            if chosen is None:
                raise UnsupportedPrinterError(f"unknown model {model!r}")
        elif family:
            chosen = generic_model(found.name, Family(str(family).upper() if not isinstance(family, Family) else family))
        else:
            chosen = found.model

        transport = BleTransport(found)
        await transport.connect()
        try:
            return await cls._from_transport(transport, chosen, found.name)
        except BaseException:
            await transport.close()
            raise

    @classmethod
    async def _from_transport(
        cls, transport: Transport, model: Optional[PrinterModel], name: str = ""
    ) -> "Printer":
        if model is None:
            await transport.start(None)
            for fam in (Family.V5G, Family.V5X):
                driver = make_driver(fam, transport)
                if await driver.probe():
                    model = generic_model(name or transport.name, fam)
                    log.info("unknown printer %s answered the %s protocol", name, fam.value)
                    break
            else:
                raise UnsupportedPrinterError(
                    f"{name or transport.address} did not answer any supported printer protocol"
                )
            await transport.start(model.family)
            driver = make_driver(model.family, transport)
        else:
            await transport.start(model.family)
            driver = make_driver(model.family, transport)
        printer = cls(transport, model, driver)
        await printer._initialise()
        return printer

    async def _initialise(self) -> None:
        await asyncio.sleep(0.2)
        try:
            await self._driver.query_info()
            await self._driver.refresh_status()
        except Exception as exc:  # pragma: no cover - informative only
            log.debug("initial queries failed: %s", exc)

    async def disconnect(self) -> None:
        await self._t.close()

    async def __aenter__(self) -> "Printer":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.disconnect()

    # --------------------------------------------------------------------------- properties ----
    @property
    def name(self) -> str:
        return self._t.name or self.model.label

    @property
    def address(self) -> str:
        return self._t.address

    @property
    def family(self) -> Family:
        return self.model.family

    @property
    def width(self) -> int:
        """Printable width in dots."""
        return self.model.dots_per_line

    @property
    def is_connected(self) -> bool:
        return self._t.is_connected

    @property
    def status(self) -> PrinterStatus:
        """Last status reported by the printer (see :meth:`refresh_status`)."""
        return self._driver.status

    @property
    def info(self) -> DeviceInfo:
        return self._driver.info

    @property
    def temperature(self) -> Optional[int]:
        """Last reported print head temperature in °C, if the model reports it."""
        return self._driver.temperature_c

    @property
    def mtu(self) -> int:
        return self._t.mtu

    def on(self, callback: EventCallback) -> Callable[[], None]:
        """Register ``callback(kind, payload)`` for printer notifications
        (``status``, ``temperature``, ``buffer_full``, ``buffer_free``, ``firmware``, ``print_done``…).
        Returns a function that unregisters it."""
        self._driver.add_listener(callback)
        return lambda: self._driver.remove_listener(callback)

    def __repr__(self) -> str:
        return f"<Printer {self.name} {self.family.value} {self.address}>"

    # ------------------------------------------------------------------------------ queries ----
    async def refresh_status(self) -> PrinterStatus:
        self._require()
        return await self._driver.refresh_status()

    async def get_info(self) -> DeviceInfo:
        self._require()
        return await self._driver.query_info()

    # ------------------------------------------------------------------------------ printing ----
    def render(
        self,
        source: ImageSource,
        *,
        gray: bool = False,
        **image_options: object,
    ) -> Image.Image:
        """Prepare an image exactly as :meth:`print_image` would, without printing it."""
        return imaging.prepare(source, self.width, ImageOptions(**image_options), gray=gray and self.model.supports_gray)  # type: ignore[arg-type]

    async def print_image(
        self,
        source: ImageSource,
        *,
        density: int = DEFAULT_DENSITY,
        dither: str = "floyd",
        rotate: Union[str, int] = "auto",
        brightness: int = 0,
        contrast: int = 0,
        gamma: float = 1.0,
        sharpen: bool = False,
        invert: bool = False,
        threshold: int = 128,
        autocontrast: bool = False,
        max_height: Optional[int] = None,
        gray: bool = False,
        copies: int = 1,
        cooldown: float = 0.0,
        feed: Optional[int] = None,
        energy: Optional[int] = None,
        intensity: Optional[int] = None,
        speed: Optional[int] = None,
        quality: Optional[int] = None,
        wait: bool = True,
        on_progress: Optional[ProgressCallback] = None,
    ) -> PrintResult:
        """Print a picture (path, bytes, file object or PIL image).

        * ``density`` 1 (light) .. 7 (darkest). ``energy`` (V5G) / ``intensity`` (V5X) override it.
        * ``gray=True`` uses 16-level grayscale on printers that support it (V5X family).
        * ``rotate="auto"`` turns landscape pictures 90° to use the length of the paper.
        * ``copies`` with ``cooldown`` seconds of rest for the head between copies.
        * ``wait=False`` returns as soon as the data is sent instead of when the paper is out.
        """
        opts = ImageOptions(
            rotate=rotate, dither=dither, brightness=brightness, contrast=contrast, gamma=gamma,
            sharpen=sharpen, invert=invert, threshold=threshold, autocontrast=autocontrast, max_height=max_height,
        )
        use_gray = bool(gray and self.model.supports_gray)
        img = imaging.prepare(source, self.width, opts, gray=use_gray)
        return await self.print_raster(
            img, density=density, content="gray" if use_gray else "image", copies=copies, cooldown=cooldown,
            feed=feed, energy=energy, intensity=intensity, speed=speed, quality=quality, wait=wait,
            on_progress=on_progress,
        )

    async def print_text(
        self,
        text: str,
        *,
        size: int = 26,
        font: FontLike = None,
        bold: bool = False,
        mono: bool = False,
        align: str = "left",
        line_spacing: float = 1.2,
        underline: bool = False,
        invert: bool = False,
        density: int = DEFAULT_DENSITY,
        copies: int = 1,
        feed: Optional[int] = None,
        energy: Optional[int] = None,
        intensity: Optional[int] = None,
        wait: bool = True,
        on_progress: Optional[ProgressCallback] = None,
    ) -> PrintResult:
        """Print text. Lines wrap automatically; use ``\\n`` for explicit breaks."""
        img = render_text(
            text, self.width, font=font, size=size, bold=bold, mono=mono, align=align,
            line_spacing=line_spacing, underline=underline, invert=invert,
        )
        return await self.print_raster(
            img, density=density, content="text", copies=copies, feed=feed, energy=energy,
            intensity=intensity, wait=wait, on_progress=on_progress,
        )

    async def print_qr(
        self,
        data: str,
        *,
        size: Optional[int] = None,
        caption: Optional[str] = None,
        error_correction: str = "M",
        density: int = DEFAULT_DENSITY,
        feed: Optional[int] = None,
        wait: bool = True,
        on_progress: Optional[ProgressCallback] = None,
    ) -> PrintResult:
        """Print a QR code (needs ``pip install purrint[qr]``)."""
        img = render_qr(data, self.width, size=size, caption=caption, error_correction=error_correction)
        return await self.print_raster(img, density=density, content="text", feed=feed, wait=wait, on_progress=on_progress)

    async def print_separator(self, style: str = "dashed", *, feed: Optional[int] = 0) -> PrintResult:
        return await self.print_raster(render_separator(self.width, style=style), content="text", feed=feed)

    async def print_many(
        self,
        sources: Iterable[ImageSource],
        *,
        cooldown: float = 3.0,
        on_item: Optional[Callable[[int, ImageSource, PrintResult], None]] = None,
        **print_image_options: object,
    ) -> List[PrintResult]:
        """Print several pictures one after another, resting ``cooldown`` seconds between them."""
        results: List[PrintResult] = []
        items = list(sources)
        for i, src in enumerate(items):
            result = await self.print_image(src, **print_image_options)  # type: ignore[arg-type]
            results.append(result)
            if on_item:
                on_item(i, src, result)
            if cooldown and i < len(items) - 1:
                await asyncio.sleep(cooldown)
        return results

    async def print_raster(
        self,
        image: Image.Image,
        *,
        density: int = DEFAULT_DENSITY,
        content: str = "image",
        copies: int = 1,
        cooldown: float = 0.0,
        feed: Optional[int] = None,
        energy: Optional[int] = None,
        intensity: Optional[int] = None,
        speed: Optional[int] = None,
        quality: Optional[int] = None,
        wait: bool = True,
        on_progress: Optional[ProgressCallback] = None,
        check_status: bool = True,
    ) -> PrintResult:
        """Print an already prepared image (mode ``"1"``, or 16-level ``"L"`` for grayscale).

        Images narrower than the head are centred; wider ones are scaled down.
        """
        self._require()
        image = self._fit(image)
        gray = image.mode == "L" and self.model.supports_gray
        content = "gray" if gray else ("text" if content == "text" else "image")
        rows = imaging.pack_4bpp(image, self.width) if gray else imaging.pack_1bpp(image, self.width)
        copies = max(1, int(copies))
        start = time.monotonic()
        confirmed_all = True

        async with self._lock:
            if check_status:
                await self._check_ready()
            for copy in range(1, copies + 1):
                ticker = self._start_ticker(on_progress, len(rows), copy, copies)
                try:
                    confirmed = await self._send(rows, density, content, gray, feed, energy, intensity, speed, quality, wait, ticker)
                finally:
                    ticker.stop()
                confirmed_all = confirmed_all and confirmed
                if on_progress:
                    on_progress(PrintProgress("done", len(rows), 1.0, 1.0, copy, copies))
                if copy < copies and cooldown:
                    await asyncio.sleep(cooldown)
            if wait:
                try:
                    await self._driver.refresh_status()
                except Exception:  # pragma: no cover
                    pass
        return PrintResult(len(rows), copies, confirmed_all, time.monotonic() - start, self.status)

    # ----------------------------------------------------------------------- paper movement ----
    async def feed(self, lines: int = 64) -> None:
        """Advance the paper ``lines`` dot rows (8 rows ≈ 1 mm)."""
        self._require()
        async with self._lock:
            await self._driver.feed(int(lines))  # type: ignore[attr-defined]

    async def feed_mm(self, millimetres: float) -> None:
        await self.feed(int(round(millimetres * self.model.dpi / 25.4)))

    async def retract(self, lines: int = 64) -> None:
        """Pull the paper back (V5G firmwares that support it)."""
        self._require()
        async with self._lock:
            await self._driver.retract(int(lines))  # type: ignore[attr-defined]

    async def cancel(self) -> None:
        """Stop the job being sent and tell the printer to abort."""
        self._require()
        await self._driver.cancel()  # type: ignore[attr-defined]

    # ----------------------------------------------------------------------------- internals ----
    def _require(self) -> None:
        if not self._t.is_connected:
            raise NotConnectedError("the printer is not connected")

    def _fit(self, image: Image.Image) -> Image.Image:
        if image.mode not in ("1", "L"):
            image = image.convert("L")
        if image.width == self.width:
            return image
        if image.width > self.width:
            return imaging.fit_width(image.convert("L"), self.width).convert(image.mode)
        canvas = Image.new(image.mode, (self.width, image.height), 255)
        canvas.paste(image, ((self.width - image.width) // 2, 0))
        return canvas

    async def _check_ready(self, overheat_wait: float = 45.0) -> None:
        status = await self._driver.refresh_status()
        if status.out_of_paper or status.cover_open:
            raise OutOfPaperError("the printer reports no paper or an open cover", status)
        deadline = time.monotonic() + overheat_wait
        while status.overheated:
            if time.monotonic() > deadline:
                raise OverheatError("the print head is too hot; let it cool down", status)
            log.warning("print head overheated, waiting for it to cool down")
            await asyncio.sleep(3.0)
            status = await self._driver.refresh_status()
        if status.low_battery:
            log.warning("printer battery is low")

    def _density_levels(self, content: str) -> DensityLevels:
        if self.family is Family.V5G:
            profile = self.model.density or V5G_DEFAULT_DENSITY
        else:
            head = self.info.head_type
            profile = V5X_DENSITY_LOW_VOLTAGE if head == "low_voltage" else V5X_DENSITY_HIGH_VOLTAGE
        if content == "gray" and profile.gray is not None:
            return profile.gray
        return profile.text if content == "text" else profile.image

    async def _send(
        self, rows, density, content, gray, feed, energy, intensity, speed, quality, wait, ticker
    ) -> bool:
        level = max(1, min(DENSITY_LEVELS, int(density)))
        if isinstance(self._driver, V5GDriver):
            settings = v5g.JobSettings(
                energy=int(energy) if energy else v5g.energy_for_level(level),
                density_value=self._density_levels(content).at(level, DENSITY_LEVELS),
                quality=int(quality) if quality else v5g.DEFAULT_QUALITY,
                speed=int(speed) if speed else v5g.DEFAULT_SPEED,
                feed_lines=v5g.DEFAULT_FEED_LINES if feed is None else max(0, int(feed)),
            )
            return await self._driver.send_job(rows, settings, ticker.sent, wait)
        assert isinstance(self._driver, V5XDriver)
        value = int(intensity) if intensity is not None else self._density_levels(content).at(level, DENSITY_LEVELS)
        confirmed = await self._driver.send_job(rows, self.width, value, gray, None, ticker.sent, wait)
        if feed:
            await self._driver.feed(int(feed))
        return confirmed

    def _start_ticker(self, cb: Optional[ProgressCallback], lines: int, copy: int, copies: int) -> "_Ticker":
        return _Ticker(self._driver, cb, lines, copy, copies)


class _Ticker:
    """Calls the progress callback ~20 times per second while a job runs."""

    def __init__(self, driver: Driver, cb: Optional[ProgressCallback], lines: int, copy: int, copies: int) -> None:
        self._driver = driver
        self._cb = cb
        self._lines = lines
        self._copy = copy
        self._copies = copies
        self._sent = 0.0
        self._task: Optional[asyncio.Task] = None
        if cb is not None:
            self._task = asyncio.ensure_future(self._run())

    def sent(self, fraction: float) -> None:
        self._sent = fraction

    async def _run(self) -> None:
        try:
            while True:
                printed = self._driver.estimator.printed_fraction()
                phase = "sending" if self._sent < 1.0 else ("printing" if printed < 1.0 else "feeding")
                self._cb(PrintProgress(phase, self._lines, self._sent, printed, self._copy, self._copies))  # type: ignore[misc]
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()


async def connect(
    target: Union[str, FoundPrinter, None] = None,
    *,
    timeout: float = 12.0,
    model: Optional[str] = None,
    family: Union[Family, str, None] = None,
) -> Printer:
    """Connect to a printer. See :meth:`Printer.connect`."""
    return await Printer.connect(target, timeout=timeout, model=model, family=family)
