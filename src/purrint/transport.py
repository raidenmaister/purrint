"""Bluetooth Low Energy transport built on `bleak <https://github.com/hbldh/bleak>`_.

The printers expose one of a few GATT layouts. purrint picks the right characteristics for:

* ``0000ae30`` service: ``ae01`` commands (write w/o response), ``ae02`` notifications,
  ``ae03`` bulk data (V5X family only). Some macOS stacks show it as ``af30``/``af01``…
* ``0000ff00`` service: ``ff02`` write, ``ff03`` notifications (older V5G boards).
* ``0000200a`` service: ``202a`` write, ``204a`` notifications ("R5" boards).

Anything else falls back to the first writable characteristic and the first notifying one.
"""

from __future__ import annotations

import abc
import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Mapping, Optional, Tuple

from .catalog import Family, PrinterModel, identify
from .exceptions import ConnectionFailedError, PrinterNotFoundError

log = logging.getLogger("purrint")

NotifyHandler = Callable[[bytes], None]

_ADDRESS_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$|^[0-9A-Fa-f-]{36}$")


def _uuid(short: str) -> str:
    return f"0000{short}-0000-1000-8000-00805f9b34fb"


# (service, command/write, notify, data)
_LAYOUTS: Tuple[Tuple[str, str, str, Optional[str]], ...] = (
    (_uuid("ae30"), _uuid("ae01"), _uuid("ae02"), _uuid("ae03")),
    (_uuid("af30"), _uuid("af01"), _uuid("af02"), _uuid("af03")),
    (_uuid("ff00"), _uuid("ff02"), _uuid("ff03"), None),
    (_uuid("200a"), _uuid("202a"), _uuid("204a"), None),
)


def looks_like_address(value: str) -> bool:
    """True for ``AA:BB:CC:DD:EE:FF`` MAC addresses and macOS CoreBluetooth UUIDs."""
    return bool(_ADDRESS_RE.match(value.strip()))


class Transport(abc.ABC):
    """Byte pipe to a printer. Implementations: :class:`BleTransport`, :class:`purrint.simulator.SimulatedTransport`."""

    name: str = ""
    address: str = ""
    mtu: int = 23

    @property
    def max_write(self) -> int:
        """Largest payload for one write without response."""
        return max(20, min(self.mtu - 3, 244))

    @abc.abstractmethod
    async def write(self, data: bytes, *, channel: str = "cmd") -> None:
        """Send bytes. ``channel`` is ``"cmd"`` or ``"data"`` (V5X bulk image data)."""

    @abc.abstractmethod
    def set_notify_handler(self, handler: Optional[NotifyHandler]) -> None: ...

    @abc.abstractmethod
    async def start(self, family: Optional[Family]) -> None:
        """Subscribe to notifications and choose characteristics for ``family``."""

    @abc.abstractmethod
    async def close(self) -> None: ...

    @property
    @abc.abstractmethod
    def is_connected(self) -> bool: ...


# ------------------------------------------------------------------------------------ scanning ----
@dataclass(frozen=True)
class FoundPrinter:
    """A device seen while scanning."""

    name: str
    address: str
    rssi: Optional[int]
    model: Optional[PrinterModel]
    device: object = None  # bleak BLEDevice

    @property
    def known(self) -> bool:
        return self.model is not None

    def __str__(self) -> str:
        fam = self.model.family.value if self.model else "?"
        return f"{self.name} [{self.address}] {fam} rssi={self.rssi}"


async def discover(
    timeout: float = 6.0,
    *,
    known_only: bool = True,
    name: Optional[str] = None,
    stop_on_first: bool = False,
) -> List[FoundPrinter]:
    """Scan for printers.

    ``known_only`` keeps only catalog models (plus anything advertising the printer service).
    ``name`` keeps devices whose name contains it (case/space insensitive).
    """
    from bleak import BleakScanner

    found: Dict[str, FoundPrinter] = {}
    done = asyncio.Event()
    wanted = re.sub(r"\s+", "", name).upper() if name else None
    printer_service = {_uuid("ae30"), _uuid("af30"), _uuid("ff00"), _uuid("200a")}

    def on_adv(device, adv) -> None:  # noqa: ANN001 - bleak types
        adv_name = adv.local_name or device.name or ""
        if not adv_name:
            return
        mfr: Mapping[int, bytes] = getattr(adv, "manufacturer_data", None) or {}
        model = identify(adv_name, mfr)
        services = {s.lower() for s in (getattr(adv, "service_uuids", None) or [])}
        if known_only and model is None and not (services & printer_service):
            return
        if wanted and wanted not in re.sub(r"\s+", "", adv_name).upper():
            return
        found[device.address] = FoundPrinter(adv_name, device.address, getattr(adv, "rssi", None), model, device)
        if stop_on_first:
            done.set()

    scanner = BleakScanner(detection_callback=on_adv)
    await scanner.start()
    try:
        try:
            await asyncio.wait_for(done.wait(), timeout)
        except asyncio.TimeoutError:
            pass
    finally:
        await scanner.stop()
    return sorted(found.values(), key=lambda p: -(p.rssi if p.rssi is not None else -999))


