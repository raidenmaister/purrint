"""End-to-end tests against the simulated printer (both protocol families)."""

import asyncio

import pytest
from PIL import Image

from purrint.imaging import _pixels as px

import purrint
from purrint import Family, OutOfPaperError, connect_simulated
from purrint.imaging import pack_1bpp
from purrint.printer import Printer
from purrint.simulator import SimulatedTransport
from purrint.catalog import get_model


def run(coro):
    return asyncio.run(coro)


def _photo() -> Image.Image:
    img = Image.linear_gradient("L").resize((300, 500))
    return img.convert("RGB")


def test_v5g_roundtrip_matches_raster():
    async def go():
        p = await connect_simulated("MX10")
        assert p.family is Family.V5G
        assert p.info.firmware == "1.0.11"
        expected = p.render(_photo())
        result = await p.print_image(_photo())
        page = p.simulator.pages[-1]
        assert page.size == expected.size == (384, 640)
        assert pack_1bpp(page) == pack_1bpp(expected)
        assert result.confirmed and result.lines == 640
        assert p.temperature == 31
        await p.disconnect()

    run(go())


def test_v5x_dot_and_gray():
    async def go():
        p = await connect_simulated("MXW01")
        assert p.family is Family.V5X
        assert p.info.head_type == "high_voltage"
        await p.print_text("hola", size=30)
        dot = p.simulator.pages[-1]
        assert dot.height >= 90 and 0 in set(px(dot))
        r = await p.print_image(_photo(), gray=True)
        assert r.confirmed
        gray = p.simulator.pages[-1]
        assert len(set(px(gray))) > 4  # real grayscale reached the printer
        intensity = p.simulator.settings[0xA2][0]
        assert 75 <= intensity <= 100

    run(go())


def test_density_and_energy_overrides():
    async def go():
        p = await connect_simulated("MX06")
        await p.print_text("x", density=7)
        assert p.simulator.settings[0xAF] == (20000).to_bytes(2, "little")
        assert p.simulator.settings[0xF2] == bytes((1, 150))  # MX06 text "high"
        await p.print_text("x", energy=9000)
        assert p.simulator.settings[0xAF] == (9000).to_bytes(2, "little")

    run(go())


def test_out_of_paper_is_reported():
    async def go():
        p = await connect_simulated("MX10", paper=False)
        with pytest.raises(OutOfPaperError):
            await p.print_text("no paper")
        p2 = await connect_simulated("MXW01", paper=False)
        with pytest.raises(OutOfPaperError):
            await p2.print_text("no paper")

    run(go())


def test_copies_and_progress():
    async def go():
        p = await connect_simulated("MX10", seconds_per_line=0.0005)
        seen = []
        await p.print_text("copies", copies=2, on_progress=seen.append)
        assert len(p.simulator.pages) == 2
        assert seen[-1].phase == "done" and seen[-1].copy == 2
        assert any(s.phase in ("sending", "printing", "feeding") for s in seen)

    run(go())


def test_unknown_device_is_probed():
    async def go():
        model = get_model("MXW01")
        t = SimulatedTransport(model)
        p = await Printer._from_transport(t, None, "WeirdName")
        assert p.family is Family.V5X
        assert p.model.name == "WEIRDNAME"

    run(go())


def test_feed_and_status():
    async def go():
        p = await connect_simulated("MX10")
        await p.feed(80)
        assert (0xA1, (80).to_bytes(2, "little")) in p.simulator.commands
        st = await p.refresh_status()
        assert st.ok
        info = await p.get_info()
        assert info.serial == "BA724D91C128"

    run(go())


def test_narrow_raster_is_centered():
    async def go():
        p = await connect_simulated("MX10")
        img = Image.new("1", (100, 20), 0)
        await p.print_raster(img)
        page = p.simulator.pages[-1]
        assert page.size == (384, 20)
        assert page.getpixel((0, 0)) == 255 and page.getpixel((192, 10)) == 0

    run(go())


def test_sync_api_with_simulator():
    from purrint.sync import SyncPrinter, _run

    sp = SyncPrinter(_run(connect_simulated("MX10")))
    result = sp.print_text("sync works")
    assert result.confirmed
    assert sp.refresh_status().ok
    sp.disconnect()


def test_public_api_exports():
    for name in purrint.__all__:
        assert hasattr(purrint, name), name
