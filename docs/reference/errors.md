# Status and Exceptions Reference

## Exceptions Hierarchy

All library-specific exceptions derive from `purrint.exceptions.PurrintError`.

::: purrint.exceptions.PurrintError
    options:
      show_root_heading: true

::: purrint.exceptions.PrinterNotFoundError
    options:
      show_root_heading: true

::: purrint.exceptions.OutOfPaperError
    options:
      show_root_heading: true

::: purrint.exceptions.OverheatError
    options:
      show_root_heading: true

::: purrint.exceptions.ConnectionFailedError
    options:
      show_root_heading: true

::: purrint.exceptions.NotConnectedError
    options:
      show_root_heading: true

---

## Status and Telemetry Data

::: purrint.status.PrinterStatus
    options:
      show_root_heading: true

::: purrint.status.DeviceInfo
    options:
      show_root_heading: true
