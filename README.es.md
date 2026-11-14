<p align="right">
  <a href="https://github.com/raidenmaister/purrint/blob/main/README.md"><img src="https://img.shields.io/badge/Language-%F0%9F%87%BA%F0%9F%87%B8%20English-blue?style=flat-square" alt="English"></a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/raidenmaister/purrint/main/docs/logo.svg" alt="purrint logo" width="360">
</p>

<h3 align="center">
  Controlador y CLI en Python para Impresoras Térmicas Bluetooth
</h3>

<p align="center">
  <a href="https://raidenmaister.github.io/purrint/"><img src="https://img.shields.io/badge/documentaci%C3%B3n-GitHub_Pages-blue.svg" alt="Documentación"></a>
  <a href="https://pypi.org/project/purrint/"><img src="https://img.shields.io/pypi/v/purrint.svg" alt="Versión de PyPI"></a>
  <a href="https://pypi.org/project/purrint/"><img src="https://img.shields.io/pypi/pyversions/purrint.svg" alt="Versiones de Python"></a>
  <a href="https://github.com/raidenmaister/purrint/actions/workflows/test.yml"><img src="https://github.com/raidenmaister/purrint/actions/workflows/test.yml/badge.svg" alt="Estado de pruebas"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/Licencia-MIT-blue.svg" alt="Licencia: MIT"></a>
  <a href="https://github.com/raidenmaister/purrint"><img src="https://img.shields.io/badge/tipos-anotados-blue.svg" alt="Tipado estático"></a>
</p>

---

**purrint** es una librería independiente y herramienta de línea de comandos en Python para comunicarse directamente con impresoras térmicas portátiles Bluetooth Low Energy (comúnmente conocidas como impresoras de bolsillo o impresoras "gato": MX10, MX06, modelos estilo GB01, MXW01 y más de 100 variantes compatibles). Opera directamente mediante BLE sin necesidad de aplicaciones del fabricante, cuentas ni servicios en la nube.

## Instalación

```bash
pip install purrint
```

Para habilitar la generación e impresión de códigos QR, instala el paquete con el extra `qr`:

```bash
pip install "purrint[qr]"
```

## Inicio Rápido

```python
import purrint

with purrint.connect_sync() as impresora:
    impresora.print_image("foto.jpg")
    impresora.print_text("¡Hola desde Python!", size=36, align="center")
```

## Características

| Capacidad | Descripción |
|---|---|
| **Detección** | Escaneo de dispositivos cercanos, identificación de modelos por nombre Bluetooth o sondeo de protocolo en clones desconocidos. |
| **Procesamiento de Imágenes** | Orientación EXIF automática, rotación automática de fotos horizontales a 90 grados, controles de brillo/contraste/gamma, 6 algoritmos de tramado (dithering) y soporte de escala de grises de 16 niveles en hardware V5X. |
| **Renderizado de Texto** | Soporte de fuentes del sistema o archivos TrueType propios, ajuste de línea automático, alineación (izquierda/centro/derecha), negrita, subrayado, monoespaciado e inversión de color. |
| **Composición de Recibos** | Generación de códigos QR con subtítulo, separadores de línea continuos/discontinuos/punteados y componentes gráficos combinables en pila. |
| **Control Térmico** | Densidades predefinidas (1 a 7) adaptadas a cada modelo, control manual de energía/intensidad y velocidad de impresión configurable. |
| **Telemetría de Hardware** | Monitoreo de estado: sin papel, tapa abierta, sobrecalentamiento del cabezal, nivel de batería, versión de firmware y número de serie. |
| **Sincronización Real** | Estimación en tiempo real del progreso del cabezal y control de flujo para esperar a que el papel termine de avanzar físicamente. |
| **Gestión de Papel** | Avance en puntos o milímetros, retroceso de papel, cancelación de trabajo y múltiples copias con intervalos de enfriamiento. |
| **Simulador Integrado** | Simulador por software (`connect_simulated`) para probar flujos de desarrollo sin requerir hardware físico. |
| **Interfaces** | API asíncrona completa (`asyncio`), API síncrona bloqueante (`connect_sync`) y comando de consola (`purrint`). |

