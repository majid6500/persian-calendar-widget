"""Windows per-user startup integration tests.

Each test uses a unique registry value name and removes it afterwards, so the
user's real startup entries are never touched.
"""

from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from app.services.startup import StartupManager, application_command

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="Windows registry integration"
)


@pytest.fixture
def manager() -> StartupManager:
    value_name = f"PersianCalendarWidgetTest-{uuid.uuid4().hex}"
    instance = StartupManager(
        value_name=value_name,
        command=subprocess.list2cmdline(
            [str(Path(sys.executable)), str(Path.cwd() / "main.py")]
        ),
    )
    yield instance
    instance.set_enabled(False)


def test_application_command_points_to_main_script() -> None:
    command = application_command()
    assert "main.py" in command
    assert str(Path(sys.executable).parent) in command or "python" in command.lower()


def test_enable_disable_round_trip(manager: StartupManager) -> None:
    assert manager.supported
    ok, message = manager.set_enabled(False)
    assert ok, message
    assert not manager.is_enabled()
    assert manager.current_command() is None

    ok, message = manager.set_enabled(True)
    assert ok, message
    assert manager.is_enabled()
    assert manager.current_command() == manager.command

    ok, message = manager.set_enabled(False)
    assert ok, message
    assert not manager.is_enabled()
    assert manager.current_command() is None


def test_sync_is_idempotent_and_updates_stale_command(
    manager: StartupManager,
) -> None:
    ok, message = manager.sync(False)
    assert ok, message
    assert not manager.is_enabled()

    ok, message = manager.sync(True)
    assert ok, message
    assert manager.current_command() == manager.command

    # A command from an older installation is replaced.
    new_command = subprocess.list2cmdline(
        [str(Path(sys.executable)), str(Path.cwd() / "main.py"), "--moved"]
    )
    manager.command = new_command
    ok, message = manager.sync(True)
    assert ok, message
    assert manager.current_command() == new_command

    ok, message = manager.sync(False)
    assert ok, message
    assert not manager.is_enabled()


def test_unsupported_manager_does_not_touch_registry() -> None:
    class UnsupportedStartupManager(StartupManager):
        @property
        def supported(self) -> bool:  # type: ignore[override]
            return False

    manager = UnsupportedStartupManager(
        value_name=f"PersianCalendarWidgetTest-{uuid.uuid4().hex}",
        command="test",
    )
    assert manager.is_enabled() is False
    assert manager.current_command() is None
    ok, message = manager.set_enabled(True)
    assert ok is False
    assert "ویندوز" in message
    ok, message = manager.sync(True)
    assert ok is False
