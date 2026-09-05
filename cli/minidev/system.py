from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandStatus:
    name: str
    path: str | None
    version: str | None
    installed: bool
    working: bool
    error: str | None = None


@dataclass(frozen=True)
class SystemInfo:
    os_name: str
    os_release: str
    machine: str
    ram_gb: float


def detect_system() -> SystemInfo:
    return SystemInfo(
        os_name=platform.system() or "Unknown",
        os_release=platform.release() or "Unknown",
        machine=platform.machine() or "Unknown",
        ram_gb=detect_ram_gb(),
    )


def detect_ram_gb() -> float:
    system = platform.system()
    total_bytes: int | None = None

    if system == "Darwin":
        try:
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
            total_bytes = int(out)
        except (OSError, subprocess.SubprocessError, ValueError):
            total_bytes = None
    elif system in {"Linux", "FreeBSD"}:
        if hasattr(os, "sysconf"):
            try:
                total_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
            except (OSError, ValueError):
                total_bytes = None
    elif system == "Windows":
        class MemoryStatus(ctypes.Structure):
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

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            total_bytes = int(status.ullTotalPhys)

    if total_bytes is None:
        return 0.0

    return round(total_bytes / (1024**3), 1)


def pick_model(ram_gb: float) -> str:
    if ram_gb < 16:
        return "qwen2.5-coder:7b"
    if ram_gb <= 32:
        return "qwen2.5-coder:14b"
    return "qwen2.5-coder:32b"


def command_status(command: str, version_args: list[str] | None = None) -> CommandStatus:
    version_args = version_args or ["--version"]
    path = shutil.which(command)
    if path is None:
        return CommandStatus(command, None, None, installed=False, working=False)

    try:
        proc = subprocess.run(
            [path, *version_args],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return CommandStatus(command, path, None, installed=True, working=False, error=str(exc))

    output = (proc.stdout or proc.stderr).strip()
    return CommandStatus(
        command,
        path,
        output.splitlines()[0] if output else None,
        installed=True,
        working=proc.returncode == 0,
        error=None if proc.returncode == 0 else output or f"exit code {proc.returncode}",
    )


def run_command(command: list[str], dry_run: bool = False) -> None:
    if dry_run:
        return
    subprocess.run(command, check=True)


def home_dir() -> Path:
    return Path.home()
