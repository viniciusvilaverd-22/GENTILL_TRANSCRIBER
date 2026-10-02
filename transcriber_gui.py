from __future__ import annotations

import argparse
import math
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from transcriber import SUPPORTED_INPUTS, transcribe, write_outputs


SOURCE_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_DIR))
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else SOURCE_DIR
DEFAULT_MODEL = RESOURCE_DIR / "models" / "whisper-small-ct2"
DEFAULT_OUTPUT = Path.home() / "Documents" / "Gentill Transcriber" / "Transcricoes"
APP_ICON = RESOURCE_DIR / "assets" / "gentill_transcriber.ico"
APP_VERSION = "0.3.0-rc1"

ABOUT_AUTHOR = "Vinícius Vilaverde"
ABOUT_ORGANIZATION = "Gentill Ops"
ABOUT_GITHUB_URL = "https://github.com/viniciusvilaverd-22/GENTILL_TRANSCRIBER"
ABOUT_PIX_KEY = "eb608e93-1781-49fc-9a70-94cc395dcd53"
ABOUT_PIX_STATUS = "Aguardando chave Pix do autor"

BRAND_DEEP = "#0B1F3B"
BRAND_BLUE = "#2563EB"
BRAND_LIGHT = "#60A5FA"
BRAND_GREEN = "#10B981"
BRAND_NEUTRAL = "#6B7280"

BG = "#07162B"
CARD = "#0D2340"
CARD_ALT = "#112D50"
BORDER = "#23456D"
TEXT = "#F8FAFC"
MUTED = "#9FB3CC"
ACCENT = BRAND_BLUE
ACCENT_ACTIVE = "#3B82F6"
SUCCESS = BRAND_GREEN
DANGER = "#EF4444"


def human_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = max(0, int(round(float(seconds))))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}min"
    if minutes:
        return f"{minutes:d}min {secs:02d}s"
    return f"{secs:d}s"


def input_filetypes() -> list[tuple[str, str]]:
    media = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_INPUTS))
    return [
        ("Áudio e vídeo suportados", media),
        ("Todos os arquivos", "*.*"),
    ]


class TranscriberApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Gentill Transcriber")
        self.geometry("1220x800")
        self.minsize(1020, 700)
        self.configure(bg=BG)
        self._apply_window_icon()

        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar(value=str(DEFAULT_OUTPUT))
        self.model_path = tk.StringVar(value=str(DEFAULT_MODEL))
        self.language = tk.StringVar(value="pt")
        self.device = tk.StringVar(value="cpu")
        self.compute_type = tk.StringVar(value="int8")
        self.status_text = tk.StringVar(value="Pronto para transcrever")
        self.file_meta = tk.StringVar(value="Nenhum arquivo selecionado")
        self.result_meta = tk.StringVar(value="A transcrição aparecerá aqui.")
        self.motion_status = tk.StringVar(value="Motor local pronto")
        self.motion_elapsed = tk.StringVar(value="00:00")
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._busy = False
        self._motion_frame = 0
        self._motion_started = 0.0
        self._motion_job: str | None = None

        self._configure_styles()
        self._build_ui()
        self.after(50, self._draw_waveform)
        self.after(120, self._drain_events)

    def _apply_window_icon(self) -> None:
        if not APP_ICON.is_file():
            return
        try:
            self.iconbitmap(default=str(APP_ICON))
        except tk.TclError:
            pass

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD, relief="flat")
        style.configure("Soft.TFrame", background=CARD_ALT, relief="flat")
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 25))
        style.configure("Brand.TLabel", background=BG, foreground=BRAND_LIGHT, font=("Segoe UI Semibold", 25))
        style.configure("Eyebrow.TLabel", background=BG, foreground=BRAND_LIGHT, font=("Segoe UI Semibold", 9))
        style.configure("Subtitle.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background=CARD, foreground=TEXT, font=("Segoe UI Semibold", 12))
        style.configure("Label.TLabel", background=CARD, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Value.TLabel", background=CARD_ALT, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Badge.TLabel", background=CARD_ALT, foreground=SUCCESS, font=("Segoe UI Semibold", 9), padding=(10, 5))
        style.configure("Motion.TLabel", background=BRAND_DEEP, foreground=TEXT, font=("Segoe UI Semibold", 10))
        style.configure("MotionSub.TLabel", background=BRAND_DEEP, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Status.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Primary.TButton", background=ACCENT, foreground="#07111F", borderwidth=0, focusthickness=0, font=("Segoe UI Semibold", 10), padding=(16, 11))
        style.map("Primary.TButton", background=[("active", ACCENT_ACTIVE), ("disabled", BORDER)])
        style.configure("Secondary.TButton", background=CARD_ALT, foreground=TEXT, borderwidth=0, focusthickness=0, font=("Segoe UI Semibold", 9), padding=(12, 9))
        style.map("Secondary.TButton", background=[("active", BORDER)])
        style.configure("TEntry", fieldbackground=CARD_ALT, foreground=TEXT, insertcolor=TEXT, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=8)
        style.configure("TCombobox", fieldbackground=CARD_ALT, background=CARD_ALT, foreground=TEXT, arrowcolor=MUTED, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=7)
        style.map("TCombobox", fieldbackground=[("readonly", CARD_ALT)], foreground=[("readonly", TEXT)])
        style.configure("Horizontal.TProgressbar", troughcolor=CARD_ALT, background=ACCENT, bordercolor=CARD_ALT, lightcolor=ACCENT, darkcolor=ACCENT, thickness=5)

    def _build_ui(self) -> None:
        shell = ttk.Frame(self, style="App.TFrame", padding=(28, 24, 28, 20))
        shell.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        shell.grid_columnconfigure(0, weight=0, minsize=390)
        shell.grid_columnconfigure(1, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        header = ttk.Frame(shell, style="App.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        header.grid_columnconfigure(0, weight=1)

        title_wrap = ttk.Frame(header, style="App.TFrame")
        title_wrap.grid(row=0, column=0, sticky="w")
        title_wrap.grid_columnconfigure(1, weight=0)

        self.brand_mark = tk.Canvas(title_wrap, width=52, height=48, bg=BG, highlightthickness=0)
        self.brand_mark.grid(row=0, column=0, rowspan=3, sticky="w", padx=(0, 12))
        self._draw_brand_mark()

        wordmark = ttk.Frame(title_wrap, style="App.TFrame")
        wordmark.grid(row=0, column=1, sticky="w")
        ttk.Label(wordmark, text="Gentill", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(wordmark, text=" Transcriber", style="Brand.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(title_wrap, text="ÁUDIO E VÍDEO EM TEXTO  •  LOCAL  •  OFFLINE  •  PRIVADO", style="Eyebrow.TLabel").grid(row=1, column=1, sticky="w", pady=(2, 0))
        ttk.Label(title_wrap, text="Transcrição local com privacidade e controle total dos seus dados.", style="Subtitle.TLabel").grid(row=2, column=1, sticky="w", pady=(3, 0))
        header_actions = ttk.Frame(header, style="App.TFrame")
        header_actions.grid(row=0, column=1, rowspan=3, sticky="e")
        ttk.Label(header_actions, text="●  100% OFFLINE", style="Badge.TLabel").grid(row=0, column=0, padx=(0, 10))
        ttk.Button(header_actions, text="Sobre", style="Secondary.TButton", command=self._show_about).grid(row=0, column=1)

        controls = ttk.Frame(shell, style="Card.TFrame", padding=20)
        controls.grid(row=1, column=0, sticky="nsew", padx=(0, 18))
        controls.grid_columnconfigure(0, weight=1)

        ttk.Label(controls, text="Arquivo de entrada", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(controls, text="Selecione um áudio ou vídeo para processar.", style="Label.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 10))

        input_box = ttk.Frame(controls, style="Soft.TFrame", padding=12)
        input_box.grid(row=2, column=0, sticky="ew")
        input_box.grid_columnconfigure(0, weight=1)
        ttk.Label(input_box, textvariable=self.file_meta, style="Value.TLabel", wraplength=250).grid(row=0, column=0, sticky="w")
        ttk.Button(input_box, text="Escolher", style="Secondary.TButton", command=self._pick_input).grid(row=0, column=1, sticky="e", padx=(10, 0))

        ttk.Separator(controls, orient="horizontal").grid(row=3, column=0, sticky="ew", pady=18)
        ttk.Label(controls, text="Configurações", style="CardTitle.TLabel").grid(row=4, column=0, sticky="w")

        settings = ttk.Frame(controls, style="Card.TFrame")
        settings.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        settings.grid_columnconfigure(0, weight=1)
        settings.grid_columnconfigure(1, weight=1)

        self._field(settings, "Idioma", self.language, 0, 0, ("pt", "auto", "en", "es"))
        self._field(settings, "Dispositivo", self.device, 0, 1, ("cpu", "auto", "cuda"))
        self._field(settings, "Precisão", self.compute_type, 1, 0, ("int8", "float32", "float16"))

        output_block = ttk.Frame(settings, style="Card.TFrame")
        output_block.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        output_block.grid_columnconfigure(0, weight=1)
        ttk.Label(output_block, text="Pasta de saída", style="Label.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 5))
        ttk.Entry(output_block, textvariable=self.output_path).grid(row=1, column=0, sticky="ew")
        ttk.Button(output_block, text="…", style="Secondary.TButton", width=3, command=self._pick_output).grid(row=1, column=1, padx=(8, 0))

        model_block = ttk.Frame(settings, style="Card.TFrame")
        model_block.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        model_block.grid_columnconfigure(0, weight=1)
        ttk.Label(model_block, text="Modelo local", style="Label.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 5))
        ttk.Entry(model_block, textvariable=self.model_path).grid(row=1, column=0, sticky="ew")
        ttk.Button(model_block, text="…", style="Secondary.TButton", width=3, command=self._pick_model).grid(row=1, column=1, padx=(8, 0))

        controls.grid_rowconfigure(6, weight=1)
        action_wrap = ttk.Frame(controls, style="Card.TFrame")
        action_wrap.grid(row=7, column=0, sticky="ew", pady=(20, 0))
        action_wrap.grid_columnconfigure(0, weight=1)
        self.transcribe_button = ttk.Button(action_wrap, text="Transcrever agora", style="Primary.TButton", command=self._start_transcription)
        self.transcribe_button.grid(row=0, column=0, sticky="ew")

        preview = ttk.Frame(shell, style="Card.TFrame", padding=20)
        preview.grid(row=1, column=1, sticky="nsew")
        preview.grid_rowconfigure(3, weight=1)
        preview.grid_columnconfigure(0, weight=1)

        preview_head = ttk.Frame(preview, style="Card.TFrame")
        preview_head.grid(row=0, column=0, sticky="ew")
        preview_head.grid_columnconfigure(0, weight=1)
        ttk.Label(preview_head, text="Transcrição", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")

        actions = ttk.Frame(preview_head, style="Card.TFrame")
        actions.grid(row=0, column=1, sticky="e")
        ttk.Button(actions, text="Copiar", style="Secondary.TButton", command=self._copy_text).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(actions, text="Abrir saída", style="Secondary.TButton", command=self._open_output).grid(row=0, column=1)

        ttk.Label(preview, textvariable=self.result_meta, style="Label.TLabel").grid(row=1, column=0, sticky="w", pady=(5, 12))

        motion = tk.Frame(preview, bg=BRAND_DEEP, highlightbackground=BORDER, highlightthickness=1)
        motion.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        motion.grid_columnconfigure(0, weight=1)

        motion_head = tk.Frame(motion, bg=BRAND_DEEP)
        motion_head.grid(row=0, column=0, sticky="ew", padx=16, pady=(13, 2))
        motion_head.grid_columnconfigure(0, weight=1)
        tk.Label(motion_head, textvariable=self.motion_status, bg=BRAND_DEEP, fg=TEXT, font=("Segoe UI Semibold", 10)).grid(row=0, column=0, sticky="w")
        tk.Label(motion_head, textvariable=self.motion_elapsed, bg=BRAND_DEEP, fg=BRAND_LIGHT, font=("Segoe UI Semibold", 10)).grid(row=0, column=1, sticky="e")

        tk.Label(motion, text="Processamento local • seu áudio não sai deste dispositivo", bg=BRAND_DEEP, fg=MUTED, font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", padx=16)

        self.wave_canvas = tk.Canvas(motion, height=82, bg=BRAND_DEEP, highlightthickness=0)
        self.wave_canvas.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 10))
        self.wave_canvas.bind("<Configure>", lambda _event: self._draw_waveform())

        text_wrap = ttk.Frame(preview, style="Soft.TFrame", padding=1)
        text_wrap.grid(row=3, column=0, sticky="nsew")
        text_wrap.grid_rowconfigure(0, weight=1)
        text_wrap.grid_columnconfigure(0, weight=1)

        self.preview_text = tk.Text(text_wrap, bg=CARD_ALT, fg=TEXT, insertbackground=TEXT, selectbackground=ACCENT, selectforeground="#07111F", relief="flat", borderwidth=0, wrap="word", padx=18, pady=16, font=("Segoe UI", 11), spacing1=2, spacing3=4)
        self.preview_text.grid(row=0, column=0, sticky="nsew")
        self.preview_text.insert("1.0", "Selecione um arquivo para iniciar uma transcrição.")
        self.preview_text.configure(state="disabled")

        scrollbar = ttk.Scrollbar(text_wrap, orient="vertical", command=self.preview_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.preview_text.configure(yscrollcommand=scrollbar.set)

        footer = ttk.Frame(shell, style="App.TFrame")
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        footer.grid_columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_text, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(footer, mode="indeterminate", style="Horizontal.TProgressbar", length=220)
        self.progress.grid(row=0, column=1, sticky="e")

    def _field(self, parent: ttk.Frame, label: str, variable: tk.StringVar, row: int, column: int, values: tuple[str, ...]) -> None:
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.grid(row=row, column=column, sticky="ew", padx=(0, 6) if column == 0 else (6, 0), pady=(0, 2))
        frame.grid_columnconfigure(0, weight=1)
        ttk.Label(frame, text=label, style="Label.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 5))
        ttk.Combobox(frame, textvariable=variable, values=values, state="readonly").grid(row=1, column=0, sticky="ew")

    def _pick_input(self) -> None:
        selected = filedialog.askopenfilename(title="Escolha um áudio ou vídeo", filetypes=input_filetypes())
        if not selected:
            return
        path = Path(selected)
        self.input_path.set(str(path))
        size_mb = path.stat().st_size / (1024 * 1024)
        self.file_meta.set(f"{path.name}\n{path.suffix.upper().lstrip('.')}  •  {size_mb:.1f} MB")
        self.status_text.set("Arquivo selecionado. Pronto para transcrever.")

    def _pick_output(self) -> None:
        selected = filedialog.askdirectory(title="Escolha a pasta de saída", initialdir=self.output_path.get() or str(APP_DIR))
        if selected:
            self.output_path.set(selected)

    def _pick_model(self) -> None:
        selected = filedialog.askdirectory(title="Escolha a pasta do modelo local", initialdir=self.model_path.get() or str(APP_DIR))
        if selected:
            self.model_path.set(selected)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            self.progress.start(12)
            self.transcribe_button.configure(state="disabled", text="Transcrevendo…")
            self._start_motion()
        else:
            self.progress.stop()
            self.transcribe_button.configure(state="normal", text="Transcrever agora")
            self._stop_motion()

    def _start_transcription(self) -> None:
        if self._busy:
            return
        input_value = self.input_path.get().strip()
        if not input_value:
            messagebox.showwarning("Selecione um arquivo", "Escolha um áudio ou vídeo antes de iniciar.")
            return

        input_path = Path(input_value)
        output_dir = Path(self.output_path.get().strip() or DEFAULT_OUTPUT)
        model_path = Path(self.model_path.get().strip() or DEFAULT_MODEL)
        language = None if self.language.get().lower() == "auto" else self.language.get().lower()

        if not input_path.is_file():
            messagebox.showerror("Arquivo não encontrado", str(input_path))
            return
        if not model_path.is_dir():
            messagebox.showerror("Modelo não encontrado", f"Modelo local não encontrado:\n{model_path}")
            return

        self._set_busy(True)
        self.status_text.set("Processamento local em andamento…")
        self.result_meta.set("Motor offline ativo. Aguarde a conclusão.")
        self.motion_status.set("Transcrição local em andamento")
        self._replace_preview("Transcrevendo…\n\nO áudio permanece nesta máquina.")

        threading.Thread(target=self._worker, args=(input_path, output_dir, model_path, language, self.device.get(), self.compute_type.get()), daemon=True).start()

    def _worker(self, input_path: Path, output_dir: Path, model_path: Path, language: str | None, device: str, compute_type: str) -> None:
        try:
            segments, metadata = transcribe(input_path=input_path, model_path=model_path, language=language, device=device, compute_type=compute_type)
            write_outputs(output_dir, input_path.stem, segments, metadata)
            text_value = "\n\n".join(segment.text.strip() for segment in segments if segment.text.strip())
            self._events.put(("success", (input_path, output_dir, segments, metadata, text_value)))
        except Exception as exc:
            self._events.put(("error", exc))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "success":
                    input_path, output_dir, segments, metadata, text_value = payload
                    self._set_busy(False)
                    self._replace_preview(text_value or "Nenhum trecho de fala foi detectado.")
                    language = metadata.get("language") or "—"
                    duration = human_duration(metadata.get("duration"))
                    self.result_meta.set(f"{input_path.name}  •  {len(segments)} segmentos  •  idioma {language}  •  {duration}")
                    self.status_text.set(f"Concluído. Arquivos salvos em {output_dir}")
                    self.motion_status.set("Transcrição concluída")
                    self._draw_waveform(final_state="success")
                elif kind == "error":
                    self._set_busy(False)
                    self.status_text.set("Falha na transcrição")
                    self.result_meta.set("A transcrição não foi concluída.")
                    self._replace_preview(f"Erro:\n{payload}")
                    self.motion_status.set("Falha no processamento")
                    self._draw_waveform(final_state="error")
                    messagebox.showerror("Falha na transcrição", str(payload))
        except queue.Empty:
            pass
        finally:
            self.after(120, self._drain_events)

    def _draw_brand_mark(self) -> None:
        canvas = self.brand_mark
        canvas.delete("all")
        bars = [16, 28, 38, 24, 14]
        x = 4
        center = 24
        for index, height in enumerate(bars):
            color = BRAND_LIGHT if index % 2 == 0 else BRAND_BLUE
            canvas.create_rectangle(x, center - height / 2, x + 4, center + height / 2, fill=color, outline="")
            x += 7
        canvas.create_line(38, 9, 48, 9, 48, 39, 38, 39, fill=BRAND_LIGHT, width=3)
        canvas.create_line(39, 18, 46, 18, fill=BRAND_BLUE, width=2)
        canvas.create_line(39, 25, 46, 25, fill=BRAND_BLUE, width=2)
        canvas.create_line(39, 32, 45, 32, fill=BRAND_BLUE, width=2)

    def _draw_waveform(self, final_state: str | None = None) -> None:
        if not hasattr(self, "wave_canvas"):
            return
        canvas = self.wave_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 420)
        height = max(canvas.winfo_height(), 82)
        center = height / 2
        count = 44
        gap = width / (count + 1)

        for index in range(count):
            x = gap * (index + 1)
            if final_state == "success":
                amplitude = 8 + 12 * (0.5 + 0.5 * math.sin(index * 0.68))
                color = BRAND_GREEN
            elif final_state == "error":
                amplitude = 7 + 7 * (0.5 + 0.5 * math.sin(index * 0.9))
                color = DANGER
            elif self._busy:
                wave_a = 0.5 + 0.5 * math.sin(self._motion_frame * 0.19 + index * 0.72)
                wave_b = 0.5 + 0.5 * math.sin(self._motion_frame * 0.11 - index * 0.38)
                amplitude = 8 + 24 * (0.55 * wave_a + 0.45 * wave_b)
                color = BRAND_LIGHT if index % 3 == 0 else BRAND_BLUE
            else:
                amplitude = 6 + 5 * (0.5 + 0.5 * math.sin(index * 0.72))
                color = BORDER
            canvas.create_line(x, center - amplitude, x, center + amplitude, fill=color, width=4, capstyle=tk.ROUND)

    def _start_motion(self) -> None:
        self._motion_started = time.monotonic()
        self._motion_frame = 0
        if self._motion_job is not None:
            self.after_cancel(self._motion_job)
        self._animate_motion()

    def _stop_motion(self) -> None:
        if self._motion_job is not None:
            try:
                self.after_cancel(self._motion_job)
            except tk.TclError:
                pass
            self._motion_job = None

    def _animate_motion(self) -> None:
        if not self._busy:
            self._motion_job = None
            return
        elapsed = max(0, int(time.monotonic() - self._motion_started))
        minutes, seconds = divmod(elapsed, 60)
        self.motion_elapsed.set(f"{minutes:02d}:{seconds:02d}")
        self.motion_status.set("Transcrição local em andamento")
        self._motion_frame += 1
        self._draw_waveform()
        self._motion_job = self.after(70, self._animate_motion)

    def _replace_preview(self, value: str) -> None:
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", value)
        self.preview_text.configure(state="disabled")

    def _copy_text(self) -> None:
        value = self.preview_text.get("1.0", "end").strip()
        if not value:
            return
        self.clipboard_clear()
        self.clipboard_append(value)
        self.status_text.set("Texto copiado para a área de transferência.")

    def _show_about(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Sobre o Gentill Transcriber")
        dialog.geometry("640x560")
        dialog.minsize(600, 520)
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()

        shell = tk.Frame(dialog, bg=BG)
        shell.pack(fill="both", expand=True, padx=28, pady=24)

        brand = tk.Frame(shell, bg=BG)
        brand.pack(fill="x")

        mark = tk.Canvas(brand, width=58, height=52, bg=BG, highlightthickness=0)
        mark.pack(side="left", padx=(0, 14))
        bars = [16, 30, 42, 28, 16]
        x = 5
        center = 26
        for index, height in enumerate(bars):
            color = BRAND_LIGHT if index % 2 == 0 else BRAND_BLUE
            mark.create_rectangle(x, center - height / 2, x + 5, center + height / 2, fill=color, outline="")
            x += 8
        mark.create_line(43, 9, 54, 9, 54, 43, 43, 43, fill=BRAND_LIGHT, width=3)
        mark.create_line(44, 19, 52, 19, fill=BRAND_BLUE, width=2)
        mark.create_line(44, 27, 52, 27, fill=BRAND_BLUE, width=2)
        mark.create_line(44, 35, 51, 35, fill=BRAND_BLUE, width=2)

        brand_text = tk.Frame(brand, bg=BG)
        brand_text.pack(side="left", fill="x", expand=True)
        tk.Label(brand_text, text="Gentill Transcriber", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 22)).pack(anchor="w")
        tk.Label(
            brand_text,
            text="ÁUDIO E VÍDEO EM TEXTO • LOCAL • OFFLINE • PRIVADO",
            bg=BG,
            fg=BRAND_LIGHT,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", pady=(2, 0))

        tk.Label(
            shell,
            text="Transcrição local de áudio e vídeo com foco em privacidade, clareza e controle dos seus dados.",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 10),
            justify="left",
            wraplength=560,
        ).pack(anchor="w", pady=(18, 18))

        card = tk.Frame(shell, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x")
        card.grid_columnconfigure(1, weight=1)

        rows = [
            ("Versão", APP_VERSION),
            ("Autoria", f"{ABOUT_AUTHOR} + {ABOUT_ORGANIZATION}"),
            ("GitHub", ABOUT_GITHUB_URL),
            ("Pix de contribuição", ABOUT_PIX_KEY or ABOUT_PIX_STATUS),
        ]
        for row, (label, value) in enumerate(rows):
            tk.Label(card, text=label, bg=CARD, fg=MUTED, font=("Segoe UI Semibold", 9)).grid(
                row=row, column=0, sticky="nw", padx=(16, 18), pady=(14, 14)
            )
            tk.Label(
                card,
                text=value,
                bg=CARD,
                fg=TEXT if value not in ("Não configurado", ABOUT_PIX_STATUS) else BRAND_NEUTRAL,
                font=("Segoe UI", 10),
                justify="left",
                wraplength=390,
            ).grid(row=row, column=1, sticky="w", padx=(0, 16), pady=(14, 14))

        action_bar = tk.Frame(shell, bg=BG)
        action_bar.pack(fill="x", pady=(18, 0))

        github_button = ttk.Button(
            action_bar,
            text="Abrir GitHub",
            style="Secondary.TButton",
            command=self._open_github,
        )
        github_button.pack(side="left")
        if not ABOUT_GITHUB_URL:
            github_button.configure(state="disabled")

        pix_button = ttk.Button(
            action_bar,
            text="Copiar Pix",
            style="Primary.TButton",
            command=self._copy_pix,
        )
        pix_button.pack(side="left", padx=(10, 0))
        if not ABOUT_PIX_KEY:
            pix_button.configure(state="disabled")

        tk.Label(
            shell,
            text="Contribuições são opcionais e ajudam a manter o projeto. O processamento de mídia continua local e offline.",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 9),
            justify="left",
            wraplength=560,
        ).pack(anchor="w", pady=(20, 8))

        ttk.Button(shell, text="Fechar", style="Secondary.TButton", command=dialog.destroy).pack(anchor="e", pady=(12, 0))

    def _open_github(self) -> None:
        if not ABOUT_GITHUB_URL:
            return
        try:
            webbrowser.open(ABOUT_GITHUB_URL, new=2)
        except Exception as exc:
            messagebox.showerror("Não foi possível abrir o GitHub", str(exc))

    def _copy_pix(self) -> None:
        if not ABOUT_PIX_KEY:
            return
        self.clipboard_clear()
        self.clipboard_append(ABOUT_PIX_KEY)
        self.status_text.set("Chave Pix copiada para a área de transferência.")

    def _open_output(self) -> None:
        output_dir = Path(self.output_path.get().strip() or DEFAULT_OUTPUT)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(output_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(output_dir)])
            else:
                subprocess.Popen(["xdg-open", str(output_dir)])
        except OSError as exc:
            messagebox.showerror("Não foi possível abrir a pasta", str(exc))


def _run_packaged_self_test(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="Gentill Transcriber self-test", add_help=False)
    parser.add_argument("--self-test-media", type=Path, required=True)
    parser.add_argument("--self-test-output", type=Path, required=True)
    args = parser.parse_args(argv)

    args.self_test_output.mkdir(parents=True, exist_ok=True)
    error_path = args.self_test_output / "SELF_TEST_ERROR.txt"
    if error_path.exists():
        error_path.unlink()

    try:
        segments, metadata = transcribe(
            input_path=args.self_test_media,
            model_path=DEFAULT_MODEL,
            language="pt",
            device="cpu",
            compute_type="int8",
        )
        write_outputs(args.self_test_output, args.self_test_media.stem, segments, metadata)
    except Exception as exc:
        error_path.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        return 1
    return 0


def main() -> int:
    if "--self-test-media" in sys.argv[1:]:
        return _run_packaged_self_test(sys.argv[1:])

    app = TranscriberApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
