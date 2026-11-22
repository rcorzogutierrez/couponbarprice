"""Interfaz gráfica del generador de códigos de barras Code 39.

Construida con CustomTkinter para lograr un aspecto moderno (tema claro/oscuro,
esquinas redondeadas, tipografía cuidada) sin salir del ecosistema estándar de
Python (Tkinter), por lo que no requiere runtimes adicionales para distribuirse.
"""

from __future__ import annotations

import os
import platform
import queue
import subprocess
import threading
import tkinter as tk
import tkinter.colorchooser as colorchooser
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from src.barcode_core import (
    BarcodeStyle,
    CodeFormat,
    EmptyCodeError,
    InvalidCode39CharacterError,
    extract_column,
    flatten_single_column,
    generate_barcode_image,
    iter_item_numbers,
    read_table_rows,
    sanitize_filename,
    save_barcode_image,
)

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

PREVIEW_MAX_SIZE = (620, 260)


def open_folder(path: Path) -> None:
    """Abre una carpeta en el explorador de archivos del sistema operativo."""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(path))  # noqa: S606 - ruta elegida por el propio usuario
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as exc:
        raise RuntimeError(f"No se pudo abrir la carpeta:\n{exc}") from exc


class LabeledEntry(ctk.CTkFrame):
    """Campo de formulario reutilizable: etiqueta + entrada, con estilo consistente."""

    def __init__(self, master, label: str, placeholder: str = "", **kwargs):
        super().__init__(master, fg_color="transparent")
        self.label = ctk.CTkLabel(self, text=label, anchor="w", font=ctk.CTkFont(size=13))
        self.label.pack(fill="x", padx=2, pady=(0, 2))
        self.entry = ctk.CTkEntry(self, placeholder_text=placeholder, **kwargs)
        self.entry.pack(fill="x")

    def get(self) -> str:
        return self.entry.get()

    def set(self, value: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, value)


