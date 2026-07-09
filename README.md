# Generador de Códigos de Barras · Code 39

Aplicación de escritorio (Python + CustomTkinter) para generar códigos de
barras **Code 39**, pensada para vincularse con números de ítem/artículo de
tu inventario. Permite condicionar el formato del código (prefijo, relleno
con ceros, sufijo) y descargar la imagen generada en PNG.

## Características

- Interfaz moderna con tema claro/oscuro/automático.
- **Formato condicionable**: `PREFIJO` + `NÚMERO DE ÍTEM` (con relleno de
  ceros opcional) + `SUFIJO` → por ejemplo `ITM-000123-A`.
- Checksum opcional (dígito de verificación mod43 de Code 39).
- Vista previa en vivo mientras escribes.
- Personalización de apariencia: ancho/alto de barras, margen, tamaño de
  texto, colores de barras y fondo.
- Descarga individual en PNG.
- **Generación por lote**: crea automáticamente un PNG por cada número de
  ítem en un rango (por ejemplo, del 1 al 500) usando el mismo formato,
  guardando todo en una carpeta.

## Instalación

Requiere Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate   # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> En Linux puede que necesites instalar Tkinter a nivel de sistema si no
> viene incluido con tu Python: `sudo apt install python3-tk`.

## Uso

```bash
python main.py
```

### Pestaña "Individual"

1. Escribe el **número de ítem** (por ejemplo `123`).
2. Opcionalmente agrega **prefijo** (`ITM-`), **sufijo** (`-A`) y define
   cuántos dígitos de **relleno con ceros** quieres (`6` → `000123`).
3. Ajusta la apariencia si lo deseas (tamaño, colores, texto legible).
4. Haz clic en **Descargar imagen (PNG)** y elige dónde guardarla.

### Pestaña "Generación por lote"

Ideal para generar de una sola vez los códigos de un rango de artículos:

1. Define el mismo formato (prefijo/relleno/sufijo).
2. Indica el **número inicial** y **número final** del rango.
3. Elige la **carpeta destino**.
4. Haz clic en **Generar lote**: se creará un archivo PNG por cada número,
   nombrado según el código resultante (por ejemplo `ITM-000123-A.png`).

## Sobre Code 39

Code 39 solo admite: letras `A-Z`, dígitos `0-9` y los símbolos
`- . espacio $ / + %`. La aplicación valida el código antes de generarlo y
avisa si contiene caracteres no soportados.

## Estructura del proyecto

```
main.py                 # Punto de entrada
src/barcode_core.py      # Lógica de generación (sin dependencias de GUI)
src/gui.py                # Interfaz gráfica (CustomTkinter)
requirements.txt
```

## Generar un ejecutable (opcional)

Para distribuir la app sin requerir Python instalado, puedes usar
[PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name "GeneradorCodigoBarras" main.py
```

El ejecutable quedará en la carpeta `dist/`.
