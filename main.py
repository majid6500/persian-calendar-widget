"""Persian Calendar Widget entry point."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, qVersion
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from app import __version__
from app.core.paths import assets_path, log_file
from app.core.single_instance import SingleInstance
from app.ui.styles import apply_theme, load_fonts


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ویجت تقویم شمسی برای ویندوز")
    parser.add_argument("--version", action="store_true", help="نمایش نسخه و خروج")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="راه‌اندازی، بررسی اجزای اصلی و خروج (برای آزمون بسته)",
    )
    parser.add_argument(
        "--screenshot-dir",
        metavar="DIR",
        help="ذخیرهٔ تصویر ویجت، تقویم و تنظیمات و خروج (ابزار توسعه)",
    )
    parser.add_argument(
        "--no-single-instance",
        action="store_true",
        help="اجازه به چند نمونهٔ هم‌زمان (فقط برای آزمون)",
    )
    parser.add_argument(
        "--smoke-report",
        metavar="FILE",
        help="نوشتن نتیجهٔ آزمون دود در یک فایل JSON",
    )
    parser.add_argument(
        "--config-dir",
        metavar="DIR",
        help="محل سفارشی تنظیمات (پیش‌فرض: %%APPDATA%%\\PersianCalendarWidget)",
    )
    return parser.parse_args(argv)


def _set_app_user_model_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "PersianCalendarWidget.0.2.0"
        )
    except Exception:
        pass


def _install_excepthook(smoke: bool) -> None:
    def hook(exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            log_file().write_text(text, encoding="utf-8")
        except OSError:
            pass
        sys.__excepthook__(exc_type, exc, tb)
        if not smoke:
            try:
                QMessageBox.critical(
                    None,
                    "خطای غیرمنتظره",
                    "خطایی رخ داد. جزئیات در فایل error.log ذخیره شد.\n\n"
                    + str(exc),
                )
            except Exception:
                pass

    sys.excepthook = hook


def _load_icon(app: QApplication) -> QIcon:
    icon_path = assets_path("icons", "app.png")
    if icon_path.is_file():
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            app.setWindowIcon(icon)
            return icon
    from app.ui.components import make_icon

    icon = make_icon("calendar", "#EEF1F7", 64)
    app.setWindowIcon(icon)
    return icon


def _run_diagnostics(
    controller,
    app: QApplication,
    screenshot_dir: str | None,
    report_path: str | None = None,
) -> None:
    result: dict[str, object] = {}

    def write_report() -> None:
        if not report_path:
            return
        try:
            path = Path(report_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            print(f"SMOKE REPORT ERROR: {exc}", flush=True)

    def check() -> None:
        code = 1
        try:
            widget = controller.widget
            result["version"] = __version__
            result["qt"] = qVersion()
            result["widget_visible"] = widget.isVisible()
            result["widget_size"] = [widget.width(), widget.height()]
            result["widget_opacity"] = round(widget.windowOpacity(), 2)
            result["weather_enabled"] = controller.weather_enabled
            result["weather_status"] = controller.weather.state.status
            result["weather_city"] = (
                controller.weather.state.location.display_name
                if controller.weather.state.location is not None
                else None
            )

            from app.weather.art import WeatherArt
            from app.weather.visuals import validate_assets

            asset_report = validate_assets()
            asset_decode_failures = WeatherArt().validate_files()
            result["weather_assets"] = {
                "background_count": asset_report.background_count,
                "icon_count": asset_report.icon_count,
                "missing": list(asset_report.missing),
                "decode_failures": list(asset_decode_failures),
            }

            result["holiday_loaded"] = controller.service.is_loaded
            result["holiday_error"] = controller.service.load_error
            result["holiday_count"] = controller.service.holiday_count
            result["occasion_count"] = controller.service.occasion_day_count
            result["occasion_entry_count"] = controller.service.occasion_entry_count
            result["coverage"] = (
                [
                    controller.service.coverage.min_year,
                    controller.service.coverage.max_year,
                ]
                if controller.service.coverage
                else None
            )

            controller.open_calendar()
            app.processEvents()
            calendar = controller.calendar
            assert calendar is not None
            result["calendar_visible"] = calendar.isVisible()
            result["calendar_cells"] = len(calendar._cells)
            result["calendar_month"] = calendar.month_label.text()
            result["calendar_gregorian"] = calendar.gregorian_label.text()
            result["calendar_selected"] = calendar.selected_label.text()

            controller.open_settings()
            app.processEvents()
            settings = controller.settings_window
            assert settings is not None
            result["settings_visible"] = settings.isVisible()
            result["settings_values"] = settings.values().__dict__

            if screenshot_dir:
                out = Path(screenshot_dir)
                out.mkdir(parents=True, exist_ok=True)
                app.processEvents()
                widget.grab().save(str(out / "widget.png"))
                calendar.grab().save(str(out / "calendar.png"))
                settings.grab().save(str(out / "settings.png"))

            ok = bool(
                result["widget_visible"]
                and result["holiday_loaded"]
                and result["calendar_cells"] == 42
                and result["settings_visible"]
                and asset_report.ok
                and not asset_decode_failures
            )
            result["ok"] = ok
            print("SMOKE " + json.dumps(result, ensure_ascii=False), flush=True)
            code = 0 if ok else 1
        except Exception:
            result["ok"] = False
            result["error"] = traceback.format_exc()
            traceback.print_exc()
            print("SMOKE " + json.dumps({"ok": False, **result}, ensure_ascii=False), flush=True)
        finally:
            write_report()
            controller.quit()
            app.exit(code)

    QTimer.singleShot(800, check)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.version:
        print(__version__)
        return 0

    if args.config_dir:
        os.environ["PCW_CONFIG_DIR"] = str(Path(args.config_dir).expanduser())
    if (args.smoke_test or args.screenshot_dir) and not args.config_dir:
        os.environ["PCW_CONFIG_DIR"] = tempfile.mkdtemp(prefix="pcw-smoke-")

    _set_app_user_model_id()
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv[:1] + (argv or sys.argv[1:]))
    app.setApplicationName("PersianCalendarWidget")
    app.setApplicationDisplayName("تقویم شمسی")
    app.setOrganizationName("PersianCalendar")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    load_fonts(app)
    _load_icon(app)
    _install_excepthook(args.smoke_test or bool(args.screenshot_dir))

    from app.core.application import CalendarApplication

    diagnostics = bool(args.smoke_test or args.screenshot_dir)
    instance: SingleInstance | None = None
    if not diagnostics and not args.no_single_instance:
        instance = SingleInstance()
        if not instance.acquire():
            return 0

    controller = CalendarApplication(app, weather_enabled=not diagnostics)
    if instance is not None:
        controller.single_instance = instance
        instance.messageReceived.connect(lambda _message: controller.activate())

    apply_theme(app, controller.values.accent)
    controller.start()

    if diagnostics:
        _run_diagnostics(
            controller, app, args.screenshot_dir, args.smoke_report
        )
    else:
        if instance is not None:
            app.aboutToQuit.connect(instance.close)

    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