async def find_printer(target: Optional[str] = None, timeout: float = 10.0) -> FoundPrinter:
    """Find one printer by name fragment, by address, or the strongest known one when ``target`` is None."""
    if target and looks_like_address(target):
        from bleak import BleakScanner

        device = await BleakScanner.find_device_by_address(target, timeout=timeout)
        if device is None:
            raise PrinterNotFoundError(f"no device with address {target} is advertising")
        name = device.name or ""
        return FoundPrinter(name, device.address, None, identify(name), device)
    results = await discover(timeout, known_only=target is None, name=target, stop_on_first=True)
    if not results:
        what = f"named {target!r}" if target else "from the supported list"
        raise PrinterNotFoundError(
            f"no printer {what} found. Is it switched on, close by, and not connected to a phone?"
        )
    return results[0]


# ---------------------------------------------------------------------------------- BLE link ----
class BleTransport(Transport):
    """GATT connection through bleak."""

    def __init__(self, found: FoundPrinter, connect_timeout: float = 15.0) -> None:
        self.name = found.name
        self.address = found.address
        self._target = found.device or found.address
        self._timeout = connect_timeout
        self._client = None
        self._write_char = None
        self._data_char = None
        self._notify_chars: List[object] = []
        self._handler: Optional[NotifyHandler] = None
        self._write_response = False
        self._data_response = False

    async def connect(self) -> None:
        from bleak import BleakClient
        from bleak.exc import BleakError

        self._client = BleakClient(self._target, timeout=self._timeout)
        try:
            await self._client.connect()
        except (BleakError, asyncio.TimeoutError, OSError) as exc:
            raise ConnectionFailedError(f"could not connect to {self.name or self.address}: {exc}") from exc
        backend = getattr(self._client, "_backend", None)
        acquire = getattr(backend, "_acquire_mtu", None)
        if acquire is not None:  # BlueZ needs an explicit MTU exchange
            try:
                await acquire()
            except Exception:  # pragma: no cover - backend specific
                pass
        try:
            self.mtu = int(self._client.mtu_size or 23)
        except Exception:  # pragma: no cover
            self.mtu = 23
        log.debug("connected to %s, MTU %s", self.address, self.mtu)

    @property
    def is_connected(self) -> bool:
        return bool(self._client is not None and self._client.is_connected)

    def set_notify_handler(self, handler: Optional[NotifyHandler]) -> None:
        self._handler = handler

    def _on_notify(self, _sender, data: bytearray) -> None:  # noqa: ANN001
        if self._handler is not None:
            try:
                self._handler(bytes(data))
            except Exception:  # pragma: no cover - never break bleak's loop
                log.exception("notification handler failed")

    def _select(self, family: Optional[Family]) -> None:
        services = self._client.services
        for service_uuid, write_uuid, notify_uuid, data_uuid in _LAYOUTS:
            service = services.get_service(service_uuid)
            if service is None:
                continue
            write = service.get_characteristic(write_uuid)
            notify = service.get_characteristic(notify_uuid)
            data = service.get_characteristic(data_uuid) if data_uuid else None
            if write is None:
                continue
            self._write_char = write
            self._notify_chars = [notify] if notify is not None else []
            if family is Family.V5X and data is not None:
                self._data_char = data
            else:
                self._data_char = write
            break
        if self._write_char is None:
            for service in services:
                for ch in service.characteristics:
                    props = set(ch.properties)
                    if self._write_char is None and ({"write-without-response", "write"} & props) and "read" not in props:
                        self._write_char = ch
                    if "notify" in props or "indicate" in props:
                        self._notify_chars.append(ch)
            self._data_char = self._write_char
        if self._write_char is None:
            raise ConnectionFailedError("the device has no writable characteristic; is it a printer?")
        self._write_response = "write-without-response" not in self._write_char.properties
        self._data_response = "write-without-response" not in self._data_char.properties
        log.debug(
            "using write=%s data=%s notify=%s",
            self._write_char.uuid, self._data_char.uuid, [c.uuid for c in self._notify_chars],
        )

    async def start(self, family: Optional[Family]) -> None:
        if not self.is_connected:
            raise ConnectionFailedError("not connected")
        already = list(self._notify_chars)
        self._write_char = None
        self._data_char = None
        self._notify_chars = []
        self._select(family)
        for ch in self._notify_chars:
            if any(c.uuid == ch.uuid for c in already):
                continue  # still subscribed from a previous call
            try:
                await self._client.start_notify(ch, self._on_notify)
            except Exception as exc:  # pragma: no cover - device specific
                log.warning("could not subscribe to %s: %s", ch.uuid, exc)

    async def write(self, data: bytes, *, channel: str = "cmd") -> None:
        if not self.is_connected:
            from .exceptions import NotConnectedError

            raise NotConnectedError("printer disconnected")
        if channel == "data":
            await self._client.write_gatt_char(self._data_char, data, response=self._data_response)
        else:
            await self._client.write_gatt_char(self._write_char, data, response=self._write_response)

    async def close(self) -> None:
        client, self._client = self._client, None
        if client is None:
            return
        try:
            for ch in self._notify_chars:
                try:
                    await client.stop_notify(ch)
                except Exception:
                    pass
            await client.disconnect()
        except Exception:  # pragma: no cover
            pass
