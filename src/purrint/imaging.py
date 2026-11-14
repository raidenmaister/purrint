"""Image preparation for thermal printing: load, orient, scale, tone, dither and pack."""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from typing import List, Optional, Sequence, Union

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

ImageSource = Union[str, "os.PathLike[str]", bytes, bytearray, io.IOBase, Image.Image]

DITHER_METHODS = ("floyd", "atkinson", "bayer", "halftone", "threshold", "none")

_BAYER8 = (
    (0, 32, 8, 40, 2, 34, 10, 42),
    (48, 16, 56, 24, 50, 18, 58, 26),
    (12, 44, 4, 36, 14, 46, 6, 38),
    (60, 28, 52, 20, 62, 30, 54, 22),
    (3, 35, 11, 43, 1, 33, 9, 41),
    (51, 19, 59, 27, 49, 17, 57, 25),
    (15, 47, 7, 39, 13, 45, 5, 37),
    (63, 31, 55, 23, 61, 29, 53, 21),
)


@dataclass(frozen=True)
class ImageOptions:
    """How to turn a picture into dots.

    * ``rotate``: ``"auto"`` turns landscape pictures 90° so they use the length of the paper;
      or an angle (0, 90, 180, 270) applied clockwise.
    * ``dither``: ``floyd`` (photos), ``atkinson`` (crisper photos), ``bayer`` (ordered pattern),
      ``halftone`` (newspaper dots), ``threshold`` (text/line art), ``none`` (grayscale printers only).
    * ``brightness`` / ``contrast``: -100..100. ``gamma``: >1 darkens mid-tones, <1 lightens them.
    * ``threshold``: 0..255 cut-off used by ``threshold`` dithering.
    """

    rotate: Union[str, int] = "auto"
    dither: str = "floyd"
    brightness: int = 0
    contrast: int = 0
    gamma: float = 1.0
    sharpen: bool = False
    invert: bool = False
    threshold: int = 128
    autocontrast: bool = False
    max_height: Optional[int] = None


def _pixels(img: Image.Image) -> list:
    """Flat pixel list on every Pillow version (``getdata`` is deprecated in Pillow 13+)."""
    getter = getattr(img, "get_flattened_data", None)
    return list(getter() if getter is not None else img.getdata())


def load_image(source: ImageSource) -> Image.Image:
    """Open a path, bytes, file object or PIL image, applying the EXIF orientation from phones."""
    if isinstance(source, Image.Image):
        img = source
    elif isinstance(source, (bytes, bytearray)):
        img = Image.open(io.BytesIO(bytes(source)))
    elif isinstance(source, io.IOBase):
        img = Image.open(source)  # type: ignore[arg-type]
    else:
        img = Image.open(os.fspath(source))
    img.load()
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:  # pragma: no cover - broken EXIF blocks
        pass
    return img


