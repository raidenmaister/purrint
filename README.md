<p align="right">
  <a href="https://github.com/raidenmaister/purrint/blob/main/README.es.md"><img src="https://img.shields.io/badge/Language-%F0%9F%87%AA%F0%9F%87%B8%20Espa%C3%B1ol-238636?style=flat-square" alt="Español"></a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/raidenmaister/purrint/main/docs/logo.svg" alt="purrint logo" width="360">
</p>

<h3 align="center">
  Thermal Bluetooth Printer Driver and CLI for Python
</h3>

<p align="center">
  <a href="https://raidenmaister.github.io/purrint/"><img src="https://img.shields.io/badge/docs-GitHub_Pages-blue.svg" alt="Documentation"></a>
  <a href="https://pypi.org/project/purrint/"><img src="https://img.shields.io/pypi/v/purrint.svg" alt="PyPI version"></a>
  <a href="https://pypi.org/project/purrint/"><img src="https://img.shields.io/pypi/pyversions/purrint.svg" alt="Python versions"></a>
  <a href="https://github.com/raidenmaister/purrint/actions/workflows/test.yml"><img src="https://github.com/raidenmaister/purrint/actions/workflows/test.yml/badge.svg" alt="Build Status"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://github.com/raidenmaister/purrint"><img src="https://img.shields.io/badge/types-typed-blue.svg" alt="Type Annotated"></a>
</p>

---

**purrint** is an independent, clean-room Python library and command-line interface for communicating with low-cost Bluetooth Low Energy thermal printers (commonly marketed as pocket or cat printers: MX10, MX06, GB01-style, MXW01, and over 100 compatible models). It operates directly via BLE without vendor apps, accounts, or cloud services.

## Installation

```bash
pip install purrint
```

To enable QR code generation, install with the optional `qr` extra:

```bash
pip install "purrint[qr]"
```

## Quickstart

```python
import purrint

with purrint.connect_sync() as printer:
    printer.print_image("photo.jpg")
    printer.print_text("Hello from Python!", size=36, align="center")
```

## Features

| Capability | Description |
|---|---|
| **Discovery** | Scan for nearby devices, identify models by BLE advertised names, or probe protocols on unknown clones. |
| **Image Processing** | Automatic EXIF orientation, 90-degree landscape rotation, brightness/contrast/gamma controls, 6 dithering algorithms, and 16-level grayscale support on V5X hardware. |
| **Text Rendering** | System or custom TrueType fonts, word wrapping, alignment (left/center/right), bold, underline, monospace, and inverted styles. |
| **Receipt Composition** | QR code rendering with captions, solid/dashed/dotted line separators, and stackable raster components. |
| **Thermal Regulation** | Preset densities (1 to 7) mapped per model, raw energy/intensity overrides, and configurable print speed. |
| **Hardware Telemetry** | Status monitoring for out-of-paper conditions, open cover, head temperature, battery level, firmware version, and serial number. |
| **Print Verification** | Physical print-head progress estimation and flow control to wait until paper feeding completes. |
| **Paper Management** | Feed in dots or millimeters, retraction, print cancellation, and multi-copy printing with cooling intervals. |
| **Virtual Simulator** | Built-in software simulator (`connect_simulated`) for testing pipelines without physical hardware. |
| **Interfaces** | Full `asyncio` API, blocking synchronous API (`connect_sync`), and a CLI tool (`purrint`). |

## Command-Line Interface

The package installs the `purrint` command:

```bash
# Discover printers in range
purrint scan

# List all 107 recognized hardware model names
purrint models

# Query hardware state and firmware details
purrint info

# Print one or multiple images
purrint image photo.jpg holiday/*.jpg

# Print images with custom dither and contrast
purrint image photo.jpg --dither atkinson --density 5 --contrast 15

# Print text with formatting
purrint text "Shopping list:\n- Milk\n- Eggs" --size 30 --bold

# Print QR code with caption
purrint qr https://example.com --caption "Scan to visit"

# Advance paper feed
purrint feed 100

# Render to an image preview without physical hardware
purrint text "Test receipt" --simulate preview.png
```

Use `-p <NAME_OR_MAC>` to select a target device, and `-v` or `-vv` for verbose transport logging.

## Python API

### Asynchronous API

```python
import asyncio
import purrint

async def main():
    async with await purrint.connect("MX10") as printer:
        print(f"Firmware: {printer.info.firmware}, Status: {printer.status}")

        await printer.print_image(
            "photo.jpg",
            density=5,            # Thermal density: 1 (lightest) .. 7 (darkest)
            dither="floyd",       # floyd | atkinson | bayer | halftone | threshold
            rotate="auto",        # Automatically rotate landscape photos
            contrast=10,
            copies=2,
            cooldown=5,           # Rest interval in seconds between copies
            on_progress=lambda p: print(f"{p.phase}: {p.current_line}/{p.lines}"),
        )

        await printer.print_text("Thank you for your purchase!", size=36, bold=True, align="center")
        await printer.print_qr("https://example.com", caption="Visit Website")
        await printer.feed_mm(10)

asyncio.run(main())
```

