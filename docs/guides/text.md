# Text Rendering and Typography

`purrint` includes a typography engine built on Pillow capable of rendering UTF-8 text with automatic word wrapping, variable alignment, custom font support, and thermal styling.

---

## Basic Text Printing

```python
with purrint.connect_sync() as printer:
    printer.print_text("Thermal Printing with Python", size=32, bold=True)
    printer.print_text("Sub-heading text aligned left", size=24)
```

---

## Alignment and Typography Controls

| Parameter | Type | Default | Description |
|---|---|---|---|
| `size` | `int` | `26` | Font size in points (approximate dot height). |
| `align` | `str` | `"left"` | Alignment across paper width: `"left"`, `"center"`, or `"right"`. |
| `bold` | `bool` | `False` | Renders a thickened stroke variant. |
| `mono` | `bool` | `False` | Enforces monospace metrics, useful for tables and alignment columns. |
| `underline` | `bool` | `False` | Draws an underline stroke beneath text baselines. |
| `invert` | `bool` | `False` | Renders white text on a solid black background strip. |
| `line_spacing` | `float` | `1.2` | Line height multiplier relative to font height. |
| `font` | `str | Path` | `None` | Path to a custom TrueType (`.ttf`) or OpenType (`.otf`) font file. |

---

## Code Examples

### Centered Title with Inverted Tag

```python
with purrint.connect_sync() as printer:
    printer.print_text("STORE DISPATCH", size=40, bold=True, align="center")
    printer.print_text(" EXPRESS DELIVERY ", size=24, bold=True, align="center", invert=True)
    printer.feed_mm(5)
```

### Monospaced Tabular Data

```python
receipt_lines = (
    "Item               Qty     Price\n"
    "--------------------------------\n"
    "Thermal Paper 57mm   2     $4.00\n"
    "Adhesive Rolls       1     $6.50\n"
    "--------------------------------\n"
    "TOTAL                     $10.50"
)

with purrint.connect_sync() as printer:
    printer.print_text(receipt_lines, size=22, mono=True)
```

### Loading Custom TrueType Fonts

```python
with purrint.connect_sync() as printer:
    printer.print_text(
        "Custom Typography",
        font="fonts/Roboto-Bold.ttf",
        size=34,
        align="center",
    )
```
