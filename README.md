# purrint 🐱🖨️

**Print photos, text and QR codes on cheap Bluetooth thermal "cat" printers from Python** – MX10, MX06,
MX05, GB01-style, MXW01, X1, C17 and **107 advertised models** in total, on Windows, Linux and macOS.

```bash
pip install purrint          # add [qr] for QR codes:  pip install "purrint[qr]"
```

```python
import purrint

with purrint.connect_sync() as printer:            # nearest supported printer
    printer.print_image("photo.jpg")               # auto-rotated, dithered, sized to the paper
    printer.print_text("Hello from Python!", size=36, align="center")
```

No vendor app, no account, no cloud. purrint talks to the printer directly over Bluetooth Low Energy.

---

## Features

| | |
|---|---|
| 🔍 **Discovery** | Scan, identify the model by its Bluetooth name, or auto-detect the protocol of unknown clones. |
| 🖼️ **Images** | Phone EXIF orientation, landscape photos turned 90° to use the paper length, brightness / contrast / gamma / sharpen / invert, 6 dithering algorithms, true **16-level grayscale** on V5X printers. |
| 🔤 **Text** | System fonts or your own `.ttf`, word wrap, left/center/right, bold, monospace, underline, inverted. |
| 🔳 **QR codes & rules** | QR with caption, solid/dashed/dotted separators, `stack()` to build receipts. |
| 🔥 **Heat control** | `density` 1–7 mapped to each model's own tables, or raw `energy` (V5G) / `intensity` (V5X), print `speed` and `quality`. |
| 🌡️ **Status** | Out of paper, cover open, overheated head (waits for it to cool), low battery, head temperature, battery %, firmware, serial, head type. |
| ⏱️ **Real completion** | Waits until the paper has *physically* stopped, with flow control and a live head-position estimate for progress bars. |
| 📄 **Paper** | Feed (in dots or mm), retract, cancel, copies with cool-down, batches of pictures. |
| 🧪 **Simulator** | `connect_simulated("MX10")` – same API, no hardware; save exactly what would print. |
| ⚙️ **APIs** | Async (`asyncio`), blocking (`connect_sync`, `quick_print`) and a CLI (`purrint ...`). |

## Command line

```bash
purrint scan                                  # printers in range
purrint models                                # the 107 supported names
purrint info                                  # firmware, serial, status, temperature
purrint image photo.jpg holiday/*.jpg         # print pictures (landscape ones are rotated)
purrint image photo.jpg --dither atkinson --density 5 --contrast 15
purrint image photo.jpg --gray                # 16-level grayscale (V5X printers)
purrint text "Shopping list:\n- milk\n- eggs" --size 30 --bold
purrint qr https://example.com --caption "scan me"
purrint feed 100
purrint text "test" --simulate preview.png    # no printer needed
```

Add `-p MX10` (name fragment) or `-p AA:BB:CC:DD:EE:FF` to choose a printer, `-v`/`-vv` for logs.

## Python API

### Async

```python
import asyncio
import purrint

async def main():
    async with await purrint.connect("MX10") as printer:
        print(printer.info.firmware, printer.status)

        await printer.print_image(
            "photo.jpg",
            density=5,            # 1 light .. 7 darkest
            dither="floyd",       # floyd | atkinson | bayer | halftone | threshold
            rotate="auto",        # landscape -> portrait; or 0/90/180/270
            contrast=10,
            copies=2, cooldown=5, # rest the head between copies
            on_progress=lambda p: print(p.phase, p.current_line, "/", p.lines),
        )
        await printer.print_text("Thanks!", size=40, bold=True, align="center")
        await printer.print_qr("https://example.com", caption="our web")
        await printer.feed_mm(10)

asyncio.run(main())
```

### Blocking

```python
import purrint

printer = purrint.connect_sync()          # or connect_sync("MXW01") / connect_sync("AA:BB:...")
printer.print_image("photo.jpg", gray=True)
print(printer.refresh_status())
printer.disconnect()

purrint.quick_print("photo.jpg")                     # connect, print, disconnect
purrint.quick_print(None, text="Hello!", size=40)
```

### Build your own layout

```python
from purrint import render_text, render_qr, render_separator, stack, prepare

ticket = stack([
    render_text("CAFÉ PURR", size=48, bold=True, align="center"),
    render_separator(style="dashed"),
    render_text("Latte ......... 3.00\nCookie ........ 1.50", mono=True),
    render_qr("https://example.com/receipt/42", size=200),
])
await printer.print_raster(ticket)
```

`prepare(source, width=384, options=ImageOptions(...))` gives you the exact dithered image before
printing; `preview(img)` turns it into a paper-like picture for your UI.

### Events and errors

```python
unsubscribe = printer.on(lambda kind, payload: print(kind, payload))
# kinds: status, temperature, buffer_full, buffer_free, firmware, serial, print_done, challenge ...

try:
    await printer.print_text("hi")
except purrint.OutOfPaperError:
    print("load paper")
except purrint.OverheatError:
    print("let it cool down")
except purrint.PrinterNotFoundError:
    print("switch it on / disconnect the phone app")
```

All purrint errors derive from `purrint.PurrintError`.

## Supported printers

Printers are identified by the name they advertise over Bluetooth (case and spaces are ignored, and
suffixes like `MX10-8A3F` are understood). Devices that are not listed can still work: purrint probes
both protocols, or you can force one with `connect(..., family="V5G")`.

