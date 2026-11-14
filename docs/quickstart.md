# Quickstart Guide

This guide walks through establishing a connection, querying device telemetry, and printing your first document.

---

## Prerequisites

1. A computer equipped with a functional Bluetooth 4.0+ (BLE) adapter.
2. An active, supported thermal printer powered on and loaded with paper.
3. **Important:** Ensure the printer is not actively connected to a smartphone application. Bluetooth Low Energy thermal printers accept only one active connection at a time and stop broadcasting when paired.

---

## 1. Discovering Nearby Printers

Use the discovery API to locate printers within radio range:

=== "Python"

    ```python
    import purrint

    # Synchronous scan
    devices = purrint.scan_sync(timeout=5.0)
    for dev in devices:
        print(f"Name: {dev.name}, Address: {dev.address}, RSSI: {dev.rssi}")
    ```

=== "CLI"

    ```bash
    purrint scan
    ```

---

## 2. Connecting to a Printer

The connection helper connects to the nearest recognized printer if no identifier is passed, or accepts a name fragment or MAC address:

```python
import purrint

# Connect to the nearest detected printer
with purrint.connect_sync() as printer:
    print(f"Connected to model: {printer.model.name} (Protocol: {printer.family.name})")
```

To target a specific printer:

```python
# Match by device name fragment
with purrint.connect_sync("MX10") as printer:
    ...

# Match by explicit MAC / UUID address
with purrint.connect_sync("AA:BB:CC:DD:EE:FF") as printer:
    ...
```

---

## 3. Querying Hardware Telemetry

You can read diagnostic status, battery levels, head temperatures, and firmware details:

```python
import purrint

with purrint.connect_sync() as printer:
    # Diagnostic flags
    status = printer.refresh_status()
    print("Paper present:", not status.out_of_paper)
    print("Cover closed:", not status.cover_open)
    print("Temperature:", printer.temperature, "Celsius")

    # Hardware info
    info = printer.get_info()
    print("Firmware:", info.firmware)
    print("Serial:", info.serial)
```

---

## 4. One-Shot Quick Printing

For scripts that simply need to send an image or text without manually managing connection handles:

```python
import purrint

# Connect, print, feed paper, and disconnect in a single call
purrint.quick_print("cat_photo.jpg", density=5)

# Quick text print
purrint.quick_print(None, text="Order ID #84910\nStatus: Verified", size=30)
```