## Interfaz de Línea de Comandos (CLI)

El paquete incluye el comando `purrint`:

```bash
# Escanear impresoras en rango
purrint scan

# Listar los 107 modelos reconocidos por catálogo
purrint models

# Consultar telemetría y versión de firmware
purrint info

# Imprimir una o varias imágenes
purrint image foto.jpg vacaciones/*.jpg

# Imprimir con tramado personalizado y contraste ajustado
purrint image foto.jpg --dither atkinson --density 5 --contrast 15

# Imprimir texto con formato
purrint text "Lista de compras:\n- Leche\n- Huevos" --size 30 --bold

# Imprimir código QR con subtítulo
purrint qr https://example.com --caption "Escanear enlace"

# Avanzar papel
purrint feed 100

# Previsualizar el resultado en imagen sin impresora física
purrint text "Recibo de prueba" --simulate vista.png
```

Usa el parámetro `-p <NOMBRE_O_MAC>` para seleccionar un dispositivo concreto, y `-v` o `-vv` para depuración detallada del protocolo.

## API en Python

### API Asíncrona

```python
import asyncio
import purrint

async def main():
    async with await purrint.connect("MX10") as impresora:
        print(f"Firmware: {impresora.info.firmware}, Estado: {impresora.status}")

        await impresora.print_image(
            "foto.jpg",
            density=5,            # Densidad térmica: 1 (más claro) .. 7 (más oscuro)
            dither="floyd",       # floyd | atkinson | bayer | halftone | threshold
            rotate="auto",        # Rotar fotos apaisadas automáticamente
            contrast=10,
            copies=2,
            cooldown=5,           # Intervalo de enfriamiento en segundos entre copias
            on_progress=lambda p: print(f"{p.phase}: {p.current_line}/{p.lines}"),
        )

        await impresora.print_text("¡Gracias por su compra!", size=36, bold=True, align="center")
        await impresora.print_qr("https://example.com", caption="Sitio Web")
        await impresora.feed_mm(10)

asyncio.run(main())
```

### API Síncrona

Para scripts simples o entornos sin bucle de eventos (`asyncio`):

```python
import purrint

# El gestor de contexto maneja la conexión y desconexión automáticamente
with purrint.connect_sync() as impresora:
    impresora.print_image("foto.jpg", gray=True)
    estado = impresora.refresh_status()
    print("Estado:", estado)

# Atajos directos para impresión rápida
purrint.quick_print("foto.jpg")
purrint.quick_print(None, text="Orden #1048", size=32)
```

### Composición de Recibos y Diseños Personalizados

Permite unir varios elementos en una única imagen contigua antes de imprimir:

```python
from purrint import render_text, render_qr, render_separator, stack

ticket = stack([
    render_text("CAFÉ CENTRAL", size=48, bold=True, align="center"),
    render_separator(style="dashed"),
    render_text("Espresso ........ 2.50\nCroissant ....... 1.80", mono=True),
    render_separator(style="solid"),
    render_qr("https://example.com/pedido/1048", size=200),
])

await impresora.print_raster(ticket)
```

### Manejo de Excepciones

Todas las excepciones de la librería derivan de `purrint.PurrintError`:

```python
import purrint

try:
    with purrint.connect_sync() as impresora:
        impresora.print_text("Prueba")
except purrint.OutOfPaperError:
    print("Error: La impresora se ha quedado sin papel.")
except purrint.OverheatError:
    print("Error: El cabezal térmico está sobrecalentado. Esperando enfriamiento.")
except purrint.PrinterNotFoundError:
    print("Error: No se encontró la impresora. Verifica que esté encendida y el Bluetooth activo.")
```

