"""Protocol drivers: turn prepared rasters into Bluetooth traffic and track the printer state."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Dict, List, Optional

from .catalog import Family
from .exceptions import PrintCancelledError, PrinterStateError, PrintTimeoutError
from .progress import HeadEstimator
from .protocol import v5g, v5x
from .status import DeviceInfo, PrinterStatus
from .transport import Transport

log = logging.getLogger("purrint")

SentCallback = Callable[[float], None]


class Driver:
    """Shared plumbing: notification parsing, reply waiting, paced writes."""

    family: Family

    def __init__(self, transport: Transport) -> None:
        self.t = transport
        self.status = PrinterStatus()
        self.info = DeviceInfo()
        self.temperature_c: Optional[int] = None
        self.estimator = HeadEstimator()
        self._pending = b""
        self._waiters: Dict[str, List[asyncio.Future]] = {}
        self._listeners: List[Callable[[str, object], None]] = []
        self._cancel = False
        transport.set_notify_handler(self._on_bytes)

    # -- notifications --------------------------------------------------------------------------
    def add_listener(self, fn: Callable[[str, object], None]) -> None:
        self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[str, object], None]) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    def _emit(self, kind: str, payload: object) -> None:
        for fn in list(self._listeners):
            try:
                fn(kind, payload)
            except Exception:  # pragma: no cover
                log.exception("listener failed")
        for fut in self._waiters.pop(kind, []):
            if not fut.done():
                fut.set_result(payload)

    def _on_bytes(self, data: bytes) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    async def wait_for(self, kind: str, timeout: float) -> Optional[object]:
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._waiters.setdefault(kind, []).append(fut)
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            lst = self._waiters.get(kind)
            if lst and fut in lst:
                lst.remove(fut)

    async def request(self, frame: bytes, kind: str, timeout: float = 2.0) -> Optional[object]:
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._waiters.setdefault(kind, []).append(fut)
        await self.t.write(frame)
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            lst = self._waiters.get(kind)
            if lst and fut in lst:
                lst.remove(fut)

    def request_cancel(self) -> None:
        self._cancel = True

    async def _paced_write(
        self,
        payload: bytes,
        *,
        channel: str = "cmd",
        chunk: Optional[int] = None,
        delay: Optional[float] = None,
        on_sent: Optional[SentCallback] = None,
        flow_control: bool = False,
        before_last: Optional[Callable[[], None]] = None,
    ) -> None:
        size = chunk or min(self.t.max_write, 128 if channel == "cmd" else 180)
        pause = delay if delay is not None else max(0.004, size * 0.00011)
        total = len(payload) or 1
        for offset in range(0, len(payload), size):
            if self._cancel:
                raise PrintCancelledError("print cancelled")
            if flow_control:
                await self._wait_buffer()
            if before_last is not None and offset + size >= len(payload):
                before_last()
            await self.t.write(payload[offset : offset + size], channel=channel)
            if on_sent is not None:
                on_sent(min(1.0, (offset + size) / total))
            if pause:
                await asyncio.sleep(pause)

    async def _wait_buffer(self) -> None:  # pragma: no cover - V5G overrides
        return

    # -- interface ------------------------------------------------------------------------------
    async def probe(self) -> bool:
        raise NotImplementedError

    async def refresh_status(self) -> PrinterStatus:
        raise NotImplementedError

    async def query_info(self) -> DeviceInfo:
        raise NotImplementedError


# ------------------------------------------------------------------------------------------ V5G --
class V5GDriver(Driver):
    family = Family.V5G

    def __init__(self, transport: Transport) -> None:
        super().__init__(transport)
        self._buffer_free = asyncio.Event()
        self._buffer_free.set()
        self._job_sent = False
        self._job_had_full = False
        self._job_started = 0.0
        self._job_done: Optional[asyncio.Future] = None
        self.challenge_seen = False

    def _on_bytes(self, data: bytes) -> None:
        notices, self._pending = v5g.decode_stream(data, self._pending)
        for n in notices:
            log.debug("<< V5G %s %s", n.kind, n.frame.payload.hex())
            if n.kind == v5g.KIND_STATUS and n.status is not None:
                self.status = n.status.merged(temperature_c=self.temperature_c)
                self._emit("status", self.status)
            elif n.kind == v5g.KIND_BUFFER_FULL:
                self._buffer_free.clear()
                self._job_had_full = True
                self._emit("buffer_full", None)
            elif n.kind == v5g.KIND_BUFFER_FREE:
                self._buffer_free.set()
                self._emit("buffer_free", None)
                if self._job_sent and self._job_done is not None and not self._job_done.done():
                    # After a "buffer full" the printer also says "free" while it still prints the
                    # rest; only accept it as the end once most of the expected time has passed.
                    elapsed = time.monotonic() - self._job_started
                    if not self._job_had_full or elapsed >= 0.75 * self.estimator.expected_duration():
                        self._job_done.set_result(True)
            elif n.kind == v5g.KIND_TEMPERATURE:
                self.temperature_c = n.temperature_c
                self.status = self.status.merged(temperature_c=n.temperature_c)
                self._emit("temperature", n.temperature_c)
            elif n.kind == v5g.KIND_FIRMWARE:
                self.info = DeviceInfo(firmware=n.text, serial=self.info.serial, head_type=self.info.head_type)
                self._emit("firmware", n.text)
            elif n.kind == v5g.KIND_SERIAL:
                self.info = DeviceInfo(firmware=self.info.firmware, serial=n.text, head_type=self.info.head_type)
                self._emit("serial", n.text)
            elif n.kind == v5g.KIND_OVERHEAT:
                self.status = self.status.merged(overheated=True)
                self._emit("status", self.status)
            elif n.kind == v5g.KIND_CHALLENGE:
                self.challenge_seen = True
                log.warning("printer sent an authentication challenge (D6); purrint does not answer it")
                self._emit("challenge", n.frame.payload)
            else:
                self._emit("other", n.frame)

    async def _wait_buffer(self) -> None:
        if not self._buffer_free.is_set():
            try:
                await asyncio.wait_for(self._buffer_free.wait(), 10.0)
            except asyncio.TimeoutError:
                log.debug("buffer-free notification missing, continuing")
                self._buffer_free.set()

    async def probe(self) -> bool:
        return await self.request(v5g.get_device_info(), "firmware", 1.5) is not None or \
            await self.request(v5g.get_state(), "status", 1.0) is not None

    async def refresh_status(self) -> PrinterStatus:
        await self.request(v5g.get_state(), "status", 2.0)
        return self.status

    async def query_info(self) -> DeviceInfo:
        await self.request(v5g.get_device_info(), "firmware", 2.0)
        await self.request(v5g.get_serial(), "serial", 2.0)
        return self.info

    async def send_job(
        self, rows: List[bytes], settings: v5g.JobSettings, on_sent: Optional[SentCallback], wait: bool
    ) -> bool:
        """Send one job; returns True when the printer confirmed completion."""
        self._cancel = False
        payload = v5g.build_job(rows, settings)
        loop = asyncio.get_running_loop()
        self._job_done = loop.create_future()
        self._job_sent = False
        self._job_had_full = False
        self._job_started = time.monotonic()
        self._buffer_free.set()
        self.estimator.begin(len(rows))

        def sent(f: float) -> None:
            self.estimator.report_sent(f)
            if on_sent:
                on_sent(f)

        def last_chunk() -> None:
            self._job_sent = True  # the completion notice may arrive as soon as this chunk lands

        try:
            await self._paced_write(payload, on_sent=sent, flow_control=True, before_last=last_chunk)
        except PrintCancelledError:
            self._job_sent = False
            await self.t.write(v5g.build_cancel())
            raise
        self._job_sent = True
        if not wait:
            return False
        timeout = self.estimator.expected_duration() * 1.8 + 6
        try:
            await asyncio.wait_for(asyncio.shield(self._job_done), timeout)
            confirmed = True
        except asyncio.TimeoutError:
            confirmed = False
            log.info("no completion notification; assuming the job finished")
        self.estimator.finish(confirmed)
        return confirmed

    async def feed(self, lines: int) -> None:
        await self.t.write(v5g.build_feed_job(lines))

    async def retract(self, lines: int) -> None:
        await self.t.write(v5g.retract(lines))

    async def cancel(self) -> None:
        self.request_cancel()
        await self.t.write(v5g.build_cancel())


# ------------------------------------------------------------------------------------------ V5X --
class V5XDriver(Driver):
    family = Family.V5X

    def _on_bytes(self, data: bytes) -> None:
        notices, self._pending = v5x.decode_stream(data, self._pending)
        for n in notices:
            log.debug("<< V5X %s %s", n.kind, n.frame.payload.hex())
            if n.kind == v5x.KIND_STATUS and n.status is not None:
                self.status = n.status
                if n.status.temperature_c is not None:
                    self.temperature_c = n.status.temperature_c
                self._emit("status", self.status)
            elif n.kind == v5x.KIND_PRINT_ACK:
                self._emit("print_ack", n)
            elif n.kind == v5x.KIND_PRINT_DONE:
                self._emit("print_done", n)
            elif n.kind == v5x.KIND_VERSION:
                head = v5x.head_type_from_version(n.text) or self.info.head_type
                self.info = DeviceInfo(firmware=n.text, serial=self.info.serial, head_type=head)
                self._emit("firmware", n.text)
            elif n.kind == v5x.KIND_HEAD_TYPE:
                self.info = DeviceInfo(firmware=self.info.firmware, serial=self.info.serial, head_type=n.text)
                self._emit("head_type", n.text)
            elif n.kind == v5x.KIND_BATTERY:
                self.status = self.status.merged(battery_percent=n.value)
                self._emit("battery", n.value)
            elif n.kind == v5x.KIND_COUNT:
                self.info = DeviceInfo(firmware=self.info.firmware, serial=n.text, head_type=self.info.head_type)
                self._emit("serial", n.text)
            elif n.kind == v5x.KIND_CHALLENGE:
                log.warning("printer sent an authentication challenge (B3); purrint does not answer it")
                self._emit("challenge", n.frame.payload)
            else:
                self._emit("other", n.frame)

    async def probe(self) -> bool:
        return await self.request(v5x.get_version(), "firmware", 1.5) is not None or \
            await self.request(v5x.get_status(), "status", 1.0) is not None

    async def refresh_status(self) -> PrinterStatus:
        await self.request(v5x.get_status(), "status", 2.0)
        return self.status

    async def query_info(self) -> DeviceInfo:
        await self.request(v5x.get_version(), "firmware", 2.0)
        await self.request(v5x.get_head_type(), "head_type", 1.5)
        await self.request(v5x.query_count(), "serial", 1.5)
        return self.info

    async def send_job(
        self,
        rows: List[bytes],
        width: int,
        intensity: int,
        gray: bool,
        mode: Optional[int],
        on_sent: Optional[SentCallback],
        wait: bool,
    ) -> bool:
        self._cancel = False
        lines = v5x.padded_line_count(len(rows))
        bitmap = v5x.bitmap_payload(rows, width, gray)
        await self.t.write(v5x.set_intensity(intensity))
        await asyncio.sleep(0.05)
        self.estimator.begin(lines)
        ack = await self.request(v5x.print_request(lines, mode if mode is not None else (v5x.MODE_GRAY if gray else v5x.MODE_DOT)), "print_ack", 5.0)
        if ack is None:
            log.info("no A9 acknowledgement, sending data anyway")
        elif not ack.ok:  # type: ignore[union-attr]
            await self.refresh_status()
            raise PrinterStateError(f"printer refused the job (code 0x{ack.code:02X})", self.status)  # type: ignore[union-attr]

        def sent(f: float) -> None:
            self.estimator.report_sent(f)
            if on_sent:
                on_sent(f)

        try:
            await self._paced_write(bitmap, channel="data", on_sent=sent)
        except PrintCancelledError:
            await self.t.write(v5x.cancel())
            raise
        if not wait:
            await self.t.write(v5x.flush())
            return False
        # Register for AA before flushing so a fast printer cannot beat us to it
        done = await self.request(v5x.flush(), "print_done", self.estimator.expected_duration() * 2.0 + 10)
        self.estimator.finish(done is not None)
        if done is None:
            log.info("no AA completion notification; assuming the job finished")
        return done is not None

    async def feed(self, lines: int) -> None:
        await self.t.write(v5x.feed(lines))

    async def retract(self, lines: int) -> None:
        raise NotImplementedError("V5X printers have no retract command")

    async def cancel(self) -> None:
        self.request_cancel()
        await self.t.write(v5x.cancel())


def make_driver(family: Family, transport: Transport) -> Driver:
    return V5GDriver(transport) if family is Family.V5G else V5XDriver(transport)

