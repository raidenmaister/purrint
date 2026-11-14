"""Blocking API for scripts that do not use asyncio.

    import purrint
    with purrint.connect_sync("MX10") as printer:
        printer.print_image("photo.jpg")
        printer.print_text("Hello!", size=40, align="center")

Bluetooth work runs on a private event loop in a background thread.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Coroutine, List, Optional, TypeVar, Union

from .catalog import Family
from .printer import Printer, PrintResult
from .status import DeviceInfo, PrinterStatus
from .transport import FoundPrinter, discover

T = TypeVar("T")


class _Loop:
    _lock = threading.Lock()
    _instance: Optional["_Loop"] = None

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, name="purrint-loop", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    @classmethod
    def get(cls) -> "_Loop":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def run(self, coro: Coroutine[Any, Any, T], timeout: Optional[float] = None) -> T:
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)


def _run(coro: Coroutine[Any, Any, T]) -> T:
    return _Loop.get().run(coro)


class SyncPrinter:
    """Blocking wrapper around :class:`purrint.Printer`. Every method mirrors the async one."""

    def __init__(self, printer: Printer) -> None:
        self._p = printer

    @property
    def printer(self) -> Printer:
        """The underlying asynchronous printer."""
        return self._p

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._p, name)
        if asyncio.iscoroutinefunction(attr):
            def call(*args: Any, **kwargs: Any) -> Any:
                return _run(attr(*args, **kwargs))

            call.__name__ = name
            call.__doc__ = attr.__doc__
            return call
        return attr

    # Explicit signatures for the most used calls (better IDE help)
    def print_image(self, source: Any, **options: Any) -> PrintResult:
        return _run(self._p.print_image(source, **options))

    def print_text(self, text: str, **options: Any) -> PrintResult:
        return _run(self._p.print_text(text, **options))

    def print_qr(self, data: str, **options: Any) -> PrintResult:
        return _run(self._p.print_qr(data, **options))

    def feed(self, lines: int = 64) -> None:
        _run(self._p.feed(lines))

    def refresh_status(self) -> PrinterStatus:
        return _run(self._p.refresh_status())

    def get_info(self) -> DeviceInfo:
        return _run(self._p.get_info())

    def disconnect(self) -> None:
        _run(self._p.disconnect())

    def __enter__(self) -> "SyncPrinter":
        return self

    def __exit__(self, *exc: object) -> None:
        self.disconnect()

    def __repr__(self) -> str:
        return f"<SyncPrinter {self._p!r}>"


def connect_sync(
    target: Union[str, FoundPrinter, None] = None,
    *,
    timeout: float = 12.0,
    model: Optional[str] = None,
    family: Union[Family, str, None] = None,
) -> SyncPrinter:
    """Blocking version of :func:`purrint.connect`."""
    return SyncPrinter(_run(Printer.connect(target, timeout=timeout, model=model, family=family)))


def scan_sync(timeout: float = 6.0, *, known_only: bool = True, name: Optional[str] = None) -> List[FoundPrinter]:
    """Blocking version of :func:`purrint.scan`."""
    return _run(discover(timeout, known_only=known_only, name=name))


def quick_print(source: Any, printer: Optional[str] = None, **options: Any) -> PrintResult:
    """Connect, print one picture (or text with ``text=...``) and disconnect.

        purrint.quick_print("photo.jpg")
        purrint.quick_print(None, text="Shopping list:\\n- milk")
    """

    async def job() -> PrintResult:
        async with await Printer.connect(printer) as p:
            text = options.pop("text", None)
            if text is not None:
                return await p.print_text(text, **options)
            return await p.print_image(source, **options)

    return _run(job())


def run(coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Run an async purrint workflow from synchronous code on the shared loop."""
    return _run(coro_factory())
