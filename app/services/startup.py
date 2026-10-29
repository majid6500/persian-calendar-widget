"""Optional per-user Windows startup integration.

Only one value, named ``PersianCalendarWidget``, is ever created or removed
under ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``.  No
administrator rights are required and unrelated entries are never touched.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "PersianCalendarWidget"


def application_command() -> str:
    """Command line that relaunches this application."""
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([sys.executable])
    executable = Path(sys.executable)
    pythonw = executable.with_name("pythonw.exe")
    launcher = pythonw if pythonw.is_file() else executable
    script = Path(__file__).resolve().parents[2] / "main.py"
    return subprocess.list2cmdline([str(launcher), str(script)])


class StartupManager:
    def __init__(
        self,
        value_name: str = VALUE_NAME,
        run_key: str = RUN_KEY,
        command: str | None = None,
    ) -> None:
        self.value_name = value_name
        self.run_key = run_key
        self.command = command or application_command()

    @property
    def supported(self) -> bool:
        return sys.platform == "win32" and os.name == "nt"

    def is_enabled(self) -> bool:
        if not self.supported:
            return False
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self.run_key, 0, winreg.KEY_READ
            ) as key:
                winreg.QueryValueEx(key, self.value_name)
                return True
        except FileNotFoundError:
            return False
        except OSError:
            return False

    def current_command(self) -> str | None:
        if not self.supported:
            return None
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self.run_key, 0, winreg.KEY_READ
            ) as key:
                value, _ = winreg.QueryValueEx(key, self.value_name)
                return str(value)
        except (FileNotFoundError, OSError):
            return None

    def set_enabled(self, enabled: bool) -> tuple[bool, str]:
        if not self.supported:
            return False, "راه‌اندازی خودکار فقط در ویندوز پشتیبانی می‌شود."
        import winreg

        try:
            if enabled:
                with winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER,
                    self.run_key,
                    0,
                    winreg.KEY_SET_VALUE,
                ) as key:
                    winreg.SetValueEx(
                        key, self.value_name, 0, winreg.REG_SZ, self.command
                    )
                return True, "برنامه هنگام ورود به ویندوز اجرا می‌شود."
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    self.run_key,
                    0,
                    winreg.KEY_SET_VALUE,
                ) as key:
                    winreg.DeleteValue(key, self.value_name)
            except FileNotFoundError:
                pass
            return True, "راه‌اندازی خودکار غیرفعال شد."
        except OSError as exc:
            return False, f"تغییر تنظیمات راه‌اندازی ممکن نشد: {exc}"

    def sync(self, enabled: bool) -> tuple[bool, str]:
        """Make the registry match the saved setting, idempotently."""
        if not self.supported:
            return False, "راه‌اندازی خودکار فقط در ویندوز پشتیبانی می‌شود."
        if enabled:
            if self.current_command() == self.command:
                return True, ""
            return self.set_enabled(True)
        if self.is_enabled():
            return self.set_enabled(False)
        return True, ""
