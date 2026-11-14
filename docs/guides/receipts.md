# Receipts, Dividers and QR Codes

To generate complete receipts, labels, and badges, `purrint` provides raster composition helpers that stack visual elements vertically into a single cohesive print buffer.

---

## Example Output

Below is a complete receipt layout composed using `stack()`, `render_text()`, `render_separator()`, and `render_qr()`:

<p align="center">
  <img src="../../images/receipt_sample.png" alt="Generated receipt preview" width="384">
  <br>
  <em>Rendered receipt output from virtual simulator (384 dots width)</em>
</p>

---

## Layout Composition with `stack()`

The `stack()` function takes a list of Pillow images and joins them top-to-bottom, ensuring the resulting raster matches the exact printer width (384 dots):

```python
import purrint
from purrint import render_text, render_separator, render_qr, stack

# Compose the receipt blocks
ticket = stack([
    # Store Header
    render_text("COFFEE & CATS", size=38, bold=True, align="center"),
    
    # Dashed divider line
    render_separator(style="dashed"),
    
    # Line items
    render_text(
        "Date: 2026-11-13\n"
        "Item: Americano ...... 3.50\n"
        "Item: Cat Treat ...... 1.50",
        mono=True,
        size=22,
    ),
    
    # Solid divider line
    render_separator(style="solid"),
    
    # QR Code with caption
    render_qr(
        "https://github.com/raidenmaister/purrint",
        size=180,
        caption="scan for receipt",
    ),
])

# Send the entire composed job to the printer
with purrint.connect_sync() as printer:
    printer.print_raster(ticket)
```

---

## Divider Styles

The `render_separator(width, style, thickness)` helper supports three pattern styles:

- `style="solid"`: Continuous horizontal rule.
- `style="dashed"`: Alternating dash pattern.
- `style="dotted"`: Uniform pixel dots.

```python
# Solid 2-pixel separator
sep_solid = render_separator(style="solid", thickness=2)

# Dashed line
sep_dashed = render_separator(style="dashed", thickness=1)
```

---

## QR Code Options

The `render_qr(data, size, caption, ...)` helper requires the optional `qrcode` package (`pip install "purrint[qr]"`):

```python
qr_img = render_qr(
    "https://example.com/order/1092",
    size=200,                  # Bounding box in pixels
    caption="Order Verification", # Optional label beneath code
    caption_size=20,
)
```
