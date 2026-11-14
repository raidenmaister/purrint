"""Async example with live progress, status events and several kinds of content.

    python examples/quickstart_async.py photo.jpg
"""

import asyncio
import sys

import purrint


def show(progress: purrint.PrintProgress) -> None:
    print(f"\r{progress.phase:<9} line {progress.current_line:>4}/{progress.lines}", end="", flush=True)
    if progress.phase == "done":
        print()


async def main() -> None:
    # 1. Find printers (optional: connect() alone picks the nearest supported one)
    for found in await purrint.scan(timeout=5):
        print("found:", found)

    async with await purrint.connect() as printer:
        printer.on(lambda kind, payload: kind == "temperature" and print(f"\nhead at {payload} °C"))
        print("connected to", printer, "firmware", printer.info.firmware)

        await printer.print_text("purrint", size=56, bold=True, align="center", feed=0)
        await printer.print_separator("dashed")
        await printer.print_text("Receipt #42\nCoffee ........ 2.50\nCake .......... 3.20", mono=True, feed=0)
        await printer.print_separator("solid")

        if len(sys.argv) > 1:
            await printer.print_image(sys.argv[1], dither="atkinson", density=5, on_progress=show)

        await printer.print_qr("https://pypi.org/project/purrint/", caption="scan me", on_progress=show)
        print("status:", await printer.refresh_status())


asyncio.run(main())
