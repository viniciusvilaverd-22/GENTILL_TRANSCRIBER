from __future__ import annotations

import ctypes
import os
import platform
import sys
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class DiagnosticSnapshot:
    os: str
    os_version: str
    architecture: str
    python: str
    cpu: str
    logical_cpus: int | None
    memory_gb: float | None
    frozen: bool

    def as_dict(self) -> dict:
        return asdict(self)


def _memory_gb_windows() -> float | None:
    if os.name != "nt":
        return None

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return round(status.ullTotalPhys / (1024 ** 3), 1)


def snapshot() -> DiagnosticSnapshot:
    cpu = platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "Desconhecida")
    return DiagnosticSnapshot(
        os=platform.system(),
        os_version=platform.version(),
        architecture=platform.machine(),
        python=platform.python_version(),
        cpu=cpu,
        logical_cpus=os.cpu_count(),
        memory_gb=_memory_gb_windows(),
        frozen=bool(getattr(sys, "frozen", False)),
    )


def realtime_factor(media_duration: float | None, elapsed: float | None) -> float | None:
    if not media_duration or not elapsed or elapsed <= 0:
        return None
    return media_duration / elapsed
