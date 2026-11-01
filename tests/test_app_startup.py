"""End-to-end application startup, shutdown and CLI diagnostics tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import main as app_main

ROOT = Path(__file__).resolve().parents[1]


def test_parse_args_flags() -> None:
    args = app_main._parse_args(
        [
            "--smoke-test",
            "--smoke-report",
            "report.json",
            "--screenshot-dir",
            "shots",
            "--no-single-instance",
        ]
    )
    assert args.smoke_test is True
    assert args.smoke_report == "report.json"
    assert args.screenshot_dir == "shots"
    assert args.no_single_instance is True
    assert args.version is False


def test_version_cli_does_not_start_the_ui(capsys) -> None:
    assert app_main.main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "0.2.0"


def test_smoke_test_subprocess_writes_report(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    report_path = tmp_path / "smoke.json"
    environment = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONIOENCODING": "utf-8",
        "PCW_CONFIG_DIR": str(tmp_path / "env-config"),
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "main.py"),
            "--smoke-test",
            "--smoke-report",
            str(report_path),
            "--config-dir",
            str(config_dir),
            "--no-single-instance",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    output = completed.stdout
    assert "Traceback" not in output
    smoke_line = next(
        line for line in output.splitlines() if line.startswith("SMOKE ")
    )
    stdout_report = json.loads(smoke_line[len("SMOKE ") :])
    assert stdout_report["ok"] is True
    assert stdout_report["holiday_loaded"] is True
    assert stdout_report["calendar_cells"] == 42
    assert stdout_report["settings_visible"] is True
    assert stdout_report["coverage"] == [1402, 1426]
    assert stdout_report["weather_assets"]["background_count"] == 14
    assert stdout_report["weather_assets"]["icon_count"] == 24
    assert stdout_report["weather_assets"]["missing"] == []
    assert stdout_report["weather_assets"]["decode_failures"] == []

    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["holiday_count"] >= 600
    assert report["occasion_entry_count"] >= report["occasion_count"]
    assert report["calendar_month"]
    assert report["calendar_selected"]
    assert report["settings_values"]["accent"].startswith("#")
    assert "error" not in report
