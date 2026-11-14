# Changelog

## 0.1.0 – 2026-11-13

First public release.

- Two protocol families: **V5G** (`51 78`, MX10/MX06/GB01-style) and **V5X** (`22 21`, MXW01 board,
  including the whole V5X_S group).
- Catalog of 107 advertised names with their family, product kind and density tables.
- Automatic protocol probing for printers that are not in the catalog.
- Images: EXIF orientation, auto-rotation of landscape photos, brightness/contrast/gamma/sharpen/invert,
  six dithering methods, 16-level grayscale on V5X printers.
- Text (system fonts, wrapping, alignment, bold, monospace, underline), QR codes, separators.
- Density 1–7 mapped per model, raw energy/intensity/speed/quality overrides, copies with cool-down.
- Flow control, physical completion detection, head position estimate and progress callbacks.
- Status: paper, cover, overheat, low battery, temperature, battery level, firmware, serial, head type.
- Paper feed / retract, cancel.
- Async API, blocking API (`connect_sync`, `quick_print`), CLI (`purrint ...`) and a simulator.