class FormatPanel(ctk.CTkFrame):
    """Sección de formato: prefijo / número / relleno / sufijo / checksum.

    Este bloque es el que permite condicionar el número generado para
    vincularlo con un "item number" (por ejemplo ITM-000123-A).
    """

    def __init__(self, master, on_change=None):
        super().__init__(master, corner_radius=12)
        self.on_change = on_change

        title = ctk.CTkLabel(
            self, text="Formato del código", font=ctk.CTkFont(size=16, weight="bold")
        )
        title.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 8))

        self.prefix = LabeledEntry(self, "Prefijo (opcional)", "Ej: ITM-")
        self.prefix.grid(row=1, column=0, sticky="ew", padx=(16, 8), pady=6)

        self.suffix = LabeledEntry(self, "Sufijo (opcional)", "Ej: -A")
        self.suffix.grid(row=1, column=1, sticky="ew", padx=(8, 16), pady=6)

        self.item_number = LabeledEntry(self, "Número de ítem", "Ej: 123")
        self.item_number.grid(row=2, column=0, sticky="ew", padx=(16, 8), pady=6)

        self.pad_length = LabeledEntry(self, "Relleno con ceros (dígitos)", "Ej: 6")
        self.pad_length.set("0")
        self.pad_length.grid(row=2, column=1, sticky="ew", padx=(8, 16), pady=6)

        self.uppercase_var = tk.BooleanVar(value=True)
        self.uppercase_check = ctk.CTkCheckBox(
            self,
            text="Convertir automáticamente a mayúsculas",
            variable=self.uppercase_var,
            command=self._changed,
        )
        self.uppercase_check.grid(row=3, column=0, columnspan=2, sticky="w", padx=16, pady=(6, 2))

        self.checksum_var = tk.BooleanVar(value=False)
        self.checksum_check = ctk.CTkCheckBox(
            self,
            text="Agregar dígito de verificación (checksum mod43)",
            variable=self.checksum_var,
            command=self._changed,
        )
        self.checksum_check.grid(row=4, column=0, columnspan=2, sticky="w", padx=16, pady=(2, 6))

        self.preview_label = ctk.CTkLabel(
            self,
            text="Código resultante: —",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
            text_color=("#1f6aa5", "#4da6ff"),
        )
        self.preview_label.grid(row=5, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        for widget in (self.prefix.entry, self.suffix.entry, self.item_number.entry, self.pad_length.entry):
            widget.bind("<KeyRelease>", lambda _e: self._changed())

    def _changed(self) -> None:
        if self.on_change:
            self.on_change()

    def get_format(self) -> CodeFormat:
        pad_text = self.pad_length.get().strip()
        pad_length = min(int(pad_text), 40) if pad_text.isdigit() else 0
        return CodeFormat(
            prefix=self.prefix.get(),
            suffix=self.suffix.get(),
            pad_length=pad_length,
            uppercase=self.uppercase_var.get(),
        )

    def get_add_checksum(self) -> bool:
        return self.checksum_var.get()

    def update_preview_text(self, text: str, error: bool = False) -> None:
        color = ("#c0392b", "#ff6b6b") if error else ("#1f6aa5", "#4da6ff")
        self.preview_label.configure(text=text, text_color=color)


class StylePanel(ctk.CTkFrame):
    """Sección de apariencia: dimensiones, texto legible y colores."""

    def __init__(self, master, on_change=None):
        super().__init__(master, corner_radius=12)
        self.on_change = on_change

        title = ctk.CTkLabel(self, text="Apariencia", font=ctk.CTkFont(size=16, weight="bold"))
        title.grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(14, 8))

        self.module_width = self._add_slider("Ancho de barra", row=1, from_=0.15, to=0.6, default=0.25)
        self.module_height = self._add_slider("Alto (mm)", row=2, from_=5, to=40, default=15)
        self.quiet_zone = self._add_slider("Margen lateral", row=3, from_=0, to=20, default=6.5)

        self.write_text_var = tk.BooleanVar(value=True)
        self.write_text_check = ctk.CTkCheckBox(
            self,
            text="Mostrar texto legible debajo del código",
            variable=self.write_text_var,
            command=self._changed,
        )
        self.write_text_check.grid(row=4, column=0, columnspan=3, sticky="w", padx=16, pady=(6, 2))

        self.font_size = self._add_slider("Tamaño de texto", row=5, from_=6, to=20, default=10, is_int=True)

        self.foreground = "#000000"
        self.background = "#FFFFFF"
        colors_frame = ctk.CTkFrame(self, fg_color="transparent")
        colors_frame.grid(row=6, column=0, columnspan=3, sticky="ew", padx=16, pady=(10, 16))
        colors_frame.grid_columnconfigure((0, 1), weight=1)

        self.fg_button = ctk.CTkButton(
            colors_frame, text="Color de barras", fg_color=self.foreground,
            hover_color="#333333", command=self._pick_foreground,
        )
        self.fg_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.bg_button = ctk.CTkButton(
            colors_frame, text="Color de fondo", fg_color=self.background,
            text_color="#000000", hover_color="#dddddd", command=self._pick_background,
        )
        self.bg_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.grid_columnconfigure(0, weight=1)

    def _add_slider(self, label: str, row: int, from_: float, to: float, default: float, is_int: bool = False):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=row, column=0, columnspan=3, sticky="ew", padx=16, pady=(4, 8))
        container.grid_columnconfigure(0, weight=1)

        text_var = tk.StringVar(value=str(default))
        lbl = ctk.CTkLabel(container, text=f"{label}: {default}", anchor="w")
        lbl.grid(row=0, column=0, sticky="ew")

        def _on_move(value):
            value = int(value) if is_int else round(float(value), 2)
            lbl.configure(text=f"{label}: {value}")
            text_var.set(str(value))
            self._changed()

        slider = ctk.CTkSlider(container, from_=from_, to=to, command=_on_move)
        slider.set(default)
        slider.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        slider.text_var = text_var
        return slider

    def _pick_foreground(self):
        color = colorchooser.askcolor(color=self.foreground, title="Color de las barras")
        if color and color[1]:
            self.foreground = color[1]
            self.fg_button.configure(fg_color=self.foreground)
            self._changed()

    def _pick_background(self):
        color = colorchooser.askcolor(color=self.background, title="Color de fondo")
        if color and color[1]:
            self.background = color[1]
            self.bg_button.configure(fg_color=self.background)
            self._changed()

    def _changed(self) -> None:
        if self.on_change:
            self.on_change()

    def get_style(self) -> BarcodeStyle:
        return BarcodeStyle(
            module_width=float(self.module_width.text_var.get()),
            module_height=float(self.module_height.text_var.get()),
            font_size=int(float(self.font_size.text_var.get())),
            quiet_zone=float(self.quiet_zone.text_var.get()),
            write_text=self.write_text_var.get(),
            background=self.background,
            foreground=self.foreground,
        )


