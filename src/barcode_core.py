"""Lógica de generación de códigos de barras Code 39.

Este módulo no depende de la interfaz gráfica: recibe parámetros simples
(strings, números, dataclasses) y devuelve imágenes PIL o las guarda en
disco. Así se puede probar y reutilizar de forma independiente de Tkinter.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from barcode.codex import Code39
from barcode.writer import ImageWriter
from PIL import Image

# Conjunto de caracteres soportados por Code 39 (sin el asterisco de inicio/fin,
# que la librería agrega automáticamente).
CODE39_VALID_CHARS = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-. $/+%")


class InvalidCode39CharacterError(ValueError):
    """Se lanza cuando el código contiene caracteres no soportados por Code 39."""

    def __init__(self, invalid_chars: set[str]):
        self.invalid_chars = invalid_chars
        chars = ", ".join(repr(c) for c in sorted(invalid_chars))
        super().__init__(
            f"El código contiene caracteres no válidos para Code 39: {chars}. "
            "Solo se permiten letras A-Z, números 0-9 y - . espacio $ / + %"
        )


class EmptyCodeError(ValueError):
    """Se lanza cuando el código resultante queda vacío."""


@dataclass
class CodeFormat:
    """Define cómo se construye el texto codificado a partir de un número de ítem.

    Ejemplo: prefix="ITM-", pad_length=6, suffix="-A" con item_number="42"
    produce el código "ITM-000042-A".
    """

    prefix: str = ""
    suffix: str = ""
    pad_length: int = 0
    uppercase: bool = True

    def build(self, item_number: str) -> str:
        number = item_number.strip()
        if self.pad_length > 0 and number.isdigit():
            number = number.zfill(self.pad_length)
        code = f"{self.prefix}{number}{self.suffix}"
        return code.upper() if self.uppercase else code


@dataclass
class BarcodeStyle:
    """Opciones visuales del código de barras, mapeadas a ImageWriter de python-barcode."""

    module_width: float = 0.25
    module_height: float = 15.0
    font_size: int = 10
    text_distance: float = 5.0
    quiet_zone: float = 6.5
    write_text: bool = True
    background: str = "#FFFFFF"
    foreground: str = "#000000"
    dpi: int = 300

    def to_writer_options(self) -> dict:
        return {
            "module_width": self.module_width,
            "module_height": self.module_height,
            "font_size": self.font_size,
            "text_distance": self.text_distance,
            "quiet_zone": self.quiet_zone,
            "write_text": self.write_text,
            "background": self.background,
            "foreground": self.foreground,
            "dpi": self.dpi,
        }


def validate_code39(code: str) -> None:
    """Lanza un error descriptivo si el código no es válido para Code 39."""
    if not code:
        raise EmptyCodeError("El código resultante está vacío.")
    invalid = {c for c in code if c not in CODE39_VALID_CHARS}
    if invalid:
        raise InvalidCode39CharacterError(invalid)


def generate_barcode_image(
    code: str, style: BarcodeStyle, add_checksum: bool = False
) -> tuple[Image.Image, str]:
    """Genera la imagen del código de barras.

    Devuelve una tupla (imagen, texto_final) donde texto_final incluye el
    dígito de checksum si add_checksum=True, ya que ese es el texto que
    realmente queda codificado en las barras.
    """
    validate_code39(code)
    barcode_obj = Code39(code, writer=ImageWriter(), add_checksum=add_checksum)
    buffer = BytesIO()
    barcode_obj.write(buffer, options=style.to_writer_options())
    buffer.seek(0)
    image = Image.open(buffer).convert("RGB")
    return image, barcode_obj.code


def save_barcode_image(image: Image.Image, path: Path) -> None:
    """Guarda la imagen generada como PNG (u otro formato según la extensión)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def sanitize_filename(code: str) -> str:
    """Convierte un código en un nombre de archivo seguro para el sistema operativo."""
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in code)
    return safe or "codigo_barras"


def iter_item_numbers(start: int, end: int) -> range:
    """Genera el rango inclusivo de números de ítem para un lote."""
    if end < start:
        start, end = end, start
    return range(start, end + 1)


def read_table_rows(path: Path) -> list[list[str]]:
    """Lee un archivo .txt/.csv como filas de celdas separadas por coma.

    Un .txt con un número por línea produce filas de una sola celda. Las
    filas totalmente vacías se descartan.
    """
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = [[cell.strip() for cell in row] for row in reader]
    return [row for row in rows if any(cell for cell in row)]


def flatten_single_column(rows: list[list[str]]) -> list[str]:
    """Junta en una sola lista todas las celdas no vacías de un archivo de una columna."""
    return [cell for row in rows for cell in row if cell]


def extract_column(rows: list[list[str]], column_index: int, has_header: bool) -> list[str]:
    """Extrae los valores no vacíos de una columna específica."""
    data_rows = rows[1:] if has_header else rows
    values: list[str] = []
    for row in data_rows:
        if column_index < len(row) and row[column_index]:
            values.append(row[column_index])
    return values
