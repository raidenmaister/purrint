"""Frames must match byte-for-byte what real printers expect.

Expected values come from command literals used by the vendor app and from notifications captured
from a real MX10.
"""

from purrint.crc import crc8
from purrint.protocol import v5g, v5x
from purrint.protocol.frames import parse_frames
from purrint.status import PrinterState


def h(s: str) -> bytes:
    return bytes.fromhex(s)


# ------------------------------------------------------------------------------------- CRC ----
def test_crc8_known_values():
    assert crc8(v5g.LATTICE_START) == 0xA1
    assert crc8(v5g.LATTICE_END) == 0x11
    assert crc8(b"\x30\x00") == 0xF9
    assert crc8(b"\x0A") == 0x36
    assert crc8(b"\x19") == 0x4F
    assert crc8(b"\x33") == 0x99
    assert crc8(b"\x10\x27") == 0xA2
    assert crc8(b"") == 0


# ------------------------------------------------------------------------------------- V5G ----
def test_v5g_command_literals():
    assert v5g.get_state() == h("5178A30001000000FF")
    assert v5g.get_device_info() == h("5178A80001000000FF")
    assert v5g.get_serial() == h("5178BB0001000107FF")
    assert v5g.feed(0x30) == h("5178A10002003000F9FF")
    assert v5g.set_speed(0x0A) == h("5178BD0001000A36FF")
    assert v5g.set_speed(0x19) == h("5178BD000100194FFF")
    assert v5g.set_energy(10000) == h("5178AF0002001027A2FF")
    assert v5g.set_mode(0) == h("5178BE0001000000FF")
    assert v5g.set_quality(1) == h("5178A400010031" "97FF")
    assert v5g.set_quality(4) == h("5178A4000100348CFF")
    assert v5g.lattice_start() == h("5178A6000B00AA551738445F5F5F44382CA1FF")
    assert v5g.lattice_end() == h("5178A6000B00AA5517000000000000001711FF")


def test_v5g_line_frame():
    row = bytes(range(48))
    f = v5g.line(row)
    assert f[:6] == h("5178A2003000")
    assert f[6:54] == row
    assert f[54] == crc8(row) and f[55] == 0xFF


def test_v5g_job_structure():
    rows = [b"\xff" * 48, b"\x00" * 48]
    job = v5g.build_job(rows, v5g.JobSettings(energy=12000, density_value=120, feed_lines=48))
    frames, rest = parse_frames(v5g.MAGIC, job)
    assert rest == b""
    cmds = [f.command for f in frames]
    assert cmds == [0xF2, 0xA3, 0xA4, 0xA6, 0xAF, 0xBE, 0xBD, 0xA2, 0xA2, 0xBD, 0xA1, 0xA6, 0xA3]
    assert all(f.crc_ok for f in frames)
    assert frames[4].payload == (12000).to_bytes(2, "little")


def test_v5g_energy_levels():
    assert v5g.energy_for_level(4) == 12000
    assert v5g.energy_for_level(1) == 5000
    assert v5g.energy_for_level(99) == 20000


def test_v5g_notifications_from_real_mx10():
    stream = h(
        "5178A30103000000358BFF"   # idle
        "5178A8010A00510000312E302E313100A9FF"  # firmware 1.0.11
        "5178BB010600BA724D91C12889FF"  # device id
        "5178A301030080003689FF"   # printing
        "5178D301010023E9FF"       # 35 °C
        "5178AE0101001070FF"       # buffer full
        "5178AE0101000000FF"       # buffer free
    )
    notices, rest = v5g.decode_stream(stream)
    assert rest == b""
    kinds = [n.kind for n in notices]
    assert kinds == ["status", "firmware", "serial", "status", "temperature", "buffer_full", "buffer_free"]
    assert notices[0].status.state is PrinterState.IDLE and notices[0].status.ok
    assert notices[1].text == "1.0.11"
    assert notices[2].text == "BA724D91C128"
    assert notices[3].status.state is PrinterState.PRINTING
    assert notices[4].temperature_c == 35


def test_v5g_status_flags():
    st = v5g.decode_state(0x01, b"\x01")
    assert st.out_of_paper and not st.ok
    st = v5g.decode_state(0x04, b"\x04")
    assert st.overheated
    st = v5g.decode_state(0x08, b"\x08")
    assert st.low_battery
    st = v5g.decode_state(0x09, b"\x09")
    assert st.out_of_paper and st.low_battery
    assert v5g.decode_state(0xD2, b"\xd2").overheated


def test_v5g_split_notifications():
    data = h("5178A30103000000358BFF")
    notices, rest = v5g.decode_stream(data[:5])
    assert notices == [] and rest == data[:5]
    notices, rest = v5g.decode_stream(data[5:], rest)
    assert [n.kind for n in notices] == ["status"] and rest == b""


# ------------------------------------------------------------------------------------- V5X ----
def test_v5x_command_literals():
    assert v5x.get_status() == h("2221A10001000000FF")
    assert v5x.get_version() == h("2221B10001000000FF")
    assert v5x.feed(4) == h("2221A3000200040054FF")
    assert v5x.feed(9) == h("2221A30002000900BDFF")
    assert v5x.cancel() == h("2221AC0001000000FF")
    assert v5x.flush() == h("2221AD0001000000FF")


def test_v5x_print_request():
    f = v5x.print_request(683, v5x.MODE_DOT)
    assert f[:6] == h("2221A9000400")
    assert f[6:10] == bytes((683 & 0xFF, 683 >> 8, 0x30, 0x00))
    assert f[10] == crc8(f[6:10]) and f[11] == 0xFF
    assert v5x.print_request(10, v5x.MODE_GRAY)[9] == 0x02


def test_v5x_bitmap_padding():
    rows = [b"\x01" * 48] * 10
    payload = v5x.bitmap_payload(rows, 384)
    assert len(payload) == 48 * v5x.MIN_LINES
    assert payload[:48] == b"\x01" * 48 and payload[-48:] == b"\x00" * 48
    gray = v5x.bitmap_payload([b"\xff" * 192] * 100, 384, gray=True)
    assert len(gray) == 192 * 100


def test_v5x_status_decode():
    # state=printing, battery 80, temperature 36, flag set, error 0x01 (no paper)
    payload = bytes((0x01, 0, 0, 80, 36, 0, 0x01, 0x01, 0))
    st = v5x.decode_status(payload)
    assert st.state is PrinterState.PRINTING
    assert st.battery_percent == 80 and st.temperature_c == 36
    assert st.out_of_paper
    ok = v5x.decode_status(bytes((0, 0, 0, 95, 30, 0, 0, 0, 0)))
    assert ok.ok and ok.state is PrinterState.IDLE


def test_v5x_notifications():
    frames = (
        v5x.frame(v5x.CMD_PRINT, b"\x00")
        + v5x.frame(v5x.CMD_PRINT_DONE, b"\x00")
        + v5x.frame(v5x.CMD_VERSION, b"1.9.3.1.2\x00\x02")
        + v5x.frame(v5x.CMD_HEAD_TYPE, b"\x01")
    )
    notices, rest = v5x.decode_stream(frames)
    assert [n.kind for n in notices] == ["print_ack", "print_done", "version", "head_type"]
    assert notices[0].ok is True
    assert notices[2].text == "1.9.3.1.2"
    assert v5x.head_type_from_version(notices[2].text) == "high_voltage"
    assert notices[3].text == "high_voltage"
