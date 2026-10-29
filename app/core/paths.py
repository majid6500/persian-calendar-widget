"""Filesystem locations for bundled resources and per-user configuration."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_root() -> Path:
    """Directory that contains ``assets/`` and ``data/``."""
    if getattr(sys, "frozen", False):
        # PyInstaller onedir puts data files beside the executable and also
        # exposes them through _MEIPASS.
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


def data_path(*parts: str) -> Path:
    return resource_path("data", *parts)


def assets_path(*parts: str) -> Path:
    return resource_path("assets", *parts)


def _config_base() -> Path:
    override = os.environ.get("PCW_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "PersianCalendarWidget"
    # Portable / non-Windows fallback.  Never the installation directory.
    return Path.home() / ".config" / "PersianCalendarWidget"


def config_dir() -> Path:
    path = _config_base()
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_file(name: str = "settings.ini") -> Path:
    return config_dir() / name


def log_file(name: str = "error.log") -> Path:
    return config_dir() / name
