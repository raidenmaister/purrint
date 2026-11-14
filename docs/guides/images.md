# Printing Images and Dithering

Thermal printers reproduce graphics using single-color heating elements arranged across a 384-dot horizontal line. Continuous-tone photographs must be converted into binary dot patterns (dithered) or 4-bit grayscale nibbles (supported on V5X hardware).

---

## Source Image Preparation

Below is an unmodified input photograph (Public Domain / CC0):

<p align="center">
  <img src="../../images/cat_original.jpg" alt="Source photograph" width="384">
  <br>
  <em>Input source: 384 px wide continuous-tone photograph</em>
</p>

---

## Dithering Algorithms Compared

`purrint` includes six built-in rendering algorithms via `ImageOptions(dither=...)`:

### 1. Floyd-Steinberg (`dither="floyd"`)
Default algorithm. Error-diffusion dither providing smooth gradients and natural transitions for general photography.

<p align="center">
  <img src="../../images/cat_floyd.png" alt="Floyd-Steinberg Dither" width="384">
</p>

```python
printer.print_image("cat.jpg", dither="floyd")
```

---

### 2. Atkinson (`dither="atkinson"`)
Developed by Bill Atkinson at Apple Computer. Diffuses only 75% of the error, preserving cleaner highlights and higher localized contrast. Recommended for small portraits and detailed line subjects.

<p align="center">
  <img src="../../images/cat_atkinson.png" alt="Atkinson Dither" width="384">
</p>

```python
printer.print_image("cat.jpg", dither="atkinson", contrast=15)
```

---

### 3. Bayer Ordered (`dither="bayer"`)
An 8x8 ordered threshold matrix producing a uniform geometric cross-hatch pattern. Extremely fast and resistant to paper-feed banding artifacts.

<p align="center">
  <img src="../../images/cat_bayer.png" alt="Bayer Ordered Dither" width="384">
</p>

```python
printer.print_image("cat.jpg", dither="bayer")
```

---

### 4. Halftone Screen (`dither="halftone"`)
Simulates traditional newspaper rotary press dot clustering. Excellent readability under low-contrast paper stocks.

<p align="center">
  <img src="../../images/cat_halftone.png" alt="Halftone Dither" width="384">
</p>

```python
printer.print_image("cat.jpg", dither="halftone")
```

---

### 5. Fixed Cutoff Threshold (`dither="threshold"`)
Direct binary thresholding without error distribution. Intended for black-and-white logos, icons, diagrams, and barcodes.

<p align="center">
  <img src="../../images/cat_threshold.png" alt="Threshold Dither" width="384">
</p>

```python
printer.print_image("logo.png", dither="threshold", threshold=128)
```

---

## Tone and Geometry Controls

All image parameters are exposed through `print_image(...)` or `ImageOptions`:

```python
await printer.print_image(
    "photo.jpg",
    rotate=0,             # 0: keep orientation | "auto": rotate landscape 90 deg | 90, 180, 270
    brightness=10,        # Integer range -100 to 100
    contrast=20,          # Integer range -100 to 100
    gamma=1.1,            # Floating point (>1.0 darkens midtones, <1.0 lightens)
    sharpen=True,         # High-pass convolution filter before dithering
    invert=False,         # Invert black and white pixels
    autocontrast=True,    # Maximize dynamic range using histogram stretching
    max_height=600,       # Clamp maximum vertical length
    copies=2,             # Number of prints
    cooldown=4.0,         # Cooling rest period in seconds between copies
)
```

---

## 16-Level Grayscale (V5X / MXW01 Hardware)

V5X hardware controllers support native pulse-width-modulated multi-level heating:

```python
# Enables 4-bit per pixel nibble stream (16 gray levels)
await printer.print_image("portrait.jpg", gray=True, intensity=85)
```