class IndividualTab(ctk.CTkFrame):
    """Pestaña para generar y descargar un único código de barras."""

    def __init__(self, master, app: "BarcodeApp"):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.current_image: Image.Image | None = None
        self.current_code: str = ""

        self.grid_columnconfigure(0, weight=0, minsize=380)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(self, fg_color="transparent", width=380)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        self.format_panel = FormatPanel(left, on_change=self.refresh_preview)
        self.format_panel.pack(fill="x", pady=(0, 12))

        self.style_panel = StylePanel(left, on_change=self.refresh_preview)
        self.style_panel.pack(fill="x", pady=(0, 12))

        button_row = ctk.CTkFrame(left, fg_color="transparent")
        button_row.pack(fill="x", pady=(4, 0))

        self.generate_btn = ctk.CTkButton(
            button_row, text="Generar vista previa", command=self.refresh_preview, height=40
        )
        self.generate_btn.pack(fill="x", pady=(0, 8))

        self.download_btn = ctk.CTkButton(
            button_row, text="⬇ Descargar imagen (PNG)", command=self.download_image,
            height=40, fg_color="#2e8b57", hover_color="#256e46",
        )
        self.download_btn.pack(fill="x")

        # Panel derecho: vista previa
        right = ctk.CTkFrame(self, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        preview_title = ctk.CTkLabel(right, text="Vista previa", font=ctk.CTkFont(size=16, weight="bold"))
        preview_title.grid(row=0, column=0, sticky="w", padx=16, pady=(14, 8))

        self.canvas_card = ctk.CTkFrame(right, fg_color="#FFFFFF", corner_radius=10)
        self.canvas_card.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))
        self.canvas_card.grid_rowconfigure(0, weight=1)
        self.canvas_card.grid_columnconfigure(0, weight=1)

        self.image_label = ctk.CTkLabel(self.canvas_card, text="", image=None)
        self.image_label.grid(row=0, column=0, sticky="nsew")

        self.status_label = ctk.CTkLabel(right, text="Ingresa un número de ítem para comenzar.", anchor="w")
        self.status_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))

        self.refresh_preview()

    def refresh_preview(self) -> None:
        fmt = self.format_panel.get_format()
        item_number = self.format_panel.item_number.get()
        code_text = fmt.build(item_number)
        style = self.style_panel.get_style()
        add_checksum = self.format_panel.get_add_checksum()

        if not item_number.strip():
            self.format_panel.update_preview_text("Código resultante: —")
            self.status_label.configure(text="Ingresa un número de ítem para comenzar.")
            self.current_image = None
            self.image_label.configure(image=None, text="")
            return

        try:
            image, final_code = generate_barcode_image(code_text, style, add_checksum=add_checksum)
        except (InvalidCode39CharacterError, EmptyCodeError) as exc:
            self.format_panel.update_preview_text(f"Código resultante: {code_text}", error=True)
            self.status_label.configure(text=str(exc), text_color=("#c0392b", "#ff6b6b"))
            self.current_image = None
            self.image_label.configure(image=None, text="")
            return
        except Exception as exc:  # noqa: BLE001 - se muestra cualquier error inesperado al usuario
            self.status_label.configure(text=f"Error inesperado: {exc}", text_color=("#c0392b", "#ff6b6b"))
            return

        self.format_panel.update_preview_text(f"Código resultante: {final_code}")
        self.current_image = image
        self.current_code = final_code

        ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=self._fit_size(image))
        self.image_label.configure(image=ctk_image, text="")
        self.image_label.image = ctk_image

        self.status_label.configure(
            text=f"Listo — {image.width}×{image.height}px  ·  código codificado: {final_code}",
            text_color=("gray20", "gray80"),
        )

    @staticmethod
    def _fit_size(image: Image.Image) -> tuple[int, int]:
        max_w, max_h = PREVIEW_MAX_SIZE
        ratio = min(max_w / image.width, max_h / image.height, 1.0)
        width = max(1, round(image.width * ratio))
        height = max(1, round(image.height * ratio))
        return (width, height)

    def download_image(self) -> None:
        if self.current_image is None:
            messagebox.showwarning("Sin código", "Genera un código de barras válido antes de descargarlo.")
            return
        default_name = sanitize_filename(self.current_code) + ".png"
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=default_name,
            filetypes=[("Imagen PNG", "*.png"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        try:
            save_barcode_image(self.current_image, Path(path))
        except OSError as exc:
            messagebox.showerror("Error al guardar", str(exc))
            return
        self.status_label.configure(text=f"Imagen guardada en: {path}", text_color=("gray20", "gray80"))


class ColumnPickerDialog(ctk.CTkToplevel):
    """Modal para elegir qué columna de un archivo con varias columnas trae los números de ítem."""

    def __init__(self, master, rows: list[list[str]], on_confirm):
        super().__init__(master)
        self.title("Selecciona la columna de números de ítem")
        self.geometry("520x440")
        self.minsize(460, 380)
        self.rows = rows
        self.on_confirm = on_confirm
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(
            self,
            text="Tu archivo tiene varias columnas. Elige cuál contiene los números de ítem.",
            wraplength=480,
            justify="left",
        ).pack(fill="x", padx=16, pady=(16, 8))

        self.header_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self, text="La primera fila es encabezado", variable=self.header_var, command=self._refresh
        ).pack(anchor="w", padx=16, pady=(0, 8))

        ctk.CTkLabel(self, text="Columna:", anchor="w").pack(fill="x", padx=16)
        self.column_menu = ctk.CTkOptionMenu(self, values=["Columna 1"])
        self.column_menu.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(self, text="Vista previa:", anchor="w").pack(fill="x", padx=16)
        self.preview_box = ctk.CTkTextbox(self, height=180)
        self.preview_box.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.preview_box.configure(state="disabled")

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(button_row, text="Cancelar", fg_color="gray40", hover_color="gray30", command=self.destroy).pack(
            side="left", expand=True, fill="x", padx=(0, 6)
        )
        ctk.CTkButton(button_row, text="Usar esta columna", command=self._confirm).pack(
            side="left", expand=True, fill="x", padx=(6, 0)
        )

        self._refresh()

    def _column_labels(self) -> list[str]:
        max_cols = max(len(row) for row in self.rows)
        if self.header_var.get() and self.rows:
            header_row = self.rows[0]
            return [
                header_row[i] if i < len(header_row) and header_row[i] else f"Columna {i + 1}"
                for i in range(max_cols)
            ]
        return [f"Columna {i + 1}" for i in range(max_cols)]

    def _refresh(self) -> None:
        labels = self._column_labels()
        self.column_menu.configure(values=labels)
        self.column_menu.set(labels[0])

        has_header = self.header_var.get()
        preview_rows = self.rows[1:6] if has_header else self.rows[:5]
        text = "\n".join(" | ".join(row) for row in preview_rows) or "(sin datos)"
        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", "end")
        self.preview_box.insert("1.0", text)
        self.preview_box.configure(state="disabled")

    def _confirm(self) -> None:
        labels = self._column_labels()
        selected = self.column_menu.get()
        column_index = labels.index(selected) if selected in labels else 0
        numbers = extract_column(self.rows, column_index, self.header_var.get())
        self.destroy()
        self.on_confirm(numbers)


class BatchTab(ctk.CTkFrame):
    """Pestaña para generar en lote un código de barras por cada número de ítem de un rango."""

    def __init__(self, master, app: "BarcodeApp"):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.output_dir: Path | None = None
        self.progress_queue: queue.Queue = queue.Queue()
        self.worker_thread: threading.Thread | None = None
        self.source_mode: str = "rango"
        self.loaded_numbers: list[str] = []
        self.loaded_file_path: Path | None = None

        self.grid_columnconfigure(0, weight=0, minsize=380)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(self, fg_color="transparent", width=380)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        self.format_panel = FormatPanel(left, on_change=self.refresh_sample)
        # En lote no tiene sentido pedir un único número; lo ocultamos y usamos rango o archivo.
        self.format_panel.item_number.grid_remove()
        self.format_panel.pad_length.grid_configure(columnspan=2)
        # Este panel también trae su propio "Código resultante", pero solo lo actualiza
        # la pestaña Individual; en lote usamos el label "Ejemplo" de más abajo en su lugar.
        self.format_panel.preview_label.grid_remove()
        self.format_panel.pack(fill="x", pady=(0, 12))

        source_frame = ctk.CTkFrame(left, corner_radius=12)
        source_frame.pack(fill="x", pady=(0, 12))
        source_title = ctk.CTkLabel(source_frame, text="Números de ítems", font=ctk.CTkFont(size=16, weight="bold"))
        source_title.pack(anchor="w", padx=16, pady=(14, 8))

        self.mode_selector = ctk.CTkSegmentedButton(
            source_frame, values=["Rango", "Archivo"], command=self._on_mode_change
        )
        self.mode_selector.set("Rango")
        self.mode_selector.pack(fill="x", padx=16, pady=(0, 10))

        self.range_subframe = ctk.CTkFrame(source_frame, fg_color="transparent")
        self.start_entry = LabeledEntry(self.range_subframe, "Número inicial", "Ej: 1")
        self.start_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.end_entry = LabeledEntry(self.range_subframe, "Número final", "Ej: 50")
        self.end_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.range_subframe.grid_columnconfigure((0, 1), weight=1)
        for widget in (self.start_entry.entry, self.end_entry.entry):
            widget.bind("<KeyRelease>", lambda _e: self.refresh_sample())
        self.range_subframe.pack(fill="x", padx=16, pady=(0, 8))

        self.file_subframe = ctk.CTkFrame(source_frame, fg_color="transparent")
        ctk.CTkButton(
            self.file_subframe, text="Cargar archivo (.txt / .csv)...", command=self.choose_numbers_file
        ).pack(fill="x")
        self.file_info_label = ctk.CTkLabel(
            self.file_subframe, text="Ningún archivo cargado", anchor="w", wraplength=330
        )
        self.file_info_label.pack(fill="x", pady=(8, 0))

        self.sample_label = ctk.CTkLabel(source_frame, text="Ejemplo: —", anchor="w")
        self.sample_label.pack(fill="x", padx=16, pady=(0, 14))

        self.style_panel = StylePanel(left, on_change=self.refresh_sample)
        self.style_panel.pack(fill="x", pady=(0, 12))

        dest_frame = ctk.CTkFrame(left, corner_radius=12)
        dest_frame.pack(fill="x", pady=(0, 12))
        dest_title = ctk.CTkLabel(dest_frame, text="Carpeta destino", font=ctk.CTkFont(size=16, weight="bold"))
        dest_title.pack(anchor="w", padx=16, pady=(14, 8))
        self.dest_label = ctk.CTkLabel(dest_frame, text="Ninguna carpeta seleccionada", anchor="w", wraplength=330)
        self.dest_label.pack(fill="x", padx=16)
        ctk.CTkButton(dest_frame, text="Elegir carpeta...", command=self.choose_folder).pack(
            fill="x", padx=16, pady=(8, 8)
        )
        self.open_folder_btn = ctk.CTkButton(
            dest_frame, text="Abrir carpeta destino", command=self.open_destination_folder,
            fg_color="gray40", hover_color="gray30", state="disabled",
        )
        self.open_folder_btn.pack(fill="x", padx=16, pady=(0, 16))

        self.generate_batch_btn = ctk.CTkButton(
            left, text="Generar lote", command=self.start_batch, height=40,
            fg_color="#2e8b57", hover_color="#256e46",
        )
        self.generate_batch_btn.pack(fill="x", pady=(4, 0))

        # Panel derecho: progreso y resumen
        right = ctk.CTkFrame(self, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(right, text="Progreso del lote", font=ctk.CTkFont(size=16, weight="bold"))
        title.grid(row=0, column=0, sticky="w", padx=16, pady=(14, 8))

        self.progress_bar = ctk.CTkProgressBar(right)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        self.progress_label = ctk.CTkLabel(right, text="Sin actividad todavía.", anchor="w")
        self.progress_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))

        self.log_box = ctk.CTkTextbox(right, wrap="word")
        self.log_box.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.log_box.configure(state="disabled")
        right.grid_rowconfigure(3, weight=1)

        self.refresh_sample()

    def refresh_sample(self) -> None:
        fmt = self.format_panel.get_format()
        if self.source_mode == "archivo":
            sample_number = self.loaded_numbers[0] if self.loaded_numbers else "123"
        else:
            start_text = self.start_entry.get().strip()
            sample_number = start_text if start_text.isdigit() else "123"
        code = fmt.build(sample_number)
        try:
            from src.barcode_core import validate_code39

            validate_code39(code)
            self.sample_label.configure(text=f"Ejemplo: {code}", text_color=("gray20", "gray80"))
        except (InvalidCode39CharacterError, EmptyCodeError) as exc:
            self.sample_label.configure(text=str(exc), text_color=("#c0392b", "#ff6b6b"))

    def _on_mode_change(self, value: str) -> None:
        self.source_mode = "archivo" if value == "Archivo" else "rango"
        if self.source_mode == "rango":
            self.file_subframe.pack_forget()
            self.range_subframe.pack(fill="x", padx=16, pady=(0, 8))
        else:
            self.range_subframe.pack_forget()
            self.file_subframe.pack(fill="x", padx=16, pady=(0, 8))
        self.refresh_sample()

    def choose_numbers_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecciona un archivo con números de ítem",
            filetypes=[("Texto o CSV", "*.txt *.csv"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        file_path = Path(path)
        try:
            rows = read_table_rows(file_path)
        except OSError as exc:
            messagebox.showerror("Error al leer archivo", str(exc))
            return
        if not rows:
            messagebox.showwarning("Archivo vacío", "El archivo no contiene datos.")
            return

        max_cols = max(len(row) for row in rows)
        if max_cols <= 1:
            numbers = flatten_single_column(rows)
            if not numbers:
                messagebox.showwarning("Archivo vacío", "El archivo no contiene números de ítem.")
                return
            self._apply_loaded_numbers(numbers, file_path)
            return

        def on_confirm(numbers: list[str]) -> None:
            if not numbers:
                messagebox.showwarning("Columna vacía", "La columna elegida no contiene valores.")
                return
            self._apply_loaded_numbers(numbers, file_path)

        ColumnPickerDialog(self, rows, on_confirm)

    def _apply_loaded_numbers(self, numbers: list[str], file_path: Path) -> None:
        self.loaded_numbers = numbers
        self.loaded_file_path = file_path
        self.file_info_label.configure(
            text=f"{file_path.name} — {len(numbers)} números cargados",
            text_color=("gray20", "gray80"),
        )
        self.refresh_sample()

    def choose_folder(self) -> None:
        folder = filedialog.askdirectory(title="Selecciona la carpeta destino")
        if folder:
            self.output_dir = Path(folder)
            self.dest_label.configure(text=str(self.output_dir))
            self.open_folder_btn.configure(state="normal")

    def open_destination_folder(self) -> None:
        if self.output_dir is None:
            messagebox.showwarning("Sin carpeta", "Primero selecciona una carpeta destino.")
            return
        try:
            open_folder(self.output_dir)
        except RuntimeError as exc:
            messagebox.showerror("Error al abrir la carpeta", str(exc))

    def _log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def start_batch(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("En progreso", "Ya hay una generación de lote en curso.")
            return
        if self.output_dir is None:
            messagebox.showwarning("Falta carpeta", "Selecciona una carpeta destino antes de generar el lote.")
            return

        if self.source_mode == "archivo":
            if not self.loaded_numbers:
                messagebox.showwarning(
                    "Falta archivo", "Carga un archivo con números de ítem antes de generar el lote."
                )
                return
            numbers = list(self.loaded_numbers)
        else:
            start_text = self.start_entry.get().strip()
            end_text = self.end_entry.get().strip()
            if not (start_text.isdigit() and end_text.isdigit()):
                messagebox.showwarning("Rango inválido", "El número inicial y final deben ser enteros positivos.")
                return
            start, end = int(start_text), int(end_text)
            numbers = [str(n) for n in iter_item_numbers(start, end)]

        if len(numbers) > 5000:
            if not messagebox.askyesno(
                "Lote muy grande",
                f"Vas a generar {len(numbers)} imágenes. ¿Deseas continuar?",
            ):
                return

        fmt = self.format_panel.get_format()
        style = self.style_panel.get_style()
        add_checksum = self.format_panel.get_add_checksum()
        output_dir = self.output_dir

        self.generate_batch_btn.configure(state="disabled", text="Generando...")
        self.progress_bar.set(0)
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        def worker():
            total = len(numbers)
            ok, failed = 0, 0
            for index, number in enumerate(numbers, start=1):
                code_text = fmt.build(number)
                try:
                    image, final_code = generate_barcode_image(code_text, style, add_checksum=add_checksum)
                    filename = sanitize_filename(final_code) + ".png"
                    save_barcode_image(image, output_dir / filename)
                    ok += 1
                    self.progress_queue.put(("log", f"[{index}/{total}] OK  -> {filename}"))
                except (InvalidCode39CharacterError, EmptyCodeError) as exc:
                    failed += 1
                    self.progress_queue.put(("log", f"[{index}/{total}] ERROR ({code_text}): {exc}"))
                self.progress_queue.put(("progress", index / total))
            self.progress_queue.put(("done", (ok, failed, total)))

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()
        self.after(80, self._poll_queue)

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.progress_queue.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "progress":
                    self.progress_bar.set(payload)
                    self.progress_label.configure(text=f"Progreso: {payload * 100:.0f}%")
                elif kind == "done":
                    ok, failed, total = payload
                    self.progress_label.configure(text=f"Completado: {ok} generados, {failed} con error de {total}.")
                    self.generate_batch_btn.configure(state="normal", text="Generar lote")
                    open_now = messagebox.askyesno(
                        "Lote completado",
                        f"Se generaron {ok} de {total} códigos en:\n{self.output_dir}"
                        + (f"\n\n{failed} códigos tuvieron errores (ver registro)." if failed else "")
                        + "\n\n¿Deseas abrir la carpeta ahora?",
                    )
                    if open_now and self.output_dir is not None:
                        try:
                            open_folder(self.output_dir)
                        except RuntimeError as exc:
                            messagebox.showerror("Error al abrir la carpeta", str(exc))
        except queue.Empty:
            pass

        if self.worker_thread and self.worker_thread.is_alive():
            self.after(80, self._poll_queue)


class BarcodeApp(ctk.CTk):
    """Ventana principal de la aplicación."""

    def __init__(self):
        super().__init__()
        self.title("Generador de Códigos de Barras · Code 39")
        self.geometry("1180x760")
        self.minsize(980, 620)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))

        title_label = ctk.CTkLabel(
            header, text="📦 Generador de Códigos de Barras (Code 39)",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title_label.pack(side="left")

        appearance_menu = ctk.CTkOptionMenu(
            header, values=["System", "Light", "Dark"],
            command=lambda mode: ctk.set_appearance_mode(mode), width=120,
        )
        appearance_menu.pack(side="right")
        appearance_menu.set("System")

        self.tabview = ctk.CTkTabview(self, corner_radius=12)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.tabview.add("Individual")
        self.tabview.add("Generación por lote")

        self.individual_tab = IndividualTab(self.tabview.tab("Individual"), self)
        self.individual_tab.pack(fill="both", expand=True, padx=12, pady=12)

        self.batch_tab = BatchTab(self.tabview.tab("Generación por lote"), self)
        self.batch_tab.pack(fill="both", expand=True, padx=12, pady=12)


def run() -> None:
    app = BarcodeApp()
    app.mainloop()
