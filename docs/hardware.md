# Hardware Compatibility and Protocols

`purrint` supports 107 distinct thermal printer model names advertised over Bluetooth Low Energy. These models fall into two primary protocol families.

---

## Protocol Comparison

| Characteristic | V5G Protocol Family | V5X Protocol Family (MXW01 Board) |
|---|---|---|
| **Magic Header** | `0x51 0x78` | `0x22 0x21` |
| **GATT Service UUID** | `0xAE30` / `0x0001` | `0xAE30` |
| **Command Channel** | `0xAE01` (write) | `0xAE01` (write) |
| **Data Channel** | `0xAE01` (interleaved) | `0xAE03` (dedicated bitmap stream) |
| **Notification Channel** | `0xAE02` | `0xAE02` |
| **Raster Transmission** | Streamed line-by-line (`0xA2` frame) | Buffered block transfer |
| **Grayscale Support** | 1-bit monochrome only | Native 4-bit (16-level grayscale) |
| **Checksum Algorithm** | CRC-8 (polynomial `0x07`) | CRC-8 (polynomial `0x07`) |

---

## 1. V5G Protocol Models (50 Models)

MX01, MX02, MX03, MX05, MX06, MINI PRINTER, JL-BR22, MX07, MX08, MX09, URBANWORX KIDS CAMERA, CYLO BT PRINTER, MXTP-100, AZ-P2108X, MX10, MX11, MX12, PD01, MINISO-M1, LP212, XO POPPY, MX13, BQ01, BQ02, EWTTO ET-Z0499, BQ05, BQ06, BQ07, BQ7A, BQ7B, BQ08, BQ95, BQ96, MXW009, MXW010, EWTTO ET-N3689, EWTTO ET-N3687, MXPC-100, GV-MA211, KP-IM606, BQ95B, BQ03, BQ95C, BQ06B, X6, K06, BQ17, IM.17, C18, MINISO-M12.

---

## 2. V5X / MXW01 Mainboard Models (57 Models)

MXW01, X1, X2, C17, MXW-W5, MXW01-1, Portable Printer, Instant Print Plus, REKA, HDMDT-00, JK01, BH03, BHSZY, PD03, FLYINGTIGER097, LP215, KERUI, AI01, M8HZ, HZ-M8, Q15, M13, Q15A, Q15B, Q15C, Q15D, Q15E, Q15Z, STICKERMATE, Q17, MXW13, MXW18, ADQ19, QD01, JME13, JME15, LP28AI, BQTLY, STERENIA-PRINT, LEAPOM, IHEARTYARD, ELECOUTEK, Q25SZY, TCM747736, P4, RS6301985, M13SZY, TK914, TK894, D20, Q20, Q16SZY, OHELLAATP01, Q5, Q6, JME05, Q10.

---

## Unknown or Unlisted Hardware Clones

If your printer advertises a Bluetooth name not listed above, `purrint` can automatically probe both protocol handshakes:

```python
import purrint

# Auto-probes protocol response
printer = await purrint.connect()

# Or explicitly force a protocol family:
printer_v5g = await purrint.connect(family="V5G")
printer_v5x = await purrint.connect(family="V5X")
```
