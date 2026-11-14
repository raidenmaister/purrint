# Command-Line Interface (CLI)

`purrint` provides a full-featured command-line tool for scanning, inspecting, and printing directly from your terminal or shell scripts.

---

## Global Options

The CLI binary is invoked as `purrint <subcommand> [options]`.

| Flag | Description |
|---|---|
| `-p, --printer <NAME_OR_MAC>` | Target printer by name fragment or Bluetooth MAC address. |
| `-v, --verbose` | Enable debug logging. Pass `-vv` for raw BLE frame inspection. |
| `--help` | Show command reference and exit. |

---

## Subcommands

### `scan`
Scan the local radio environment for nearby Bluetooth Low Energy devices and identify supported thermal printer models.

```bash
purrint scan
```

---

### `models`
Print the list of all 107 recognized hardware models categorized by protocol family.

```bash
purrint models
```

---

### `info`
Connect to the printer, query hardware diagnostics, firmware revision, battery status, and head temperature.

```bash
purrint info
purrint info -p MX10
```

---

### `image`
Process and print one or more raster images.

```bash
purrint image photo.jpg
purrint image holiday/*.png --density 5 --contrast 15
```

**Options for `image`:**

| Flag | Argument | Default | Description |
|---|---|---|---|
| `--density` | `1..7` | `4` | Thermal burn time preset. |
| `--dither` | `name` | `floyd` | Dithering algorithm: `floyd`, `atkinson`, `bayer`, `halftone`, `threshold`. |
| `--rotate` | `angle` | `auto` | `auto` (rotates landscape 90 deg), `0` (no rotation), `90`, `180`, `270`. |
| `--contrast` | `-100..100`| `0` | Contrast adjustment. |
| `--brightness`| `-100..100`| `0` | Brightness adjustment. |
| `--gamma` | `float` | `1.0` | Gamma curve (>1.0 darkens, <1.0 lightens). |
| `--gray` | flag | `false` | Enable 16-level grayscale (V5X models only). |
| `--copies` | `int` | `1` | Number of copies to print. |
| `--cooldown` | `seconds` | `0.0` | Rest time between multiple copies. |
| `--simulate` | `file.png` | `None` | Save the rendered output as a PNG file instead of sending to hardware. |

---

### `text`
Render and print formatted text with automatic word wrapping.

```bash
purrint text "Receipt Line 1\nReceipt Line 2" --size 30 --bold
purrint text "Centred Notice" --align center --invert
```

**Options for `text`:**

| Flag | Argument | Default | Description |
|---|---|---|---|
| `--size` | `int` | `26` | Font point size. |
| `--bold` | flag | `false` | Render text in bold. |
| `--mono` | flag | `false` | Use monospace font metrics. |
| `--align` | `str` | `left` | Alignment: `left`, `center`, `right`. |
| `--underline`| flag | `false` | Draw underline under text. |
| `--invert` | flag | `false` | Invert text on black background strip. |
| `--simulate` | `file.png` | `None` | Save preview to PNG without hardware. |

---

### `qr`
Generate and print a QR code with an optional human-readable caption.

```bash
purrint qr https://example.com --caption "Scan to visit"
```

---

### `feed`
Advance paper by a specific number of dot lines.

```bash
# Feed 100 dots (approx. 12.5 mm)
purrint feed 100
```
