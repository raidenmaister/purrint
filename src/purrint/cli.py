"""Command line interface: ``purrint --help``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import List, Optional

from . import __version__
from .catalog import Family, all_models
from .exceptions import PurrintError
from .imaging import DITHER_METHODS, preview
from .progress import PrintProgress


def _bar(p: PrintProgress) -> None:
    width = 28
    filled = int(p.printed * width)
    copy = f" copy {p.copy}/{p.copies}" if p.copies > 1 else ""
    sys.stderr.write(
        f"\r  [{'#' * filled}{'.' * (width - filled)}] {int(p.printed * 100):3d}% "
        f"{p.phase:<8} line {p.current_line}/{p.lines}{copy}   "
    )
    if p.phase == "done":
        sys.stderr.write("\n")
    sys.stderr.flush()


def _add_printer_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("-p", "--printer", help="printer name fragment or Bluetooth address (default: nearest supported)")
    p.add_argument("--model", help="force a catalog model, e.g. MX10")
    p.add_argument("--family", choices=["V5G", "V5X"], help="force the protocol for unknown devices")
    p.add_argument("--simulate", metavar="PNG", help="do not use Bluetooth; save what would be printed to PNG")


def _add_job_args(p: argparse.ArgumentParser, image: bool = True) -> None:
    p.add_argument("-d", "--density", type=int, default=4, help="darkness 1 (light) .. 7 (darkest), default 4")
    p.add_argument("--energy", type=int, help="raw head energy for V5G printers (≈5000..20000)")
    p.add_argument("--intensity", type=int, help="raw intensity for V5X printers (0..100)")
    p.add_argument("--feed", type=int, help="paper feed after the job, in dot rows (8 = 1 mm)")
    p.add_argument("-n", "--copies", type=int, default=1)
    p.add_argument("--no-wait", action="store_true", help="return once data is sent")
    if image:
        p.add_argument("--dither", choices=DITHER_METHODS, default="floyd")
        p.add_argument("--rotate", default="auto", help="auto (landscape -> portrait), 0, 90, 180 or 270")
        p.add_argument("--brightness", type=int, default=0, help="-100..100")
        p.add_argument("--contrast", type=int, default=0, help="-100..100")
        p.add_argument("--gamma", type=float, default=1.0)
        p.add_argument("--sharpen", action="store_true")
        p.add_argument("--invert", action="store_true")
        p.add_argument("--autocontrast", action="store_true")
        p.add_argument("--gray", action="store_true", help="16-level grayscale (V5X printers)")
        p.add_argument("--cooldown", type=float, default=3.0, help="seconds between pictures/copies")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="purrint", description="Print on Bluetooth thermal 'cat' printers.")
    ap.add_argument("--version", action="version", version=f"purrint {__version__}")
    ap.add_argument("-v", "--verbose", action="count", default=0, help="-v info, -vv protocol debug")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="list printers in range")
    s.add_argument("-t", "--timeout", type=float, default=6.0)
    s.add_argument("-a", "--all", action="store_true", help="show every named BLE device")

    m = sub.add_parser("models", help="list supported model names")
    m.add_argument("--family", choices=["V5G", "V5X"])

    i = sub.add_parser("info", help="connect and show firmware, status and settings")
    _add_printer_args(i)

    img = sub.add_parser("image", help="print one or more pictures")
    img.add_argument("files", nargs="+")
    _add_printer_args(img)
    _add_job_args(img)

    t = sub.add_parser("text", help="print text (use '-' to read stdin)")
    t.add_argument("text")
    _add_printer_args(t)
    _add_job_args(t, image=False)
    t.add_argument("-s", "--size", type=int, default=26, help="font size in dots")
    t.add_argument("--font", help="font file or name (e.g. arial.ttf)")
    t.add_argument("--bold", action="store_true")
    t.add_argument("--mono", action="store_true")
    t.add_argument("--align", choices=["left", "center", "right"], default="left")
    t.add_argument("--underline", action="store_true")
    t.add_argument("--invert", action="store_true")

    q = sub.add_parser("qr", help="print a QR code (pip install purrint[qr])")
    q.add_argument("data")
    q.add_argument("--caption")
    q.add_argument("--size", type=int, help="QR side in dots")
    _add_printer_args(q)
    _add_job_args(q, image=False)

    f = sub.add_parser("feed", help="advance the paper")
    f.add_argument("lines", type=int, nargs="?", default=64)
    _add_printer_args(f)

    r = sub.add_parser("retract", help="pull the paper back (some V5G firmwares)")
    r.add_argument("lines", type=int, nargs="?", default=64)
    _add_printer_args(r)

    st = sub.add_parser("status", help="show the printer status")
    _add_printer_args(st)
    return ap


async def _connect(args: argparse.Namespace):
    from .printer import Printer
    from .simulator import connect_simulated

    if getattr(args, "simulate", None):
        return await connect_simulated(args.model or (args.printer or "MX10"))
    printer = await Printer.connect(args.printer, model=args.model, family=args.family)
    print(f"Connected to {printer.name} ({printer.family.value}, {printer.address})", file=sys.stderr)
    return printer


def _job_kwargs(args: argparse.Namespace) -> dict:
    kw = dict(density=args.density, copies=args.copies, feed=args.feed, energy=args.energy,
              intensity=args.intensity, wait=not args.no_wait, on_progress=_bar)
    return kw


async def _run(args: argparse.Namespace) -> int:
    if args.cmd == "models":
        fam = Family(args.family) if args.family else None
        for model in all_models(fam):
            flags = " (simplified UI)" if model.simplified else ""
            print(f"{model.label:<24} {model.family.value}  {model.vendor_model:<6} {model.kind.value}{flags}")
        print(f"\n{len(all_models(fam))} models")
        return 0

    if args.cmd == "scan":
        from .transport import discover

        found = await discover(args.timeout, known_only=not args.all)
        if not found:
            print("No printers found. Switch it on and disconnect it from any phone app.")
            return 1
        for p in found:
            model = f"{p.model.label} ({p.model.family.value})" if p.model else "unknown"
            print(f"{p.name:<22} {p.address:<20} rssi {str(p.rssi):>5}  {model}")
        return 0

    printer = await _connect(args)
    try:
        if args.cmd in ("info", "status"):
            info = await printer.get_info()
            status = await printer.refresh_status()
            print(f"Name        : {printer.name}")
            print(f"Model       : {printer.model.label} ({printer.model.vendor_model})")
            print(f"Protocol    : {printer.family.value}")
            print(f"Address     : {printer.address}")
            print(f"Width       : {printer.width} dots")
            print(f"MTU         : {printer.mtu}")
            print(f"Firmware    : {info.firmware or '-'}")
            print(f"Serial/ID   : {info.serial or '-'}")
            if info.head_type:
                print(f"Head        : {info.head_type}")
            print(f"State       : {status.state.value}")
            print(f"Problems    : {', '.join(status.problems) or 'none'}")
            if status.battery_percent is not None:
                print(f"Battery     : {status.battery_percent}%")
            if printer.temperature is not None:
                print(f"Temperature : {printer.temperature} °C")
            return 0

        if args.cmd == "feed":
            await printer.feed(args.lines)
            return 0
        if args.cmd == "retract":
            await printer.retract(args.lines)
            return 0

        if args.cmd == "image":
            rotate = args.rotate if args.rotate == "auto" else int(args.rotate)
            for idx, path in enumerate(args.files):
                print(f"Printing {path}", file=sys.stderr)
                await printer.print_image(
                    path, dither=args.dither, rotate=rotate, brightness=args.brightness, contrast=args.contrast,
                    gamma=args.gamma, sharpen=args.sharpen, invert=args.invert, autocontrast=args.autocontrast,
                    gray=args.gray, cooldown=args.cooldown, **_job_kwargs(args),
                )
                if idx < len(args.files) - 1 and args.cooldown:
                    await asyncio.sleep(args.cooldown)
        elif args.cmd == "text":
            text = sys.stdin.read() if args.text == "-" else args.text.replace("\\n", "\n")
            await printer.print_text(
                text, size=args.size, font=args.font, bold=args.bold, mono=args.mono, align=args.align,
                underline=args.underline, invert=args.invert, **_job_kwargs(args),
            )
        elif args.cmd == "qr":
            kw = _job_kwargs(args)
            kw.pop("copies"), kw.pop("energy"), kw.pop("intensity")
            await printer.print_qr(args.data, size=args.size, caption=args.caption, **kw)

        sim = getattr(printer, "simulator", None)
        if sim is not None and args.simulate:
            from .imaging import stack

            pages = [pg.convert("L") for pg in sim.pages]
            if pages:
                preview(stack(pages, gap=16)).save(args.simulate)
                print(f"Saved preview to {args.simulate}", file=sys.stderr)
        return 0
    finally:
        await printer.disconnect()


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    level = logging.WARNING if not args.verbose else logging.INFO if args.verbose == 1 else logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    try:
        return asyncio.run(_run(args))
    except PurrintError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
