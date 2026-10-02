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

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    BaseTk = TkinterDnD.Tk
    DND_AVAILABLE = True
except Exception:
    DND_FILES = None
    BaseTk = tk.Tk
    DND_AVAILABLE = False

from diagnostics import realtime_factor, snapshot as diagnostic_snapshot
from diarization_support import DiarizationUnavailable, diarize_local, is_available as diarization_available
from history_store import HistoryStore
from model_manager import MODEL_REPOS, discover_models, download_model, user_model_root
from transcriber import (
    SUPPORTED_INPUTS,
    Segment,
    TranscriptionCancelled,
    apply_speaker_turns,
    render_txt,
    transcribe,
    write_outputs,
)


SOURCE_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_DIR))
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else SOURCE_DIR
DEFAULT_MODEL = RESOURCE_DIR / "models" / "whisper-small-ct2"
DEFAULT_OUTPUT = Path.home() / "Documents" / "Gentill Transcriber" / "Transcricoes"
APP_ICON = RESOURCE_DIR / "assets" / "gentill_transcriber.ico"
APP_VERSION = "0.4.0-dev"

ABOUT_AUTHOR = "Vinícius Vilaverde"
ABOUT_ORGANIZATION = "Gentill Ops"
ABOUT_GITHUB_URL = "https://github.com/viniciusvilaverd-22/GENTILL_TRANSCRIBER"
ABOUT_PIX_KEY = "eb608e93-1781-49fc-9a70-94cc395dcd53"

BG = "#07162B"
CARD = "#0D2340"
CARD_ALT = "#112D50"
BORDER = "#23456D"
TEXT = "#F8FAFC"
MUTED = "#9FB3CC"
BLUE = "#2563EB"
LIGHT = "#60A5FA"
GREEN = "#10B981"
RED = "#EF4444"
AMBER = "#F59E0B"


def human_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = max(0, int(round(float(seconds))))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}min {secs:02d}s"
    if minutes:
        return f"{minutes:d}min {secs:02d}s"
    return f"{secs:d}s"


def input_filetypes() -> list[tuple[str, str]]:
    media = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_INPUTS))
    return [
        ("Áudio e vídeo suportados", media),
        ("Todos os arquivos", "*.*"),
    ]


def probe_media_duration(path: Path) -> float | None:
    try:
        import av
        with av.open(str(path), mode="r", metadata_errors="ignore") as container:
            if container.duration:
                return float(container.duration / 1_000_000)
            durations = [
                float(stream.duration * stream.time_base)
                for stream in container.streams
                if stream.duration is not None and stream.time_base is not None
            ]
            return max(durations) if durations else None
    except Exception:
        return None