**V5G protocol (50):** MX01, MX02, MX03, MX05, MX06, MINI PRINTER, JL-BR22, MX07, MX08, MX09,
URBANWORX KIDS CAMERA, CYLO BT PRINTER, MXTP-100, AZ-P2108X, MX10, MX11, MX12, PD01, MINISO-M1, LP212,
XO POPPY, MX13, BQ01, BQ02, EWTTO ET-Z0499, BQ05, BQ06, BQ07, BQ7A, BQ7B, BQ08, BQ95, BQ96, MXW009,
MXW010, EWTTO ET-N3689, EWTTO ET-N3687, MXPC-100, GV-MA211, KP-IM606, BQ95B, BQ03, BQ95C, BQ06B, X6,
K06, BQ17, IM.17, C18, MINISO-M12

**V5X protocol – MXW01 board (57):** MXW01, X1, X2, C17, MXW-W5, MXW01-1, Portable Printer,
Instant Print Plus, REKA, HDMDT-00, JK01, BH03, BHSZY, PD03, FLYINGTIGER097, LP215, KERUI, AI01, M8HZ,
HZ-M8, Q15, M13, Q15A, Q15B, Q15C, Q15D, Q15E, Q15Z, STICKERMATE, Q17, MXW13, MXW18, ADQ19, QD01, JME13,
JME15, LP28AI, BQTLY, STERENIA-PRINT, LEAPOM, IHEARTYARD, ELECOUTEK, Q25SZY, TCM747736, P4, RS6301985,
M13SZY, TK914, TK894, D20, Q20, Q16SZY, OHELLAATP01, Q5, Q6, JME05, Q10

### Test status – please read

| | |
|---|---|
| ✅ **Tested on hardware** | **MX10** (V5G, firmware 1.0.11): scan, info, status, temperature, text, photos, QR, feed, completion detection – on Windows 10. |
| 🧪 **Implemented, not yet tested on hardware** | The **V5X / MXW01** protocol (dot and grayscale printing, intensity, status, version, head type, feed, cancel). It is built from the documented protocol and checked byte-for-byte against known command sequences and a full simulator, but nobody has run this release on an MXW01 yet. |
| ⚠️ **Firmware dependent** | `retract()` (V5G), the `cover_open` flag, battery level on V5G printers (not reported). |

If you own a printer from the V5X list, a report (works / doesn't, with `purrint -vv info` output) is
the most valuable contribution you can make.

Some firmwares send an authentication challenge (`D6` on V5G, `B3` on V5X) that the vendor apps answer
with a secret key. purrint does **not** ship that key; printers tested so far print without answering it.
The `challenge` event tells you if your printer sends one.

## Requirements and tips

- Python 3.9+, Bluetooth Low Energy adapter. Dependencies: [bleak](https://github.com/hbldh/bleak) and Pillow.
- **The printer must not be connected to a phone** – BLE printers accept one connection at a time and stop
  advertising while connected.
- Windows 10/11: works out of the box (no pairing needed).
- Linux: BlueZ 5.55+; your user needs access to Bluetooth (usually the `bluetooth` group).
- macOS: grant Bluetooth permission to your terminal/IDE.
- Paper is 57 mm wide; the head prints 384 dots (48 mm) at 203 dpi, i.e. 8 dots per mm.
- Long batches: use `cooldown=` / `print_many(..., cooldown=5)` so cheap heads don't overheat.

## How it works (short)

| | V5G (`51 78 …`) | V5X (`22 21 …`) |
|---|---|---|
| Channel | `ae01` write, `ae02` notify (or `ff02/ff03`) | `ae01` commands, `ae03` bitmap data, `ae02` notify |
| Job | density, quality, lattice, energy, mode, speed, **one `A2` frame per line**, feed, lattice end | intensity `A2`, request `A9` → ack, raw bitmap, flush `AD` → done `AA` |
| Bits | 48 bytes/line, left dot = bit 0 | 48 bytes/line (1-bit) or 192 bytes/line (4-bit gray, left dot = high nibble) |
| Flow | `AE 10` pause / `AE 00` resume & finished | whole bitmap buffered |

Every frame is `magic, command, 0x00, length (LE16), payload, CRC-8 (poly 0x07) of payload, 0xFF`.
The `purrint.protocol` package exposes pure, I/O-free encoders/decoders if you want to build your own transport.

## Development

```bash
python -m venv .venv && .venv/Scripts/activate      # Windows   (source .venv/bin/activate elsewhere)
pip install -e ".[dev]"
pytest                                                # 50 tests, no hardware needed
```

---

## En español

`purrint` es un paquete de Python para imprimir en las impresoras térmicas Bluetooth baratas (las
"cat printers": MX10, MX06, MXW01, X1, C17… **107 nombres**) sin la app del fabricante.

```bash
pip install "purrint[qr]"
```

```python
import purrint

with purrint.connect_sync() as impresora:              # la impresora compatible más cercana
    impresora.print_image("foto.jpg", density=5)        # las fotos horizontales se giran solas
    impresora.print_text("¡Hola desde Python!", size=36, align="center", bold=True)
    impresora.print_qr("https://example.com", caption="escanéame")
    print(impresora.refresh_status())                   # papel, sobrecalentamiento, temperatura…
```

Desde la terminal: `purrint scan`, `purrint image foto.jpg`, `purrint text "hola"`, `purrint info`.
Sin impresora puedes probar con `--simulate vista.png` o `purrint.connect_simulated("MX10")`.

**Importante:** apaga el Bluetooth del teléfono (o cierra la app) antes de conectar desde la PC; estas
impresoras solo aceptan una conexión a la vez. Probado en una MX10 real con Windows 10; la familia V5X
(MXW01) está implementada y probada con el simulador, pero aún no con hardware real.

## License

MIT. purrint is an independent, clean-room implementation and is not affiliated with any printer vendor
or app. All product names are trademarks of their respective owners and are used only to identify
compatible hardware.
