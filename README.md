# Generador de Códigos de Barras · Code 39

Aplicación de escritorio (Python + CustomTkinter) para generar códigos de
barras **Code 39**, pensada para vincularse con números de ítem/artículo de
tu inventario. Permite condicionar el formato del código (prefijo, relleno
con ceros, sufijo) y descargar la imagen generada en PNG.

<img width="3839" height="1995" alt="image" src="https://github.com/user-attachments/assets/8153a7e4-b349-4e52-8528-356cfb8d606b" />


## 📥 Descargar el ejecutable (sin instalar Python)

[![Descargar v1.1.2](https://img.shields.io/badge/descargar-v1.1.2-2ea44f?style=for-the-badge)](https://github.com/rcorzogutierrez/couponbarprice/releases/latest)
[![Licencia MIT](https://img.shields.io/badge/licencia-MIT-blue?style=for-the-badge)](LICENSE)

No necesitas tener Python instalado para usar la app. Descarga el
ejecutable listo para tu sistema operativo:

| Sistema | Descarga |
|---|---|
| 🪟 Windows | [`GeneradorCodigoBarras-Windows.zip`](https://github.com/rcorzogutierrez/couponbarprice/releases/download/v1.1.2/GeneradorCodigoBarras-Windows.zip) → contiene `GeneradorCodigoBarras.exe` |
| 🍎 macOS | [`GeneradorCodigoBarras-macOS.zip`](https://github.com/rcorzogutierrez/couponbarprice/releases/download/v1.1.2/GeneradorCodigoBarras-macOS.zip) → contiene `GeneradorCodigoBarras.app` |

Descomprime el `.zip` descargado y ejecuta el programa directamente; no
requiere instalación ni Python.

En macOS, al no estar la app firmada/notarizada, la primera vez que la
abras debes hacer clic derecho → **Abrir** (o permitirlo en Preferencias
del Sistema → Privacidad y seguridad).

En Windows, como el `.exe` tampoco está firmado con un certificado de
código, es normal que aparezca el aviso **"Windows protected your PC"**
(SmartScreen) la primera vez. Haz clic en **More info → Run anyway** para
continuar.

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
  ítem, ya sea de un rango (por ejemplo, del 1 al 500) o cargando un
  archivo `.txt`/`.csv` con números no consecutivos, usando el mismo
  formato y guardando todo en una carpeta.

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

Ideal para generar de una sola vez los códigos de varios artículos. Define
el mismo formato (prefijo/relleno/sufijo) y elige de dónde salen los
números de ítem, con dos modos intercambiables:

- **Rango**: indica el **número inicial** y **número final** (ej. `1` a
  `50`) y se genera un código consecutivo por cada número del rango.
- **Archivo**: haz clic en **Cargar archivo (.txt / .csv)...** y selecciona
  un archivo con tus números de ítem. Útil cuando los números no son
  consecutivos (por ejemplo, un export de tu sistema de inventario).
  - Si el archivo tiene una sola columna (un número por línea, o
    varios separados por comas), se cargan directamente.
  - Si tiene **varias columnas** (un CSV con más campos, como
    `sku,descripción,precio`), se abre un diálogo para elegir cuál
    columna contiene los números de ítem, con vista previa de los datos
    y la opción de indicar si la primera fila es un encabezado.

Luego, en ambos modos:

1. Elige la **carpeta destino**.
2. Haz clic en **Generar lote**: se creará un archivo PNG por cada número,
   nombrado según el código resultante (por ejemplo `ITM-000123-A.png`).
3. Al terminar, se pregunta si deseas abrir la carpeta destino; también
   puedes abrirla en cualquier momento con el botón **Abrir carpeta
   destino**.

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

## Redistribuibles para Windows y macOS (sin Python)

El repositorio incluye un workflow de GitHub Actions
(`.github/workflows/build.yml`) que genera automáticamente ejecutables
standalone para **Windows** y **macOS** usando runners nativos de cada
sistema operativo (no requiere Python en las máquinas de destino).

### Descargar un build ya generado

1. Ve a la pestaña **Actions** del repositorio → workflow **"Build desktop
   app"**.
2. Si no hay una ejecución reciente, dispárala manualmente con **Run
   workflow**.
3. Cuando termine, descarga los artefactos `GeneradorCodigoBarras-Windows`
   (contiene `GeneradorCodigoBarras.exe`) y `GeneradorCodigoBarras-macOS`
   (contiene `GeneradorCodigoBarras.app`).

### Publicar una release con los binarios adjuntos

Al crear y subir un tag con formato `vX.Y.Z` (ej. `git tag v1.0.0 && git push
origin v1.0.0`), el workflow compila ambos binarios y los adjunta
automáticamente a una GitHub Release, que quedará disponible en la sección
de [Descargas](#-descargar-el-ejecutable-sin-instalar-python) de este README.

### Compilar localmente (opcional)

```bash
pip install -r requirements-build.txt
pyinstaller --noconfirm --windowed --onefile \
  --name "GeneradorCodigoBarras" \
  --collect-all customtkinter \
  --collect-all barcode \
  --hidden-import "PIL._tkinter_finder" \
  main.py
```

El resultado queda en `dist/` (`.exe` en Windows, `.app` en macOS, binario
suelto en Linux). Los flags `--collect-all` son necesarios porque
CustomTkinter y python-barcode cargan temas/fuentes como archivos de datos
en tiempo de ejecución, y `PIL._tkinter_finder` es un import oculto que
`Pillow` necesita para mostrar imágenes en Tkinter.

## Licencia

Este proyecto está bajo la licencia [MIT](LICENSE).