def _flatten(img: Image.Image) -> Image.Image:
    """Composite transparency on white and convert to 8-bit grayscale."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, rgba)
    return img.convert("L")


def _orient(img: Image.Image, rotate: Union[str, int]) -> Image.Image:
    if rotate == "auto":
        return img.rotate(-90, expand=True) if img.width > img.height else img
    angle = int(rotate) % 360
    if angle == 0:
        return img
    if angle not in (90, 180, 270):
        raise ValueError("rotate must be 'auto', 0, 90, 180 or 270")
    return img.rotate(-angle, expand=True)


def fit_width(img: Image.Image, width: int, max_height: Optional[int] = None) -> Image.Image:
    """Scale to exactly ``width`` dots keeping the aspect ratio."""
    height = max(1, round(img.height * width / img.width))
    if max_height and height > max_height:
        # Too tall: shrink proportionally and centre on a white strip of full width
        scale = max_height / height
        inner = img.resize((max(1, round(width * scale)), max_height), Image.Resampling.LANCZOS)
        canvas = Image.new("L", (width, max_height), 255)
        canvas.paste(inner, ((width - inner.width) // 2, 0))
        return canvas
    if (img.width, img.height) == (width, height):
        return img
    return img.resize((width, height), Image.Resampling.LANCZOS)


def adjust_tone(img: Image.Image, opts: ImageOptions) -> Image.Image:
    if opts.autocontrast:
        img = ImageOps.autocontrast(img, cutoff=1)
    if opts.brightness:
        img = ImageEnhance.Brightness(img).enhance(1 + max(-100, min(100, opts.brightness)) / 100)
    if opts.contrast:
        img = ImageEnhance.Contrast(img).enhance(1 + max(-100, min(100, opts.contrast)) / 100)
    if opts.gamma and abs(opts.gamma - 1.0) > 1e-3:
        g = float(opts.gamma)
        img = img.point([round(255 * ((i / 255) ** g)) for i in range(256)])
    if opts.sharpen:
        img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=2))
    if opts.invert:
        img = ImageOps.invert(img)
    return img


# --------------------------------------------------------------------------------- dithering ----
def _error_diffusion(img: Image.Image, kernel: Sequence[tuple], divisor: float) -> Image.Image:
    w, h = img.size
    buf = [float(v) for v in _pixels(img)]
    out = bytearray(w * h)
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            old = buf[i]
            new = 0.0 if old < 128 else 255.0
            out[i] = int(new)
            err = (old - new) / divisor
            if err:
                for dx, dy, weight in kernel:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and ny < h:
                        buf[ny * w + nx] += err * weight
    result = Image.new("L", (w, h))
    result.putdata(out)
    return result.convert("1", dither=Image.Dither.NONE)


_ATKINSON = ((1, 0, 1), (2, 0, 1), (-1, 1, 1), (0, 1, 1), (1, 1, 1), (0, 2, 1))


def _bayer(img: Image.Image) -> Image.Image:
    w, h = img.size
    src = img.load()
    out = Image.new("1", (w, h), 255)
    dst = out.load()
    for y in range(h):
        row = _BAYER8[y & 7]
        for x in range(w):
            if src[x, y] < (row[x & 7] + 0.5) * 4:
                dst[x, y] = 0
    return out


def _halftone(img: Image.Image, cell: int = 6) -> Image.Image:
    """Clustered-dot screen: dark areas grow round dots from each cell centre."""
    w, h = img.size
    src = img.load()
    out = Image.new("1", (w, h), 255)
    dst = out.load()
    order = sorted(
        ((x - (cell - 1) / 2) ** 2 + (y - (cell - 1) / 2) ** 2, x, y) for y in range(cell) for x in range(cell)
    )
    rank = [[0] * cell for _ in range(cell)]
    for r, (_, x, y) in enumerate(order):
        rank[y][x] = r
    n = cell * cell
    for y in range(h):
        ry = rank[y % cell]
        for x in range(w):
            if (255 - src[x, y]) * n / 256 > ry[x % cell] + 0.5:
                dst[x, y] = 0
    return out


def dither(img: Image.Image, method: str = "floyd", threshold: int = 128) -> Image.Image:
    """Return a mode ``"1"`` image (0 = black dot). ``img`` must be mode ``"L"``."""
    method = (method or "floyd").lower()
    if method in ("floyd", "floyd-steinberg", "fs"):
        return img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    if method == "atkinson":
        return _error_diffusion(img, _ATKINSON, 8.0)
    if method in ("bayer", "ordered"):
        return _bayer(img)
    if method == "halftone":
        return _halftone(img)
    if method in ("threshold", "none"):
        t = max(0, min(255, int(threshold)))
        return img.point(lambda v: 255 if v >= t else 0).convert("1", dither=Image.Dither.NONE)
    raise ValueError(f"unknown dither method {method!r}; choose one of {', '.join(DITHER_METHODS)}")


def quantize_gray16(img: Image.Image) -> Image.Image:
    """16-level grayscale (mode ``"L"`` with values multiple of 17) using Floyd-Steinberg."""
    palette_img = Image.new("P", (1, 1))
    palette = []
    for i in range(16):
        palette += [i * 17] * 3
    palette += [0] * (768 - len(palette))
    palette_img.putpalette(palette)
    quantized = img.convert("RGB").quantize(palette=palette_img, dither=Image.Dither.FLOYDSTEINBERG)
    return quantized.convert("L")


def prepare(
    source: ImageSource,
    width: int = 384,
    options: ImageOptions = ImageOptions(),
    gray: bool = False,
) -> Image.Image:
    """Full pipeline. Returns mode ``"1"`` (dots) or, with ``gray=True``, a 16-level mode ``"L"`` image."""
    img = load_image(source)
    img = _flatten(img)
    img = _orient(img, options.rotate)
    img = fit_width(img, width, options.max_height)
    img = adjust_tone(img, options)
    if gray:
        return quantize_gray16(img)
    return dither(img, options.dither, options.threshold)


# ----------------------------------------------------------------------------------- packing ----
def pack_1bpp(img: Image.Image, width: Optional[int] = None) -> List[bytes]:
    """Pack a mode ``"1"``/``"L"`` image into printer rows: bit 0 = left-most dot, 1 = black."""
    if img.mode != "1":
        img = img.convert("1", dither=Image.Dither.NONE)
    w = width or img.width
    bpl = (w + 7) // 8
    px = img.load()
    rows: List[bytes] = []
    iw = min(img.width, w)
    for y in range(img.height):
        row = bytearray(bpl)
        for x in range(iw):
            if px[x, y] == 0:
                row[x >> 3] |= 1 << (x & 7)
        rows.append(bytes(row))
    return rows


def pack_4bpp(img: Image.Image, width: Optional[int] = None) -> List[bytes]:
    """Pack a mode ``"L"`` image into 4-bit rows: two dots per byte, left dot in the high nibble,
    0 = white .. 15 = black."""
    if img.mode != "L":
        img = img.convert("L")
    w = width or img.width
    bpl = (w + 1) // 2
    px = img.load()
    rows: List[bytes] = []
    iw = min(img.width, w)
    for y in range(img.height):
        row = bytearray(bpl)
        for x in range(iw):
            level = 15 - min(15, (px[x, y] + 8) // 17)
            if x & 1:
                row[x >> 1] |= level
            else:
                row[x >> 1] |= level << 4
        rows.append(bytes(row))
    return rows


def preview(img: Image.Image, paper_margin: int = 12) -> Image.Image:
    """An RGB picture of how the job looks on paper (useful for dry runs and UIs)."""
    base = img.convert("L")
    paper = Image.new("RGB", (base.width + 2 * paper_margin, base.height + 2 * paper_margin), (250, 249, 245))
    tinted = ImageOps.colorize(base, black=(25, 25, 30), white=(250, 249, 245))
    paper.paste(tinted, (paper_margin, paper_margin))
    return paper


def stack(images: Sequence[Image.Image], gap: int = 0) -> Image.Image:
    """Join images vertically (all must share the same width)."""
    if not images:
        raise ValueError("nothing to stack")
    width = images[0].width
    mode = "L" if any(i.mode == "L" for i in images) else "1"
    height = sum(i.height for i in images) + gap * (len(images) - 1)
    out = Image.new(mode, (width, height), 255)
    y = 0
    for i in images:
        if i.width != width:
            raise ValueError("all images must have the same width")
        out.paste(i.convert(mode), (0, y))
        y += i.height + gap
    return out
