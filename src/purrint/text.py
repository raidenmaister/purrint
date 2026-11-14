"""Render text (and QR codes) into printable images."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import List, Optional, Sequence, Union

from PIL import Image, ImageDraw, ImageFont

FontLike = Union[str, "os.PathLike[str]", ImageFont.FreeTypeFont, None]

_CANDIDATES_REGULAR = (
    # Windows
    "segoeui.ttf", "arial.ttf", "calibri.ttf", "tahoma.ttf",
    # Linux
    "DejaVuSans.ttf", "NotoSans-Regular.ttf", "LiberationSans-Regular.ttf", "Ubuntu-R.ttf",
    # macOS
    "Helvetica.ttc", "Arial.ttf", "SFNS.ttf",
)
_CANDIDATES_BOLD = (
    "segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahomabd.ttf",
    "DejaVuSans-Bold.ttf", "NotoSans-Bold.ttf", "LiberationSans-Bold.ttf", "Ubuntu-B.ttf",
    "Arial Bold.ttf", "Helvetica.ttc",
)
_CANDIDATES_MONO = (
    "consola.ttf", "cour.ttf", "DejaVuSansMono.ttf", "NotoSansMono-Regular.ttf",
    "LiberationMono-Regular.ttf", "Menlo.ttc", "Courier New.ttf",
)


def _font_dirs() -> List[str]:
    dirs: List[str] = []
    if sys.platform.startswith("win"):
        windir = os.environ.get("WINDIR", r"C:\Windows")
        dirs += [os.path.join(windir, "Fonts")]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(os.path.join(local, "Microsoft", "Windows", "Fonts"))
    elif sys.platform == "darwin":
        dirs += ["/System/Library/Fonts", "/System/Library/Fonts/Supplemental", "/Library/Fonts",
                 os.path.expanduser("~/Library/Fonts")]
    else:
        dirs += ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts"),
                 os.path.expanduser("~/.local/share/fonts")]
    return [d for d in dirs if os.path.isdir(d)]


@lru_cache(maxsize=None)
def _find_font_file(candidates: Sequence[str]) -> Optional[str]:
    wanted = {c.lower(): i for i, c in enumerate(candidates)}
    best: Optional[tuple] = None
    for root_dir in _font_dirs():
        for root, _, files in os.walk(root_dir):
            for f in files:
                rank = wanted.get(f.lower())
                if rank is not None and (best is None or rank < best[0]):
                    best = (rank, os.path.join(root, f))
                    if rank == 0:
                        return best[1]
    return best[1] if best else None


@lru_cache(maxsize=64)
def _load(path: Optional[str], size: int) -> ImageFont.FreeTypeFont:
    if path:
        return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1 ships a scalable default
    except TypeError:  # pragma: no cover - very old Pillow
        return ImageFont.load_default()  # type: ignore[return-value]


def get_font(font: FontLike = None, size: int = 26, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    """Resolve a font: a path/name of a .ttf/.otf/.ttc, an already loaded font, or ``None`` for a
    sensible system font (falls back to Pillow's built-in font)."""
    if isinstance(font, ImageFont.FreeTypeFont):
        return font
    if font is not None:
        name = os.fspath(font)
        if os.path.isfile(name):
            return _load(name, size)
        found = _find_font_file((name,)) or _find_font_file((name + ".ttf",))
        if not found:
            raise FileNotFoundError(f"font {name!r} not found")
        return _load(found, size)
    candidates = _CANDIDATES_MONO if mono else (_CANDIDATES_BOLD if bold else _CANDIDATES_REGULAR)
    return _load(_find_font_file(candidates), size)


def _wrap(text: str, font: ImageFont.FreeTypeFont, width: int) -> List[str]:
    lines: List[str] = []
    for paragraph in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            if font.getlength(candidate) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            # Break words longer than a whole line
            while font.getlength(word) > width and len(word) > 1:
                cut = len(word)
                while cut > 1 and font.getlength(word[:cut]) > width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        lines.append(current)
    return lines


def render_text(
    text: str,
    width: int = 384,
    *,
    font: FontLike = None,
    size: int = 26,
    bold: bool = False,
    mono: bool = False,
    align: str = "left",
    line_spacing: float = 1.2,
    padding: int = 4,
    invert: bool = False,
    underline: bool = False,
) -> Image.Image:
    """Lay out ``text`` across ``width`` dots and return a mode ``"1"`` image.

    ``align`` is ``left``, ``center`` or ``right``. Long lines wrap on spaces; ``\\n`` starts a new line.
    """
    if align not in ("left", "center", "right"):
        raise ValueError("align must be 'left', 'center' or 'right'")
    f = get_font(font, size, bold=bold, mono=mono)
    inner = max(8, width - 2 * padding)
    lines = _wrap(str(text), f, inner)
    ascent, descent = f.getmetrics()
    line_h = max(1, int(round((ascent + descent) * line_spacing)))
    height = max(1, line_h * len(lines) + 2 * padding)
    img = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(img)
    fake_bold = bold and font is None and _find_font_file(_CANDIDATES_BOLD) is None
    for i, ln in enumerate(lines):
        w = f.getlength(ln)
        if align == "center":
            x = (width - w) / 2
        elif align == "right":
            x = width - padding - w
        else:
            x = padding
        y = padding + i * line_h
        draw.text((x, y), ln, font=f, fill=0)
        if fake_bold:
            draw.text((x + 1, y), ln, font=f, fill=0)
        if underline and ln:
            uy = y + ascent + max(1, size // 12)
            draw.line((x, uy, x + w, uy), fill=0, width=max(1, size // 14))
    if invert:
        img = img.point(lambda v: 255 - v)
    return img.point(lambda v: 255 if v >= 140 else 0).convert("1", dither=Image.Dither.NONE)


def render_qr(
    data: str,
    width: int = 384,
    *,
    size: Optional[int] = None,
    border: int = 2,
    error_correction: str = "M",
    caption: Optional[str] = None,
    caption_size: int = 22,
) -> Image.Image:
    """A centred QR code (requires ``pip install purrint[qr]``). ``size`` is the QR side in dots."""
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError("QR codes need the optional dependency: pip install purrint[qr]") from exc

    levels = {"L": ERROR_CORRECT_L, "M": ERROR_CORRECT_M, "Q": ERROR_CORRECT_Q, "H": ERROR_CORRECT_H}
    qr = qrcode.QRCode(error_correction=levels.get(error_correction.upper(), ERROR_CORRECT_M), border=border, box_size=1)
    qr.add_data(data)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    modules = len(matrix)
    side = min(width, size or int(width * 0.8))
    scale = max(1, side // modules)
    side = scale * modules
    code = Image.new("L", (modules, modules), 255)
    code.putdata([0 if cell else 255 for row in matrix for cell in row])
    code = code.resize((side, side), Image.Resampling.NEAREST)
    canvas = Image.new("L", (width, side), 255)
    canvas.paste(code, ((width - side) // 2, 0))
    out = canvas.convert("1", dither=Image.Dither.NONE)
    if caption:
        from .imaging import stack

        out = stack([out, render_text(caption, width, size=caption_size, align="center")])
    return out


def render_separator(width: int = 384, height: int = 12, style: str = "dashed") -> Image.Image:
    """A horizontal rule: ``solid``, ``dashed`` or ``dotted``."""
    img = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(img)
    y = height // 2
    if style == "solid":
        draw.line((0, y, width, y), fill=0, width=2)
    else:
        step, dash = (12, 7) if style == "dashed" else (6, 2)
        for x in range(0, width, step):
            draw.line((x, y, min(width, x + dash), y), fill=0, width=2)
    return img.convert("1", dither=Image.Dither.NONE)