## Dispositivos Compatibles

Las impresoras se identifican por el nombre con el que se anuncian por Bluetooth. No distingue mayúsculas/minúsculas y soporta sufijos aleatorios (ej. `MX10-8A3F`).

- **Familia de Protocolo V5G (50 Modelos):**  
  MX01, MX02, MX03, MX05, MX06, MINI PRINTER, JL-BR22, MX07, MX08, MX09, URBANWORX KIDS CAMERA, CYLO BT PRINTER, MXTP-100, AZ-P2108X, MX10, MX11, MX12, PD01, MINISO-M1, LP212, XO POPPY, MX13, BQ01, BQ02, EWTTO ET-Z0499, BQ05, BQ06, BQ07, BQ7A, BQ7B, BQ08, BQ95, BQ96, MXW009, MXW010, EWTTO ET-N3689, EWTTO ET-N3687, MXPC-100, GV-MA211, KP-IM606, BQ95B, BQ03, BQ95C, BQ06B, X6, K06, BQ17, IM.17, C18, MINISO-M12.

- **Familia de Protocolo V5X / Placa MXW01 (57 Modelos):**  
  MXW01, X1, X2, C17, MXW-W5, MXW01-1, Portable Printer, Instant Print Plus, REKA, HDMDT-00, JK01, BH03, BHSZY, PD03, FLYINGTIGER097, LP215, KERUI, AI01, M8HZ, HZ-M8, Q15, M13, Q15A, Q15B, Q15C, Q15D, Q15E, Q15Z, STICKERMATE, Q17, MXW13, MXW18, ADQ19, QD01, JME13, JME15, LP28AI, BQTLY, STERENIA-PRINT, LEAPOM, IHEARTYARD, ELECOUTEK, Q25SZY, TCM747736, P4, RS6301985, M13SZY, TK914, TK894, D20, Q20, Q16SZY, OHELLAATP01, Q5, Q6, JME05, Q10.

### Estado de Verificación

| Categoría | Detalle |
|---|---|
| **Verificado en Hardware Real** | **MX10** (V5G, firmware 1.0.11): Detección de dispositivos, telemetría, texto, gráficos rasterizados, códigos QR, avance de papel y sincronización de finalización probados en Windows 10. |
| **Verificado mediante Simulador** | **V5X / MXW01**: Protocolo completo (rasterizado de 1 bit y escala de grises de 4 bits, control de intensidad y telemetría) validado byte a byte contra trazas documentadas y suite de pruebas. |
| **Dependiente del Firmware** | Retroceso de papel (`retract`), detección de tapa abierta y reporte de porcentaje de batería en modelos V5G según la revisión instalada. |

## Notas de Plataforma y Conexión

- **Exclusividad de Conexión BLE:** Las impresoras Bluetooth Low Energy solo admiten una conexión activa a la vez. Desvincula o apaga el Bluetooth de tu teléfono móvil antes de conectar desde la PC.
- **Windows 10/11:** Soporte nativo sin necesidad de emparejamiento manual.
- **Linux:** Requiere BlueZ 5.55+ y permisos de Bluetooth (usuario en el grupo `bluetooth`).
- **macOS:** Requiere conceder permisos de Bluetooth a la terminal o IDE.
- **Especificaciones de Hardware:** Ancho de rollo estándar de 57 mm. El cabezal cuenta con 384 puntos (48 mm de ancho útil) a 203 DPI (8 puntos por milímetro).

## Desarrollo

```bash
git clone https://github.com/raidenmaister/purrint.git
cd purrint
python -m venv .venv
# Windows: .venv\Scripts\activate | Unix: source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Licencia

Este proyecto está distribuido bajo los términos de la [Licencia MIT](LICENSE).

Todos los nombres comerciales, marcas registradas y números de modelo son propiedad de sus respectivos dueños y se mencionan exclusivamente con fines de identificación y compatibilidad de hardware.
