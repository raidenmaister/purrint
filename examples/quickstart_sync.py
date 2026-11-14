"""Blocking example: no asyncio needed.

    python examples/quickstart_sync.py photo.jpg
"""

import sys

import purrint

photo = sys.argv[1] if len(sys.argv) > 1 else None

with purrint.connect_sync("MX10") as printer:  # or connect_sync() for the nearest supported printer
    print("Connected:", printer.name, printer.family.value, "firmware", printer.info.firmware)

    if photo:
        result = printer.print_image(photo, density=4, dither="floyd", feed=16)
        print(f"Photo: {result.lines} lines, confirmed by printer: {result.confirmed}, {result.seconds:.1f}s")

    printer.print_qr("https://pypi.org/project/purrint/", caption="pip install purrint", feed=60)
    print("Status:", printer.refresh_status())
