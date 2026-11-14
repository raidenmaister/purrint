"""No printer? Use the built-in simulator and save exactly what would be printed.

    python examples/preview_without_printer.py photo.jpg
"""

import asyncio
import sys

import purrint


async def main() -> None:
    for model in ("MX10", "MXW01"):  # one printer of each protocol family
        printer = await purrint.connect_simulated(model)
        await printer.print_text(f"Simulated {model}", size=32, align="center")
        if len(sys.argv) > 1:
            await printer.print_image(sys.argv[1], gray=printer.model.supports_gray)
        pages = [page.convert("L") for page in printer.simulator.pages]
        purrint.preview(purrint.stack(pages, gap=12)).save(f"preview_{model}.png")
        print(f"saved preview_{model}.png ({len(pages)} jobs)")


asyncio.run(main())