### Synchronous API

For scripts that do not run an event loop:

```python
import purrint

# Context manager automatically connects and disconnects
with purrint.connect_sync() as printer:
    printer.print_image("photo.jpg", gray=True)
    status = printer.refresh_status()
    print("Status:", status)

# Direct one-shot helper
purrint.quick_print("photo.jpg")
purrint.quick_print(None, text="Order #1048", size=32)
```

### Layout and Custom Receipts

Combine multiple elements into a single contiguous print job:

```python
from purrint import render_text, render_qr, render_separator, stack

ticket = stack([
    render_text("COFFEE SHOP", size=48, bold=True, align="center"),
    render_separator(style="dashed"),
    render_text("Espresso ........ 2.50\nCroissant ....... 1.80", mono=True),
    render_separator(style="solid"),
    render_qr("https://example.com/receipt/1048", size=200),
])

await printer.print_raster(ticket)
```

### Exception Handling

All library exceptions inherit from `purrint.PurrintError`:

```python
import purrint

try:
    with purrint.connect_sync() as printer:
        printer.print_text("Sample")
except purrint.OutOfPaperError:
    print("Error: Printer is out of paper.")
except purrint.OverheatError:
    print("Error: Thermal head is cooling down.")
except purrint.PrinterNotFoundError:
    print("Error: No printer found. Ensure device is powered on and Bluetooth is active.")
```

## Supported Hardware

Printers are identified by their advertised BLE broadcast name. Case and trailing random suffixes (e.g. `MX10-8A3F`) are handled automatically.

- **V5G Protocol Family (50 Models):**  
  MX01, MX02, MX03, MX05, MX06, MINI PRINTER, JL-BR22, MX07, MX08, MX09, URBANWORX KIDS CAMERA, CYLO BT PRINTER, MXTP-100, AZ-P2108X, MX10, MX11, MX12, PD01, MINISO-M1, LP212, XO POPPY, MX13, BQ01, BQ02, EWTTO ET-Z0499, BQ05, BQ06, BQ07, BQ7A, BQ7B, BQ08, BQ95, BQ96, MXW009, MXW010, EWTTO ET-N3689, EWTTO ET-N3687, MXPC-100, GV-MA211, KP-IM606, BQ95B, BQ03, BQ95C, BQ06B, X6, K06, BQ17, IM.17, C18, MINISO-M12.

- **V5X Protocol Family / MXW01 Mainboard (57 Models):**  
  MXW01, X1, X2, C17, MXW-W5, MXW01-1, Portable Printer, Instant Print Plus, REKA, HDMDT-00, JK01, BH03, BHSZY, PD03, FLYINGTIGER097, LP215, KERUI, AI01, M8HZ, HZ-M8, Q15, M13, Q15A, Q15B, Q15C, Q15D, Q15E, Q15Z, STICKERMATE, Q17, MXW13, MXW18, ADQ19, QD01, JME13, JME15, LP28AI, BQTLY, STERENIA-PRINT, LEAPOM, IHEARTYARD, ELECOUTEK, Q25SZY, TCM747736, P4, RS6301985, M13SZY, TK914, TK894, D20, Q20, Q16SZY, OHELLAATP01, Q5, Q6, JME05, Q10.

### Verification Status

| Category | Details |
|---|---|
| **Verified on Hardware** | **MX10** (V5G, firmware 1.0.11): Device discovery, telemetry, text printing, raster images, QR codes, feed operations, and completion synchronization tested on Windows 10. |
| **Verified via Simulator** | **V5X / MXW01**: Protocol implementation (dot and 4-bit grayscale rasterization, intensity control, head telemetry) verified byte-for-byte against captured traces and protocol specifications. |
| **Firmware Dependent** | Reverse feeding (`retract`), open-cover sensor reporting, and battery percentages on V5G devices depend on individual firmware revisions. |

## Platform and Connection Notes

- **Single Host Requirement:** Bluetooth Low Energy printers accept only one active connection at a time. Disconnect mobile applications or phone Bluetooth before connecting from a desktop.
- **Windows 10/11:** Native support without manual pairing.
- **Linux:** Requires BlueZ 5.55+ and appropriate permissions (user in `bluetooth` group).
- **macOS:** Grant Bluetooth permissions to the host terminal or application.
- **Hardware Specs:** Standard roll width is 57 mm. Print head contains 384 dots (48 mm effective width) at 203 DPI (8 dots/mm).

## Development

```bash
git clone https://github.com/raidenmaister/purrint.git
cd purrint
python -m venv .venv
# Windows: .venv\Scripts\activate | Unix: source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

This project is licensed under the terms of the [MIT License](LICENSE).

All brand names, trademarks, and model numbers are the property of their respective owners and are referenced solely for hardware compatibility purposes.
