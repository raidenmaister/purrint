# Virtual Hardware Simulator

`purrint` includes an in-memory hardware simulator (`SimulatedTransport`) that emulates both the V5G and V5X firmware state machines. It allows developers to build, test, and render layout previews without needing physical hardware or Bluetooth permissions.

---

## Interactive Simulation

Connect to the virtual simulator using `connect_simulated(model_name)`:

=== "Asynchronous"

    ```python
    import asyncio
    import purrint

    async def main():
        # Emulates an MX10 printer
        printer = await purrint.connect_simulated("MX10")

        # Run ordinary print calls
        await printer.print_text("Virtual simulation test", size=32)
        await printer.print_image("photo.jpg")

        # Inspect simulated printer paper output
        pages = printer.simulator.pages
        print(f"Rendered {len(pages)} page(s)")

        # Save simulated output to disk
        pages[-1].save("simulation_output.png")

        await printer.disconnect()

    asyncio.run(main())
    ```

=== "Synchronous"

    ```python
    from purrint.simulator import connect_simulated
    from purrint.sync import SyncPrinter, _run

    # Wrap simulated printer in synchronous facade
    printer = SyncPrinter(_run(connect_simulated("MX10")))
    printer.print_text("Testing synchronous API")

    # Access rendered page
    last_page = printer.simulator.pages[-1]
    last_page.save("mock_receipt.png")

    printer.disconnect()
    ```

---

## Simulating Error Conditions

You can test how your application responds to hardware failures by simulating out-of-paper conditions or temperature alerts:

```python
import pytest
import purrint

# Create a simulator with empty paper tray
printer = await purrint.connect_simulated("MX10", paper=False)

try:
    await printer.print_text("This should fail")
except purrint.OutOfPaperError:
    print("Caught expected out-of-paper hardware exception.")
```

---

## CLI Simulation

The command line interface supports generating `.png` previews directly with `--simulate`:

```bash
purrint text "Test layout" --bold --simulate output_preview.png
purrint image photo.jpg --dither atkinson --simulate photo_preview.png
```