class TranscriberApp(BaseTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Gentill Transcriber {APP_VERSION}")
        self.geometry("1320x860")
        self.minsize(1100, 720)
        self.configure(bg=BG)
        self._apply_window_icon()

        self.output_path = tk.StringVar(value=str(DEFAULT_OUTPUT))
        self.language = tk.StringVar(value="auto")
        self.device = tk.StringVar(value="cpu")
        self.compute_type = tk.StringVar(value="int8")
        self.model_choice = tk.StringVar()
        self.custom_model_path = tk.StringVar()
        self.diarization_enabled = tk.BooleanVar(value=False)
        self.diarization_model_path = tk.StringVar()
        self.status_text = tk.StringVar(value="Pronto")
        self.progress_text = tk.StringVar(value="0%")
        self.time_text = tk.StringVar(value="Tempo: —")
        self.queue_summary = tk.StringVar(value="Nenhum arquivo na fila")

        self.format_vars = {
            "txt": tk.BooleanVar(value=True),
            "srt": tk.BooleanVar(value=True),
            "vtt": tk.BooleanVar(value=True),
            "json": tk.BooleanVar(value=True),
            "docx": tk.BooleanVar(value=True),
        }

        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._queue_items: list[dict] = []
        self._busy = False
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._run_started = 0.0
        self._current_item_started = 0.0
        self._model_paths: dict[str, Path] = {}
        self._history = HistoryStore()

        self._configure_styles()
        self._build_ui()
        self._refresh_models()
        self.after(100, self._drain_events)

    def _apply_window_icon(self) -> None:
        if APP_ICON.is_file():
            try:
                self.iconbitmap(default=str(APP_ICON))
            except tk.TclError:
                pass

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("Soft.TFrame", background=CARD_ALT)
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 24))
        style.configure("Brand.TLabel", background=BG, foreground=LIGHT, font=("Segoe UI Semibold", 24))
        style.configure("Eyebrow.TLabel", background=BG, foreground=LIGHT, font=("Segoe UI Semibold", 9))
        style.configure("Subtitle.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background=CARD, foreground=TEXT, font=("Segoe UI Semibold", 12))
        style.configure("Label.TLabel", background=CARD, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Value.TLabel", background=CARD_ALT, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Status.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Primary.TButton", background=BLUE, foreground="#07111F", borderwidth=0, font=("Segoe UI Semibold", 10), padding=(14, 10))
        style.map("Primary.TButton", background=[("active", LIGHT), ("disabled", BORDER)])
        style.configure("Secondary.TButton", background=CARD_ALT, foreground=TEXT, borderwidth=0, font=("Segoe UI Semibold", 9), padding=(11, 8))
        style.map("Secondary.TButton", background=[("active", BORDER)])
        style.configure("Danger.TButton", background=RED, foreground=TEXT, borderwidth=0, font=("Segoe UI Semibold", 9), padding=(11, 8))
        style.configure("TEntry", fieldbackground=CARD_ALT, foreground=TEXT, insertcolor=TEXT, bordercolor=BORDER, padding=7)
        style.configure("TCombobox", fieldbackground=CARD_ALT, background=CARD_ALT, foreground=TEXT, arrowcolor=MUTED, bordercolor=BORDER, padding=7)
        style.map("TCombobox", fieldbackground=[("readonly", CARD_ALT)], foreground=[("readonly", TEXT)])
        style.configure("Horizontal.TProgressbar", troughcolor=CARD_ALT, background=BLUE, thickness=7)
        style.configure("Treeview", background=CARD_ALT, fieldbackground=CARD_ALT, foreground=TEXT, rowheight=28, borderwidth=0)
        style.configure("Treeview.Heading", background=CARD, foreground=TEXT, relief="flat")
        style.map("Treeview", background=[("selected", BLUE)], foreground=[("selected", TEXT)])
        style.configure("TCheckbutton", background=CARD, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", CARD)], foreground=[("active", TEXT)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=CARD_ALT, foreground=MUTED, padding=(14, 8))
        style.map("TNotebook.Tab", background=[("selected", CARD)], foreground=[("selected", TEXT)])

    def _build_ui(self) -> None:
        shell = ttk.Frame(self, style="App.TFrame", padding=(24, 20, 24, 18))
        shell.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        shell.grid_columnconfigure(1, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        self._build_header(shell)
        self._build_controls(shell)
        self._build_workspace(shell)
        self._build_footer(shell)

    def _build_header(self, shell: ttk.Frame) -> None:
        header = ttk.Frame(shell, style="App.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        header.grid_columnconfigure(0, weight=1)

        title = ttk.Frame(header, style="App.TFrame")
        title.grid(row=0, column=0, sticky="w")
        ttk.Label(title, text="Gentill", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(title, text=" Transcriber", style="Brand.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(title, text="LOCAL • OFFLINE • FILA • LEGENDAS • DOCX", style="Eyebrow.TLabel").grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Label(title, text="Transcreva vários arquivos sem enviar sua mídia para a nuvem.", style="Subtitle.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(3, 0))

        actions = ttk.Frame(header, style="App.TFrame")
        actions.grid(row=0, column=1, rowspan=3, sticky="e")
        ttk.Button(actions, text="Histórico", style="Secondary.TButton", command=self._show_history).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(actions, text="Diagnóstico", style="Secondary.TButton", command=self._show_diagnostics).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(actions, text="Sobre", style="Secondary.TButton", command=self._show_about).grid(row=0, column=2)

    def _build_controls(self, shell: ttk.Frame) -> None:
        controls = ttk.Frame(shell, style="Card.TFrame", padding=18)
        controls.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        controls.grid_columnconfigure(0, weight=1)

        ttk.Label(controls, text="Arquivos", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(controls, text="Arraste arquivos para a área ou selecione vários de uma vez.", style="Label.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 9))

        self.drop_zone = tk.Frame(controls, bg=CARD_ALT, highlightbackground=BORDER, highlightthickness=1, height=82)
        self.drop_zone.grid(row=2, column=0, sticky="ew")
        self.drop_zone.grid_propagate(False)
        tk.Label(
            self.drop_zone,
            text="Solte áudio ou vídeo aqui\nWAV • MP3 • MP4 • M4A • MKV • MOV • FLAC…",
            bg=CARD_ALT,
            fg=TEXT,
            font=("Segoe UI Semibold", 10),
            justify="center",
        ).place(relx=0.5, rely=0.5, anchor="center")

        if DND_AVAILABLE and DND_FILES:
            try:
                self.drop_zone.drop_target_register(DND_FILES)
                self.drop_zone.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

        file_actions = ttk.Frame(controls, style="Card.TFrame")
        file_actions.grid(row=3, column=0, sticky="ew", pady=(9, 15))
        ttk.Button(file_actions, text="Adicionar arquivos", style="Secondary.TButton", command=self._pick_inputs).pack(side="left")
        ttk.Button(file_actions, text="Limpar fila", style="Secondary.TButton", command=self._clear_queue).pack(side="left", padx=(8, 0))

        ttk.Label(controls, text="Modelo", style="CardTitle.TLabel").grid(row=4, column=0, sticky="w")
        model_line = ttk.Frame(controls, style="Card.TFrame")
        model_line.grid(row=5, column=0, sticky="ew", pady=(7, 4))
        model_line.grid_columnconfigure(0, weight=1)
        self.model_combo = ttk.Combobox(model_line, textvariable=self.model_choice, state="readonly")
        self.model_combo.grid(row=0, column=0, sticky="ew")
        ttk.Button(model_line, text="Atualizar", style="Secondary.TButton", command=self._refresh_models).grid(row=0, column=1, padx=(7, 0))
        ttk.Button(model_line, text="Baixar…", style="Secondary.TButton", command=self._show_model_manager).grid(row=0, column=2, padx=(7, 0))

        custom_line = ttk.Frame(controls, style="Card.TFrame")
        custom_line.grid(row=6, column=0, sticky="ew", pady=(4, 12))
        custom_line.grid_columnconfigure(0, weight=1)
        ttk.Entry(custom_line, textvariable=self.custom_model_path).grid(row=0, column=0, sticky="ew")
        ttk.Button(custom_line, text="Modelo local…", style="Secondary.TButton", command=self._pick_model).grid(row=0, column=1, padx=(7, 0))

        settings = ttk.Frame(controls, style="Card.TFrame")
        settings.grid(row=7, column=0, sticky="ew")
        for column in (0, 1, 2):
            settings.grid_columnconfigure(column, weight=1)
        self._combo_field(settings, "Idioma", self.language, ("auto", "pt", "en", "es"), 0)
        self._combo_field(settings, "Dispositivo", self.device, ("cpu", "auto", "cuda"), 1)
        self._combo_field(settings, "Precisão", self.compute_type, ("int8", "float32", "float16"), 2)

        ttk.Label(controls, text="Saídas", style="CardTitle.TLabel").grid(row=8, column=0, sticky="w", pady=(14, 5))
        outputs = ttk.Frame(controls, style="Card.TFrame")
        outputs.grid(row=9, column=0, sticky="ew")
        for col, key in enumerate(("txt", "srt", "vtt", "json", "docx")):
            ttk.Checkbutton(outputs, text=key.upper(), variable=self.format_vars[key]).grid(row=0, column=col, sticky="w", padx=(0, 8))

        ttk.Label(controls, text="Pasta de saída", style="Label.TLabel").grid(row=10, column=0, sticky="w", pady=(13, 4))
        output_line = ttk.Frame(controls, style="Card.TFrame")
        output_line.grid(row=11, column=0, sticky="ew")
        output_line.grid_columnconfigure(0, weight=1)
        ttk.Entry(output_line, textvariable=self.output_path).grid(row=0, column=0, sticky="ew")
        ttk.Button(output_line, text="…", style="Secondary.TButton", width=3, command=self._pick_output).grid(row=0, column=1, padx=(7, 0))

        dia = ttk.Frame(controls, style="Card.TFrame")
        dia.grid(row=12, column=0, sticky="ew", pady=(14, 0))
        dia.grid_columnconfigure(0, weight=1)
        ttk.Checkbutton(
            dia,
            text="Diarização local (experimental)",
            variable=self.diarization_enabled,
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(dia, text="Pipeline…", style="Secondary.TButton", command=self._pick_diarization_model).grid(row=0, column=1)
        ttk.Label(
            controls,
            text="Requer pyannote.audio + pipeline local. Nenhum download é iniciado automaticamente.",
            style="Label.TLabel",
            wraplength=380,
        ).grid(row=13, column=0, sticky="w", pady=(4, 0))

        action = ttk.Frame(controls, style="Card.TFrame")
        action.grid(row=14, column=0, sticky="ew", pady=(18, 0))
        action.grid_columnconfigure(0, weight=1)
        self.start_button = ttk.Button(action, text="Transcrever fila", style="Primary.TButton", command=self._start_queue)
        self.start_button.grid(row=0, column=0, sticky="ew")
        self.pause_button = ttk.Button(action, text="Pausar", style="Secondary.TButton", command=self._toggle_pause, state="disabled")
        self.pause_button.grid(row=0, column=1, padx=(8, 0))
        self.cancel_button = ttk.Button(action, text="Cancelar", style="Danger.TButton", command=self._cancel_run, state="disabled")
        self.cancel_button.grid(row=0, column=2, padx=(8, 0))

    def _combo_field(self, parent: ttk.Frame, label: str, variable: tk.StringVar, values: tuple[str, ...], column: int) -> None:
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 5, 0))
        frame.grid_columnconfigure(0, weight=1)
        ttk.Label(frame, text=label, style="Label.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Combobox(frame, textvariable=variable, values=values, state="readonly").grid(row=1, column=0, sticky="ew")

    def _build_workspace(self, shell: ttk.Frame) -> None:
        workspace = ttk.Frame(shell, style="Card.TFrame", padding=14)
        workspace.grid(row=1, column=1, sticky="nsew")
        workspace.grid_rowconfigure(0, weight=1)
        workspace.grid_columnconfigure(0, weight=1)

        notebook = ttk.Notebook(workspace)
        notebook.grid(row=0, column=0, sticky="nsew")

        queue_tab = ttk.Frame(notebook, style="Card.TFrame", padding=10)
        result_tab = ttk.Frame(notebook, style="Card.TFrame", padding=10)
        notebook.add(queue_tab, text="Fila")
        notebook.add(result_tab, text="Resultado")

        queue_tab.grid_rowconfigure(1, weight=1)
        queue_tab.grid_columnconfigure(0, weight=1)
        ttk.Label(queue_tab, textvariable=self.queue_summary, style="Label.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))

        columns = ("status", "file", "duration", "progress")
        self.queue_tree = ttk.Treeview(queue_tab, columns=columns, show="headings")
        self.queue_tree.heading("status", text="Status")
        self.queue_tree.heading("file", text="Arquivo")
        self.queue_tree.heading("duration", text="Duração")
        self.queue_tree.heading("progress", text="Progresso")
        self.queue_tree.column("status", width=110, anchor="w")
        self.queue_tree.column("file", width=390, anchor="w")
        self.queue_tree.column("duration", width=100, anchor="center")
        self.queue_tree.column("progress", width=100, anchor="center")
        self.queue_tree.grid(row=1, column=0, sticky="nsew")
        qscroll = ttk.Scrollbar(queue_tab, orient="vertical", command=self.queue_tree.yview)
        qscroll.grid(row=1, column=1, sticky="ns")
        self.queue_tree.configure(yscrollcommand=qscroll.set)

        result_tab.grid_rowconfigure(1, weight=1)
        result_tab.grid_columnconfigure(0, weight=1)
        result_actions = ttk.Frame(result_tab, style="Card.TFrame")
        result_actions.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(result_actions, text="Copiar texto", style="Secondary.TButton", command=self._copy_text).pack(side="left")
        ttk.Button(result_actions, text="Abrir saída", style="Secondary.TButton", command=self._open_output).pack(side="left", padx=(8, 0))

        self.preview_text = tk.Text(
            result_tab,
            bg=CARD_ALT,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground=BLUE,
            selectforeground=TEXT,
            relief="flat",
            borderwidth=0,
            wrap="word",
            padx=16,
            pady=14,
            font=("Segoe UI", 11),
        )
        self.preview_text.grid(row=1, column=0, sticky="nsew")
        self.preview_text.insert("1.0", "A transcrição concluída aparecerá aqui.")
        self.preview_text.configure(state="disabled")
        rscroll = ttk.Scrollbar(result_tab, orient="vertical", command=self.preview_text.yview)
        rscroll.grid(row=1, column=1, sticky="ns")
        self.preview_text.configure(yscrollcommand=rscroll.set)

    def _build_footer(self, shell: ttk.Frame) -> None:
        footer = ttk.Frame(shell, style="App.TFrame")
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        footer.grid_columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_text, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(footer, textvariable=self.time_text, style="Status.TLabel").grid(row=0, column=1, sticky="e", padx=(0, 12))
        self.progress = ttk.Progressbar(footer, mode="determinate", maximum=100, value=0, style="Horizontal.TProgressbar", length=250)
        self.progress.grid(row=0, column=2, sticky="e")
        ttk.Label(footer, textvariable=self.progress_text, style="Status.TLabel").grid(row=0, column=3, sticky="e", padx=(8, 0))

    def _on_drop(self, event) -> None:
        try:
            paths = [Path(item) for item in self.tk.splitlist(event.data)]
        except Exception:
            return
        self._add_paths(paths)

    def _pick_inputs(self) -> None:
        selected = filedialog.askopenfilenames(title="Adicionar áudio ou vídeo", filetypes=input_filetypes())
        self._add_paths(Path(item) for item in selected)

    def _add_paths(self, paths) -> None:
        existing = {item["path"].resolve() for item in self._queue_items}
        added = 0
        for raw in paths:
            path = Path(raw)
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_INPUTS:
                continue
            resolved = path.resolve()
            if resolved in existing:
                continue
            duration = probe_media_duration(path)
            item = {
                "path": path,
                "duration": duration,
                "status": "Na fila",
                "progress": 0.0,
                "tree_id": "",
            }
            tree_id = self.queue_tree.insert(
                "",
                "end",
                values=("Na fila", path.name, human_duration(duration), "0%"),
            )
            item["tree_id"] = tree_id
            self._queue_items.append(item)
            existing.add(resolved)
            added += 1
        self._refresh_queue_summary()
        if added:
            self.status_text.set(f"{added} arquivo(s) adicionado(s).")

    def _clear_queue(self) -> None:
        if self._busy:
            messagebox.showinfo("Fila em execução", "Cancele a execução antes de limpar a fila.")
            return
        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)
        self._queue_items.clear()
        self._refresh_queue_summary()
        self.progress.configure(value=0)
        self.progress_text.set("0%")

    def _refresh_queue_summary(self) -> None:
        total = len(self._queue_items)
        pending = sum(1 for item in self._queue_items if item["status"] == "Na fila")
        done = sum(1 for item in self._queue_items if item["status"] == "Concluído")
        self.queue_summary.set(f"{total} arquivo(s) • {pending} pendente(s) • {done} concluído(s)")

    def _pick_output(self) -> None:
        selected = filedialog.askdirectory(title="Pasta de saída", initialdir=self.output_path.get() or str(APP_DIR))
        if selected:
            self.output_path.set(selected)

    def _pick_model(self) -> None:
        selected = filedialog.askdirectory(title="Modelo CTranslate2 local", initialdir=self.custom_model_path.get() or str(APP_DIR))
        if selected:
            self.custom_model_path.set(selected)

    def _pick_diarization_model(self) -> None:
        selected = filedialog.askdirectory(title="Pipeline local de diarização", initialdir=self.diarization_model_path.get() or str(APP_DIR))
        if selected:
            self.diarization_model_path.set(selected)

    def _refresh_models(self) -> None:
        roots = [RESOURCE_DIR / "models", APP_DIR / "models", user_model_root()]
        found = discover_models(*roots)
        self._model_paths = {}
        labels = []
        for name, path in sorted(found.items()):
            label = f"{name} — {path}"
            labels.append(label)
            self._model_paths[label] = path
        self.model_combo["values"] = labels
        if labels and self.model_choice.get() not in labels:
            preferred = next((label for label in labels if "small" in label.lower()), labels[0])
            self.model_choice.set(preferred)

    def _selected_model_path(self) -> Path:
        custom = self.custom_model_path.get().strip()
        if custom:
            return Path(custom)
        label = self.model_choice.get()
        if label in self._model_paths:
            return self._model_paths[label]
        return DEFAULT_MODEL

    def _show_model_manager(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Gerenciar modelos")
        dialog.geometry("520x340")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()

        shell = tk.Frame(dialog, bg=BG)
        shell.pack(fill="both", expand=True, padx=20, pady=18)
        tk.Label(shell, text="Modelos Whisper locais", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 16)).pack(anchor="w")
        tk.Label(
            shell,
            text="O download só ocorre quando você clicar em Baixar. Depois disso o modelo funciona offline.",
            bg=BG, fg=MUTED, justify="left", wraplength=470, font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(4, 14))

        for name in MODEL_REPOS:
            row = tk.Frame(shell, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=name.upper(), bg=CARD, fg=TEXT, font=("Segoe UI Semibold", 10), width=12, anchor="w").pack(side="left", padx=12, pady=10)
            tk.Label(row, text=MODEL_REPOS[name], bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True)
            ttk.Button(row, text="Baixar", style="Secondary.TButton", command=lambda n=name: self._download_model_async(n, dialog)).pack(side="right", padx=10)

    def _download_model_async(self, name: str, dialog: tk.Toplevel) -> None:
        self.status_text.set(f"Baixando modelo {name}…")
        dialog.destroy()

        def worker() -> None:
            try:
                path = download_model(name)
                self._events.put(("model_download_done", (name, path)))
            except Exception as exc:
                self._events.put(("model_download_error", (name, str(exc))))

        threading.Thread(target=worker, daemon=True).start()

    def _selected_formats(self) -> set[str]:
        selected = {name for name, variable in self.format_vars.items() if variable.get()}
        return selected or {"txt"}

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.start_button.configure(state="disabled" if busy else "normal")
        self.pause_button.configure(state="normal" if busy else "disabled", text="Pausar")
        self.cancel_button.configure(state="normal" if busy else "disabled")
        if not busy:
            self._pause_event.clear()

    def _start_queue(self) -> None:
        if self._busy:
            return
        pending = [item for item in self._queue_items if item["status"] in {"Na fila", "Falhou", "Cancelado"}]
        if not pending:
            messagebox.showinfo("Fila vazia", "Adicione arquivos ou limpe/recrie a fila.")
            return

        model_path = self._selected_model_path()
        if not model_path.is_dir():
            messagebox.showerror("Modelo não encontrado", f"Modelo local não encontrado:\n{model_path}")
            return

        if self.diarization_enabled.get():
            if not diarization_available():
                messagebox.showwarning(
                    "Diarização indisponível",
                    "pyannote.audio não está instalado nesta build. A transcrição seguirá sem diarização.",
                )
                self.diarization_enabled.set(False)
            elif not Path(self.diarization_model_path.get().strip()).is_dir():
                messagebox.showerror("Pipeline ausente", "Escolha um pipeline local de diarização.")
                return

        self._cancel_event.clear()
        self._pause_event.clear()
        self._run_started = time.perf_counter()
        self._set_busy(True)
        self.status_text.set("Processando fila…")
        self.progress.configure(value=0)
        self.progress_text.set("0%")

        config = {
            "model_path": model_path,
            "output_dir": Path(self.output_path.get().strip() or DEFAULT_OUTPUT),
            "language": None if self.language.get() == "auto" else self.language.get(),
            "device": self.device.get(),
            "compute_type": self.compute_type.get(),
            "formats": self._selected_formats(),
            "diarization": self.diarization_enabled.get(),
            "diarization_model": Path(self.diarization_model_path.get().strip()) if self.diarization_model_path.get().strip() else None,
        }
        threading.Thread(target=self._queue_worker, args=(config,), daemon=True).start()

    def _queue_worker(self, config: dict) -> None:
        candidates = [item for item in self._queue_items if item["status"] in {"Na fila", "Falhou", "Cancelado"}]
        for item in candidates:
            if self._cancel_event.is_set():
                break
            input_path: Path = item["path"]
            self._current_item_started = time.perf_counter()
            self._events.put(("item_started", item))

            def callback(fraction: float, duration: float | None, segment: Segment) -> None:
                elapsed = time.perf_counter() - self._current_item_started
                remaining = (elapsed / fraction - elapsed) if fraction > 0.01 else None
                self._events.put(("progress", (item, fraction, duration, segment.end, remaining)))

            try:
                segments, metadata = transcribe(
                    input_path=input_path,
                    model_path=config["model_path"],
                    language=config["language"],
                    device=config["device"],
                    compute_type=config["compute_type"],
                    progress_callback=callback,
                    cancel_event=self._cancel_event,
                    pause_event=self._pause_event,
                )

                if config["diarization"] and config["diarization_model"]:
                    self._events.put(("status", "Executando diarização local…"))
                    turns = diarize_local(input_path, config["diarization_model"])
                    segments = apply_speaker_turns(segments, turns)
                    metadata["diarization"] = "pyannote-local"
                else:
                    metadata["diarization"] = "disabled"

                written = write_outputs(
                    config["output_dir"],
                    input_path.stem,
                    segments,
                    metadata,
                    formats=config["formats"],
                )
                elapsed = time.perf_counter() - self._current_item_started
                self._history.add(
                    input_path=input_path,
                    output_dir=config["output_dir"],
                    model=config["model_path"],
                    language=config["language"],
                    duration=metadata.get("duration"),
                    elapsed=elapsed,
                    status="PASS",
                )
                self._events.put(("item_done", (item, segments, metadata, written, elapsed)))
            except TranscriptionCancelled:
                elapsed = time.perf_counter() - self._current_item_started
                self._history.add(
                    input_path=input_path,
                    output_dir=config["output_dir"],
                    model=config["model_path"],
                    language=config["language"],
                    duration=item.get("duration"),
                    elapsed=elapsed,
                    status="CANCELLED",
                )
                self._events.put(("item_cancelled", item))
                break
            except DiarizationUnavailable as exc:
                self._events.put(("item_error", (item, f"Diarização: {exc}")))
            except Exception as exc:
                elapsed = time.perf_counter() - self._current_item_started
                self._history.add(
                    input_path=input_path,
                    output_dir=config["output_dir"],
                    model=config["model_path"],
                    language=config["language"],
                    duration=item.get("duration"),
                    elapsed=elapsed,
                    status="FAIL",
                )
                self._events.put(("item_error", (item, str(exc))))

        self._events.put(("run_finished", None))

    def _toggle_pause(self) -> None:
        if not self._busy:
            return
        if self._pause_event.is_set():
            self._pause_event.clear()
            self.pause_button.configure(text="Pausar")
            self.status_text.set("Retomando…")
        else:
            self._pause_event.set()
            self.pause_button.configure(text="Retomar")
            self.status_text.set("Pausado")

    def _cancel_run(self) -> None:
        if not self._busy:
            return
        self._cancel_event.set()
        self._pause_event.clear()
        self.status_text.set("Cancelando…")

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "item_started":
                    item = payload
                    item["status"] = "Processando"
                    self._update_tree_item(item, progress=0)
                    self.progress.configure(value=0)
                    self.progress_text.set("0%")
                    self.status_text.set(f"Transcrevendo {item['path'].name}")
                elif kind == "progress":
                    item, fraction, duration, processed, remaining = payload
                    percent = int(round(fraction * 100))
                    item["progress"] = fraction
                    self._update_tree_item(item, progress=percent)
                    self.progress.configure(value=percent)
                    self.progress_text.set(f"{percent}%")
                    if duration:
                        self.time_text.set(
                            f"{human_duration(processed)} / {human_duration(duration)}"
                            + (f" • restante ~{human_duration(remaining)}" if remaining else "")
                        )
                elif kind == "item_done":
                    item, segments, metadata, written, elapsed = payload
                    item["status"] = "Concluído"
                    item["progress"] = 1.0
                    self._update_tree_item(item, progress=100)
                    self._replace_preview(render_txt(segments))
                    factor = realtime_factor(metadata.get("duration"), elapsed)
                    self.status_text.set(
                        f"Concluído: {item['path'].name}"
                        + (f" • {factor:.2f}x tempo real" if factor else "")
                    )
                    self.time_text.set(f"Tempo: {human_duration(elapsed)}")
                    self._refresh_queue_summary()
                elif kind == "item_error":
                    item, error = payload
                    item["status"] = "Falhou"
                    self._update_tree_item(item, progress=int(item.get("progress", 0) * 100))
                    self.status_text.set(f"Falhou: {item['path'].name}")
                    messagebox.showerror("Erro na transcrição", f"{item['path']}\n\n{error}")
                    self._refresh_queue_summary()
                elif kind == "item_cancelled":
                    item = payload
                    item["status"] = "Cancelado"
                    self._update_tree_item(item, progress=int(item.get("progress", 0) * 100))
                    self._refresh_queue_summary()
                elif kind == "run_finished":
                    self._set_busy(False)
                    total_elapsed = time.perf_counter() - self._run_started if self._run_started else 0
                    self.time_text.set(f"Fila: {human_duration(total_elapsed)}")
                    if self._cancel_event.is_set():
                        self.status_text.set("Execução cancelada")
                    else:
                        self.status_text.set("Fila concluída")
                elif kind == "status":
                    self.status_text.set(str(payload))
                elif kind == "model_download_done":
                    name, path = payload
                    self.status_text.set(f"Modelo {name} disponível offline.")
                    self._refresh_models()
                    match = next((label for label, model_path in self._model_paths.items() if model_path.resolve() == Path(path).resolve()), None)
                    if match:
                        self.model_choice.set(match)
                elif kind == "model_download_error":
                    name, error = payload
                    messagebox.showerror("Falha no download do modelo", f"{name}: {error}")
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _update_tree_item(self, item: dict, progress: int) -> None:
        self.queue_tree.item(
            item["tree_id"],
            values=(
                item["status"],
                item["path"].name,
                human_duration(item.get("duration")),
                f"{progress}%",
            ),
        )

    def _replace_preview(self, text: str) -> None:
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", text)
        self.preview_text.configure(state="disabled")

    def _copy_text(self) -> None:
        text = self.preview_text.get("1.0", "end").strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_text.set("Texto copiado.")

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

    def _show_history(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Histórico local")
        dialog.geometry("900x480")
        dialog.configure(bg=BG)
        dialog.transient(self)

        shell = ttk.Frame(dialog, style="Card.TFrame", padding=14)
        shell.pack(fill="both", expand=True)
        shell.grid_rowconfigure(1, weight=1)
        shell.grid_columnconfigure(0, weight=1)

        header = ttk.Frame(shell, style="Card.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text="Histórico local", style="CardTitle.TLabel").pack(side="left")
        ttk.Button(header, text="Limpar histórico", style="Danger.TButton", command=lambda: self._clear_history(dialog)).pack(side="right")

        tree = ttk.Treeview(shell, columns=("date", "file", "elapsed", "factor", "status"), show="headings")
        for key, title, width in (
            ("date", "Data", 180),
            ("file", "Arquivo", 340),
            ("elapsed", "Tempo", 90),
            ("factor", "Velocidade", 90),
            ("status", "Status", 90),
        ):
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor="w")

        entries = self._history.recent()
        for entry in entries:
            factor = realtime_factor(entry.duration, entry.elapsed)
            tree.insert(
                "",
                "end",
                iid=str(entry.id),
                values=(
                    entry.created_at.replace("T", " ")[:19],
                    Path(entry.input_path).name,
                    human_duration(entry.elapsed),
                    f"{factor:.2f}x" if factor else "—",
                    entry.status,
                ),
            )
        tree.grid(row=1, column=0, sticky="nsew")

    def _clear_history(self, dialog: tk.Toplevel) -> None:
        if messagebox.askyesno("Limpar histórico", "Remover apenas o histórico local? Os arquivos transcritos não serão apagados."):
            self._history.clear()
            dialog.destroy()
            self._show_history()

    def _show_diagnostics(self) -> None:
        diag = diagnostic_snapshot()
        recent = self._history.recent(1)
        last = recent[0] if recent else None
        factor = realtime_factor(last.duration, last.elapsed) if last else None

        dialog = tk.Toplevel(self)
        dialog.title("Diagnóstico")
        dialog.geometry("600x470")
        dialog.configure(bg=BG)
        dialog.transient(self)

        shell = tk.Frame(dialog, bg=BG)
        shell.pack(fill="both", expand=True, padx=22, pady=20)
        tk.Label(shell, text="Diagnóstico do sistema", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 17)).pack(anchor="w")

        rows = [
            ("Sistema", f"{diag.os} {diag.os_version}"),
            ("Arquitetura", diag.architecture),
            ("CPU", diag.cpu),
            ("CPUs lógicas", str(diag.logical_cpus or "—")),
            ("RAM", f"{diag.memory_gb:.1f} GB" if diag.memory_gb else "—"),
            ("Python", diag.python),
            ("Executável empacotado", "Sim" if diag.frozen else "Não"),
            ("Backend atual", f"{self.device.get()} / {self.compute_type.get()}"),
            ("Modelo", str(self._selected_model_path())),
            ("Último benchmark", f"{factor:.2f}x tempo real" if factor else "Sem dados"),
        ]

        card = tk.Frame(shell, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(14, 0))
        for label, value in rows:
            line = tk.Frame(card, bg=CARD)
            line.pack(fill="x", padx=14, pady=7)
            tk.Label(line, text=label, bg=CARD, fg=MUTED, width=22, anchor="w", font=("Segoe UI Semibold", 9)).pack(side="left")
            tk.Label(line, text=value, bg=CARD, fg=TEXT, anchor="w", justify="left", wraplength=340, font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True)

    def _show_about(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Sobre — Gentill Transcriber")
        dialog.geometry("650x480")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()

        shell = tk.Frame(dialog, bg=BG)
        shell.pack(fill="both", expand=True, padx=28, pady=24)
        tk.Label(shell, text="Gentill Transcriber", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 22)).pack(anchor="w")
        tk.Label(shell, text=f"Versão {APP_VERSION} • local • offline • privado", bg=BG, fg=LIGHT, font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(3, 16))

        card = tk.Frame(shell, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x")
        for label, value in (
            ("Autoria", f"{ABOUT_AUTHOR} + {ABOUT_ORGANIZATION}"),
            ("GitHub", ABOUT_GITHUB_URL),
            ("Pix", ABOUT_PIX_KEY),
            ("Drag-and-drop", "Disponível" if DND_AVAILABLE else "Fallback por seletor de arquivos"),
            ("Diarização", "Disponível" if diarization_available() else "Opcional — pyannote.audio local"),
        ):
            line = tk.Frame(card, bg=CARD)
            line.pack(fill="x", padx=14, pady=8)
            tk.Label(line, text=label, bg=CARD, fg=MUTED, width=15, anchor="w", font=("Segoe UI Semibold", 9)).pack(side="left")
            tk.Label(line, text=value, bg=CARD, fg=TEXT, anchor="w", wraplength=420, justify="left", font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True)

        actions = tk.Frame(shell, bg=BG)
        actions.pack(fill="x", pady=(16, 0))
        ttk.Button(actions, text="Abrir GitHub", style="Secondary.TButton", command=lambda: webbrowser.open(ABOUT_GITHUB_URL, new=2)).pack(side="left")
        ttk.Button(actions, text="Copiar Pix", style="Primary.TButton", command=self._copy_pix).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Fechar", style="Secondary.TButton", command=dialog.destroy).pack(side="right")

    def _copy_pix(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(ABOUT_PIX_KEY)
        self.status_text.set("Chave Pix copiada.")


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
        write_outputs(
            args.self_test_output,
            args.self_test_media.stem,
            segments,
            metadata,
            formats={"txt", "json", "srt", "vtt", "docx"},
        )
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
