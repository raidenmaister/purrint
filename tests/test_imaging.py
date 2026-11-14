import io

import pytest
from PIL import Image

from purrint.imaging import _pixels as px

from purrint import ImageOptions, prepare, render_separator, render_text, stack
from purrint.imaging import DITHER_METHODS, dither, pack_1bpp, pack_4bpp


def test_pack_1bpp_left_dot_is_bit0():
    img = Image.new("1", (16, 1), 1)
    img.putpixel((0, 0), 0)
    img.putpixel((9, 0), 0)
    rows = pack_1bpp(img)
    assert rows == [bytes((0b00000001, 0b00000010))]


def test_pack_4bpp_left_dot_high_nibble():
    img = Image.new("L", (4, 1), 255)
    img.putpixel((0, 0), 0)    # black -> 15
    img.putpixel((3, 0), 136)  # mid gray -> 7
    rows = pack_4bpp(img)
    assert rows == [bytes((0xF0, 0x07))]


def _landscape() -> Image.Image:
    img = Image.new("RGB", (800, 400), "white")
    img.paste((0, 0, 0), (0, 0, 400, 400))
    return img


def test_auto_rotate_landscape_uses_paper_length():
    out = prepare(_landscape(), 384)
    assert out.mode == "1"
    assert out.size == (384, 768)


def test_no_rotate_keeps_landscape():
    out = prepare(_landscape(), 384, ImageOptions(rotate=0))
    assert out.size == (384, 192)


def test_exif_orientation_is_respected():
    img = Image.new("RGB", (200, 100), "white")
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 CW when displaying
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    out = prepare(buf.getvalue(), 384, ImageOptions(rotate=0))
    assert out.size == (384, 768)  # displayed as portrait 100x200


def test_transparency_becomes_white():
    img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    out = prepare(img, 16, ImageOptions(rotate=0, dither="threshold"))
    assert all(v == 255 for v in px(out))


@pytest.mark.parametrize("method", DITHER_METHODS)
def test_all_dither_methods(method):
    grad = Image.linear_gradient("L").resize((64, 64))
    out = dither(grad, method)
    assert out.mode == "1" and out.size == (64, 64)
    data = list(px(out))
    assert 0 in data and 255 in data


def test_gray_mode_has_16_levels():
    grad = Image.linear_gradient("L").resize((384, 64))
    out = prepare(grad, 384, ImageOptions(rotate=0), gray=True)
    assert out.mode == "L"
    assert set(px(out)) <= {i * 17 for i in range(16)}


def test_render_text_wraps_to_width():
    img = render_text("hello " * 40, 384, size=24)
    assert img.mode == "1" and img.width == 384
    assert img.height > 60
    assert 0 in set(px(img))


def test_render_text_alignment_and_newlines():
    img = render_text("a\nb\nc", 384, size=20, align="center")
    single = render_text("a", 384, size=20)
    assert img.height > 2 * single.height
    with pytest.raises(ValueError):
        render_text("x", align="justify")


def test_separator_and_stack():
    a = render_separator(384)
    b = render_text("x", 384)
    s = stack([a, b], gap=4)
    assert s.width == 384 and s.height == a.height + b.height + 4


def test_qr_optional():
    pytest.importorskip("qrcode")
    from purrint import render_qr

    img = render_qr("https://example.com", 384, caption="example")
    assert img.width == 384 and img.mode == "1"
