# purrint Documentation

<p align="center">
  <img src="logo.svg" alt="purrint logo" width="380">
</p>

**purrint** is an independent, clean-room Python library and command-line interface for communicating directly with Bluetooth Low Energy thermal printers (commonly marketed as pocket or cat printers: MX10, MX06, GB01-style, MXW01, and over 100 compatible hardware variants).

It operates locally over standard BLE channels without vendor apps, user accounts, proprietary drivers, or cloud services.

---

## Technical Specifications

| Parameter | Specification |
|---|---|
| **Supported Operating Systems** | Windows 10/11, Linux (BlueZ 5.55+), macOS |
| **Python Compatibility** | Python 3.9, 3.10, 3.11, 3.12, 3.13 |
| **Standard Paper Width** | 57 mm (2.24 inches) |
| **Effective Print Width** | 384 dots (48 mm) |
| **Thermal Resolution** | 203 DPI (8 dots per mm) |
| **Bluetooth Layer** | Bluetooth Low Energy (GATT / Bleak) |
| **Recognized Hardware Models** | 107 models across V5G and V5X protocol families |

---

## Core Architecture

The library is structured into distinct, modular layers:

- **Protocol Layer (`purrint.protocol`)**: Pure, I/O-free binary frame encoders, decoders, and CRC-8 calculation.
- **Driver Layer (`purrint.drivers`)**: Protocol-specific drivers for V5G (per-line packet streaming) and V5X (block-buffered transmission and 16-level grayscale).
- **Transport Layer (`purrint.transport`)**: Low-level BLE GATT connection management, service discovery, flow control, and notify handlers.
- **Imaging Pipeline (`purrint.imaging`)**: EXIF correction, aspect ratio scaling, tone adjustments, 6 dithering algorithms, and 1-bit / 4-bit packing.
- **High-Level API (`purrint.Printer`)**: Asynchronous and synchronous interfaces for printing, paper feeding, hardware telemetry, and job synchronization.

---

## Installation

Install the package via pip:

```bash
pip install purrint
```

To include QR code generation support, install with the `qr` extra:

```bash
pip install "purrint[qr]"
```

---

## Minimal Example

=== "Synchronous (Blocking)"

    ```python
    import purrint

    with purrint.connect_sync() as printer:
        printer.print_image("photo.jpg", density=5)
        printer.print_text("Receipt confirmation", size=32, align="center")
    ```

=== "Asynchronous (asyncio)"

    ```python
    import asyncio
    import purrint

    async def main():
        async with await purrint.connect("MX10") as printer:
            await printer.print_image("photo.jpg")
            await printer.print_text("Hello from Python!", size=36)

    asyncio.run(main())
    ```

=== "Command Line (CLI)"

    ```bash
    # Scan for printers
    purrint scan

    # Print an image
    purrint image photo.jpg --density 5

    # Print formatted text
    purrint text "Test Print" --bold --size 32
    ```
