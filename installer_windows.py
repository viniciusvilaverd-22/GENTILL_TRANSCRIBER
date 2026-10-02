from __future__ import annotations

import argparse
import os
import shutil
import sys
import tkinter as tk
import winreg
from pathlib import Path
from tkinter import messagebox, ttk


APP_NAME = "Gentill Transcriber"
APP_VERSION = "0.4.0-rc1"
SOURCE_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_DIR))
PAYLOAD = RESOURCE_DIR / "payload" / APP_NAME
UNINSTALLER = RESOURCE_DIR / "tools" / "Gentill Transcriber Uninstall.exe"
ICON = RESOURCE_DIR / "assets" / "gentill_transcriber.ico"


def default_install_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return root / "Programs" / APP_NAME


def _shortcut(path: Path, target: Path, icon: Path) -> None:
    try:
        import win32com.client
    except ImportError as exc:
        raise RuntimeError("pywin32 não está disponível para criar atalhos.") from exc

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortcut(str(path))
    shortcut.TargetPath = str(target)
    shortcut.WorkingDirectory = str(target.parent)
    shortcut.IconLocation = str(icon)
    shortcut.Save()


def _register_uninstall(target: Path) -> None:
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\GentillTranscriber"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Vinícius Vilaverde + Gentill Ops")
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(target))
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(target / f"{APP_NAME}.exe"))
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{target / "Gentill Transcriber Uninstall.exe"}"')
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)


def install(target: Path, desktop_shortcut: bool = True) -> None:
    if not (PAYLOAD / f"{APP_NAME}.exe").is_file():
        raise RuntimeError("Payload do aplicativo não foi encontrado no instalador.")
    if not UNINSTALLER.is_file():
        raise RuntimeError("Desinstalador não foi encontrado no instalador.")

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f".{target.name}.installing"
    backup = target.parent / f".{target.name}.backup"
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(backup, ignore_errors=True)

    shutil.copytree(PAYLOAD, staging)
    shutil.copy2(UNINSTALLER, staging / "Gentill Transcriber Uninstall.exe")

    if target.exists():
        target.replace(backup)
    try:
        staging.replace(target)
    except Exception:
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        if backup.exists():
            backup.replace(target)
        raise

    shutil.rmtree(backup, ignore_errors=True)

    start_menu = Path(os.environ.get("APPDATA", Path.home())) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Gentill Transcriber"
    start_menu.mkdir(parents=True, exist_ok=True)
    _shortcut(start_menu / "Gentill Transcriber.lnk", target / f"{APP_NAME}.exe", target / f"{APP_NAME}.exe")

    if desktop_shortcut:
        desktop = Path.home() / "Desktop"
        if desktop.exists():
            _shortcut(desktop / "Gentill Transcriber.lnk", target / f"{APP_NAME}.exe", target / f"{APP_NAME}.exe")

    _register_uninstall(target)


def self_test() -> int:
    required = [
        PAYLOAD / f"{APP_NAME}.exe",
        PAYLOAD / "_internal" / "models" / "whisper-small-ct2" / "model.bin",
        UNINSTALLER,
        ICON,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        print("INSTALLER_SELF_TEST=FAIL")
        for path in missing:
            print(f"MISSING={path}")
        return 1
    print("INSTALLER_SELF_TEST=PASS")
    return 0


class InstallerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Instalar Gentill Transcriber")
        self.geometry("620x390")
        self.resizable(False, False)
        self.configure(bg="#07162B")
        if ICON.is_file():
            try:
                self.iconbitmap(default=str(ICON))
            except tk.TclError:
                pass

        self.path = tk.StringVar(value=str(default_install_dir()))
        self.desktop = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Pronto para instalar.")

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#07162B")
        style.configure("TLabel", background="#07162B", foreground="#F8FAFC")
        style.configure("TCheckbutton", background="#07162B", foreground="#F8FAFC")
        style.configure("Primary.TButton", background="#2563EB", foreground="#07111F", padding=(15, 10))

        frame = ttk.Frame(self, padding=28)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Gentill Transcriber", font=("Segoe UI Semibold", 22)).pack(anchor="w")
        ttk.Label(frame, text="Instalação por usuário • sem privilégios de administrador", foreground="#9FB3CC").pack(anchor="w", pady=(3, 22))

        ttk.Label(frame, text="Pasta de instalação").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.path, width=70).pack(fill="x", pady=(6, 12))
        ttk.Checkbutton(frame, text="Criar atalho na Área de Trabalho", variable=self.desktop).pack(anchor="w")
        ttk.Label(
            frame,
            text="O aplicativo e o modelo Whisper local serão instalados juntos. O processamento permanece offline.",
            foreground="#9FB3CC",
            wraplength=540,
        ).pack(anchor="w", pady=(18, 18))

        ttk.Label(frame, textvariable=self.status, foreground="#60A5FA").pack(anchor="w", pady=(0, 10))
        self.button = ttk.Button(frame, text="Instalar", style="Primary.TButton", command=self._install)
        self.button.pack(anchor="e")

    def _install(self) -> None:
        target = Path(self.path.get().strip())
        self.button.configure(state="disabled")
        self.status.set("Instalando…")
        self.update_idletasks()
        try:
            install(target, self.desktop.get())
        except Exception as exc:
            self.button.configure(state="normal")
            self.status.set("Falha na instalação.")
            messagebox.showerror("Falha na instalação", str(exc))
            return
        self.status.set("Instalação concluída.")
        messagebox.showinfo("Gentill Transcriber", "Instalação concluída com sucesso.")
        self.destroy()


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--self-test", action="store_true")
    args, _ = parser.parse_known_args()
    if args.self_test:
        return self_test()

    app = InstallerApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
