"""Persian settings window with live preview and safe persistence."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.calendar.localization import number, percent_text
from app.storage.settings import (
    ACCENT_PRESETS,
    DEFAULTS,
    MAX_OPACITY,
    MAX_SIZE_PERCENT,
    MIN_OPACITY,
    MIN_SIZE_PERCENT,
    SettingsValues,
    normalize_accent,
)
from app.ui.components import (
    ColorSwatch,
    FramelessWindow,
    IconButton,
    ToggleSwitch,
    separator,
)
from app.ui.styles import DANGER, MUTED, TEXT
from app.weather.models import WeatherLocation

NATURAL_WIDTH = 486
NATURAL_HEIGHT = 720


class SettingsWindow(FramelessWindow):
    valuesChanged = Signal(object)  # SettingsValues
    saveRequested = Signal(object)
    cancelled = Signal()

    def __init__(
        self,
        values: SettingsValues,
        parent: QWidget | None = None,
        city_search: object | None = None,
    ) -> None:
        super().__init__(parent)
        self._values = values
        self._loading = True
        self._saved = False
        self._city_search = city_search
        self._city_search_connected = False
        self._search_results: tuple[WeatherLocation, ...] = ()
        self._selected_location: WeatherLocation | None = None

        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setFixedSize(NATURAL_WIDTH, NATURAL_HEIGHT)
        self.title_bar.set_title("تنظیمات")
        self.close_button = IconButton("close", 30, MUTED, "بستن", self)
        self.close_button.clicked.connect(self.cancel)
        self.title_bar.add_action(self.close_button)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body.addWidget(self.scroll, 1)

        self.content = QWidget()
        self.content.setObjectName("transparentRoot")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        self.scroll.setWidget(self.content)

        self._build_appearance()
        self._build_weather()
        self._build_behavior()
        self._build_footer()
        self.content_layout.addStretch(1)

        if self._city_search is not None:
            self._connect_city_search(self._city_search)

        self.load_values(values)
        self._loading = False

    # ------------------------------------------------------------------ build
    def _section(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("section")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        self.content_layout.addWidget(card)
        return card, layout

    @staticmethod
    def _row_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-size: 9.5pt;")
        return label

    def _build_appearance(self) -> None:
        _card, layout = self._section("ظاهر")

        layout.addWidget(self._row_label("رنگ تأکید"))
        accent_row = QHBoxLayout()
        accent_row.setSpacing(6)
        self.swatch_group = QButtonGroup(self)
        self.swatch_group.setExclusive(True)
        self.swatches: list[ColorSwatch] = []
        for name, color in ACCENT_PRESETS:
            swatch = ColorSwatch(color, name, self)
            swatch.setFixedSize(28, 28)
            self.swatch_group.addButton(swatch)
            swatch.clicked.connect(lambda _=False, c=color: self._set_accent(c))
            accent_row.addWidget(swatch)
            self.swatches.append(swatch)

        self.custom_swatch = ColorSwatch(self._values.accent, "رنگ دلخواه", self)
        self.custom_swatch.setFixedSize(28, 28)
        self.swatch_group.addButton(self.custom_swatch)
        self.custom_swatch.clicked.connect(
            lambda _=False: self._set_accent(self.custom_swatch.color.name())
        )
        self.custom_swatch.setVisible(False)
        accent_row.addWidget(self.custom_swatch)

        self.custom_button = QPushButton("دلخواه…")
        self.custom_button.setObjectName("ghost")
        self.custom_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_button.clicked.connect(self._pick_custom_color)
        accent_row.addWidget(self.custom_button)
        accent_row.addStretch(1)
        layout.addLayout(accent_row)

        layout.addWidget(separator())
        self.opacity_slider, self.opacity_value = self._add_slider(
            layout,
            "شفافیت ویجت",
            MIN_OPACITY,
            MAX_OPACITY,
            1,
            self._values.opacity,
        )
        layout.addWidget(separator())
        self.size_slider, self.size_value = self._add_slider(
            layout,
            "اندازهٔ ویجت",
            MIN_SIZE_PERCENT,
            MAX_SIZE_PERCENT,
            5,
            self._values.size_percent,
        )
        layout.addWidget(separator())

        gregorian_row = QHBoxLayout()
        gregorian_row.addWidget(self._row_label("نمایش تاریخ میلادی"))
        gregorian_row.addStretch(1)
        self.gregorian_toggle = ToggleSwitch(self._values.accent, self)
        gregorian_row.addWidget(self.gregorian_toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(gregorian_row)

        self.opacity_slider.valueChanged.connect(self._on_changed)
        self.size_slider.valueChanged.connect(self._on_changed)
        self.gregorian_toggle.toggled.connect(self._on_changed)

    def _add_slider(
        self,
        layout: QVBoxLayout,
        title: str,
        minimum: int,
        maximum: int,
        step: int,
        value: int,
    ) -> tuple[QSlider, QLabel]:
        top = QHBoxLayout()
        top.addWidget(self._row_label(title))
        top.addStretch(1)
        value_label = QLabel()
        value_label.setStyleSheet(f"color: {TEXT}; font-size: 9.5pt; font-weight: 600;")
        top.addWidget(value_label)
        layout.addLayout(top)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setSingleStep(step)
        slider.setPageStep(step)
        slider.setValue(value)
        slider.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(slider)
        return slider, value_label

    def _build_behavior(self) -> None:
        _card, layout = self._section("رفتار")
        self.topmost_toggle = self._toggle_row(
            layout, "همیشه در جلوی پنجره‌ها", self._values.always_on_top
        )
        layout.addWidget(separator())
        self.startup_toggle = self._toggle_row(
            layout, "اجرای خودکار هنگام ورود به ویندوز", self._values.start_with_windows
        )
        self.topmost_toggle.toggled.connect(self._on_changed)
        self.startup_toggle.toggled.connect(self._on_changed)

    def _toggle_row(self, layout: QVBoxLayout, text: str, checked: bool) -> ToggleSwitch:
        row = QHBoxLayout()
        row.addWidget(self._row_label(text))
        row.addStretch(1)
        toggle = ToggleSwitch(self._values.accent, self)
        toggle.setChecked(checked)
        row.addWidget(toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(row)
        return toggle

    def _build_weather(self) -> None:
        _card, layout = self._section("هوا")

        city_row = QHBoxLayout()
        self.weather_city_label = QLabel("شهری انتخاب نشده")
        self.weather_city_label.setObjectName("weatherCity")
        city_row.addWidget(self.weather_city_label, 1)
        self.clear_city_button = QPushButton("پاک کردن")
        self.clear_city_button.setObjectName("ghost")
        self.clear_city_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_city_button.clicked.connect(self._clear_city)
        city_row.addWidget(self.clear_city_button, 0)
        layout.addLayout(city_row)

        self.weather_subtitle_label = QLabel()
        self.weather_subtitle_label.setObjectName("dim")
        self.weather_subtitle_label.setWordWrap(True)
        self.weather_subtitle_label.setVisible(False)
        layout.addWidget(self.weather_subtitle_label)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("نام شهر را وارد کنید…")
        self.city_input.setClearButtonEnabled(True)
        self.city_input.returnPressed.connect(self._search_city)
        self.city_input.textEdited.connect(self._on_city_text_edited)
        self.city_search_button = QPushButton("جستجو")
        self.city_search_button.setObjectName("pill")
        self.city_search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.city_search_button.clicked.connect(self._search_city)
        search_row.addWidget(self.city_input, 1)
        search_row.addWidget(self.city_search_button, 0)
        layout.addLayout(search_row)

        self.city_results = QListWidget()
        self.city_results.setMaximumHeight(112)
        self.city_results.setVisible(False)
        self.city_results.itemClicked.connect(self._choose_city)
        layout.addWidget(self.city_results)

        self.city_status = QLabel("برای فعال‌سازی هوا، شهر را جستجو کنید.")
        self.city_status.setObjectName("weatherStatus")
        self.city_status.setWordWrap(True)
        layout.addWidget(self.city_status)

        units_row = QHBoxLayout()
        units_row.setSpacing(8)
        units_row.addWidget(self._row_label("دما"))
        self.temperature_combo = QComboBox()
        self.temperature_combo.addItem("سلسیوس (°C)", "celsius")
        self.temperature_combo.addItem("فارنهایت (°F)", "fahrenheit")
        self.temperature_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        units_row.addWidget(self.temperature_combo, 1)
        units_row.addWidget(self._row_label("باد"))
        self.wind_combo = QComboBox()
        self.wind_combo.addItem("کیلومتر بر ساعت", "kmh")
        self.wind_combo.addItem("متر بر ثانیه", "ms")
        self.wind_combo.addItem("مایل بر ساعت", "mph")
        self.wind_combo.addItem("گره", "kn")
        self.wind_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        units_row.addWidget(self.wind_combo, 1)
        layout.addLayout(units_row)

        self.temperature_combo.currentIndexChanged.connect(self._on_changed)
        self.wind_combo.currentIndexChanged.connect(self._on_changed)

        attribution = QLabel(
            '<a href="https://open-meteo.com/">دادهٔ هوا از Open-Meteo.com</a>'
        )
        attribution.setObjectName("weatherAttribution")
        attribution.setTextFormat(Qt.TextFormat.RichText)
        attribution.setOpenExternalLinks(True)
        attribution.setWordWrap(True)
        self.attribution_label = attribution
        layout.addWidget(attribution)

    # -------------------------------------------------------------- weather
    def _connect_city_search(self, client: object) -> None:
        if self._city_search_connected:
            return
        results_ready = getattr(client, "resultsReady", None)
        search_failed = getattr(client, "searchFailed", None)
        if results_ready is None or search_failed is None:
            return
        results_ready.connect(self._on_city_results)
        search_failed.connect(self._on_city_search_failed)
        self._city_search_connected = True

    def _ensure_city_search(self):
        if self._city_search is None:
            from app.weather.open_meteo import OpenMeteoGeocodingClient

            self._city_search = OpenMeteoGeocodingClient(parent=self)
            self._connect_city_search(self._city_search)
        return self._city_search

    def _search_city(self) -> None:
        query = self.city_input.text().strip()
        if len(query) < 2:
            self.city_status.setText("دست‌کم دو حرف از نام شهر را وارد کنید.")
            return
        client = self._ensure_city_search()
        if client is None:
            return
        self._search_results = ()
        self.city_results.clear()
        self.city_results.setVisible(False)
        self.city_status.setText("در حال جستجوی شهر…")
        self.city_search_button.setEnabled(False)
        client.search(query)

    def _on_city_text_edited(self, text: str) -> None:
        if self._city_search is not None:
            cancel = getattr(self._city_search, "cancel", None)
            if cancel is not None:
                cancel()
        self._search_results = ()
        self.city_results.clear()
        self.city_results.setVisible(False)
        self.city_search_button.setEnabled(True)
        if self._selected_location is None:
            if text.strip():
                self.city_status.setText("برای انتخاب شهر، جستجو کنید.")
            return
        if text.strip() != self._selected_location.name:
            self.city_status.setText(
                "برای تغییر شهر، جستجو کنید و نتیجه را انتخاب کنید."
            )

    def _on_city_results(self, results: object) -> None:
        self.city_search_button.setEnabled(True)
        self._search_results = tuple(
            item for item in (results or ()) if isinstance(item, WeatherLocation)
        )
        self.city_results.clear()
        if not self._search_results:
            self.city_results.setVisible(False)
            self.city_status.setText("شهری با این نام پیدا نشد.")
            return
        for location in self._search_results:
            label = location.display_name
            if location.subtitle:
                label = f"{label} — {location.subtitle}"
            self.city_results.addItem(label)
        self.city_results.setVisible(True)
        self.city_status.setText(
            f"{number(len(self._search_results))} شهر پیدا شد؛ یکی را انتخاب کنید."
        )

    def _on_city_search_failed(self, message: str) -> None:
        self.city_search_button.setEnabled(True)
        self._search_results = ()
        self.city_results.clear()
        self.city_results.setVisible(False)
        self.city_status.setText(message or "جستجوی شهر ممکن نشد.")

    def _choose_city(self, item) -> None:
        row = self.city_results.row(item)
        if 0 <= row < len(self._search_results):
            self._select_location(self._search_results[row])

    def _select_location(self, location: WeatherLocation) -> None:
        self._selected_location = location
        self._values = replace(
            self._values,
            weather_city=location.name,
            weather_latitude=location.latitude,
            weather_longitude=location.longitude,
            weather_timezone=location.timezone,
            weather_country=location.country,
            weather_admin1=location.admin1,
            weather_location_id=location.location_id,
        )
        self.weather_city_label.setText(location.display_name)
        subtitle = location.subtitle
        self.weather_subtitle_label.setText(subtitle)
        self.weather_subtitle_label.setVisible(bool(subtitle))
        self.city_input.setText(location.display_name)
        self.city_results.clear()
        self.city_results.setVisible(False)
        self.city_status.setText("شهر انتخاب شد؛ با ذخیره، هوا به‌روزرسانی می‌شود.")
        self.clear_city_button.setEnabled(True)
        if not self._loading:
            self.valuesChanged.emit(self.values())

    def _clear_city(self) -> None:
        if self._city_search is not None:
            cancel = getattr(self._city_search, "cancel", None)
            if cancel is not None:
                cancel()
        self._search_results = ()
        self._selected_location = None
        self._values = replace(
            self._values,
            weather_city="",
            weather_latitude=None,
            weather_longitude=None,
            weather_timezone="auto",
            weather_country="",
            weather_admin1="",
            weather_location_id=None,
        )
        self.weather_city_label.setText("شهری انتخاب نشده")
        self.weather_subtitle_label.clear()
        self.weather_subtitle_label.setVisible(False)
        self.city_input.clear()
        self.city_results.clear()
        self.city_results.setVisible(False)
        self.city_search_button.setEnabled(True)
        self.city_status.setText("برای فعال‌سازی هوا، شهر را جستجو کنید.")
        self.clear_city_button.setEnabled(False)
        if not self._loading:
            self.valuesChanged.emit(self.values())

    def _build_footer(self) -> None:
        self.error_label = QLabel()
        self.error_label.setObjectName("errorText")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        # Keep the actions outside the scroll area so Save/Cancel remain
        # reachable on small or highly scaled screens.
        self.body.addWidget(self.error_label)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.reset_button = QPushButton("بازنشانی")
        self.reset_button.setObjectName("ghost")
        self.reset_button.clicked.connect(self.reset_values)
        self.cancel_button = QPushButton("انصراف")
        self.cancel_button.clicked.connect(self.cancel)
        self.save_button = QPushButton("ذخیره")
        self.save_button.setObjectName("primary")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._save)
        footer.addWidget(self.reset_button)
        footer.addStretch(1)
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.save_button)
        self.body.addLayout(footer)

    # ----------------------------------------------------------------- values
    def load_values(self, values: SettingsValues) -> None:
        values = values.normalized()
        self._values = values
        self._loading = True
        self.opacity_slider.setValue(values.opacity)
        self.size_slider.setValue(values.size_percent)
        self.opacity_value.setText(percent_text(values.opacity))
        self.size_value.setText(percent_text(values.size_percent))
        self.gregorian_toggle.set_checked(values.show_gregorian, animate=False)
        self.topmost_toggle.set_checked(values.always_on_top, animate=False)
        self.startup_toggle.set_checked(values.start_with_windows, animate=False)
        for toggle in (
            self.gregorian_toggle,
            self.topmost_toggle,
            self.startup_toggle,
        ):
            toggle.set_accent(values.accent)
        self._apply_accent_ui(values.accent)

        if self._city_search is not None:
            cancel = getattr(self._city_search, "cancel", None)
            if cancel is not None:
                cancel()
        self._search_results = ()
        self.city_results.clear()
        self.city_results.setVisible(False)
        self.city_search_button.setEnabled(True)
        if values.has_weather_location:
            location = WeatherLocation(
                name=values.weather_city,
                latitude=values.weather_latitude or 0.0,
                longitude=values.weather_longitude or 0.0,
                timezone=values.weather_timezone,
                country=values.weather_country,
                admin1=values.weather_admin1,
                location_id=values.weather_location_id,
            )
            self._selected_location = location
            self.weather_city_label.setText(location.display_name)
            self.weather_subtitle_label.setText(location.subtitle)
            self.weather_subtitle_label.setVisible(bool(location.subtitle))
            self.city_input.setText(location.name)
            self.city_status.setText("شهر انتخاب‌شده؛ برای تغییر، جستجو کنید.")
            self.clear_city_button.setEnabled(True)
        else:
            self._selected_location = None
            self.weather_city_label.setText("شهری انتخاب نشده")
            self.weather_subtitle_label.clear()
            self.weather_subtitle_label.setVisible(False)
            self.city_input.clear()
            self.city_status.setText("برای فعال‌سازی هوا، شهر را جستجو کنید.")
            self.clear_city_button.setEnabled(False)

        temperature_index = self.temperature_combo.findData(
            values.weather_temperature_unit
        )
        self.temperature_combo.setCurrentIndex(temperature_index if temperature_index >= 0 else 0)
        wind_index = self.wind_combo.findData(values.weather_wind_speed_unit)
        self.wind_combo.setCurrentIndex(wind_index if wind_index >= 0 else 0)

        self.error_label.clear()
        self.error_label.setVisible(False)
        self._saved = False
        self._loading = False

    def values(self) -> SettingsValues:
        selected = self._selected_location
        return replace(
            self._values,
            accent=normalize_accent(self._values.accent),
            opacity=int(self.opacity_slider.value()),
            size_percent=int(self.size_slider.value()),
            show_gregorian=self.gregorian_toggle.isChecked(),
            always_on_top=self.topmost_toggle.isChecked(),
            start_with_windows=self.startup_toggle.isChecked(),
            weather_city=selected.name if selected is not None else "",
            weather_latitude=selected.latitude if selected is not None else None,
            weather_longitude=selected.longitude if selected is not None else None,
            weather_timezone=selected.timezone if selected is not None else "auto",
            weather_country=selected.country if selected is not None else "",
            weather_admin1=selected.admin1 if selected is not None else "",
            weather_location_id=selected.location_id if selected is not None else None,
            weather_temperature_unit=str(
                self.temperature_combo.currentData() or "celsius"
            ),
            weather_wind_speed_unit=str(self.wind_combo.currentData() or "kmh"),
        )

    def _on_changed(self, *_args) -> None:
        if self._loading:
            return
        self.opacity_value.setText(percent_text(self.opacity_slider.value()))
        self.size_value.setText(percent_text(self.size_slider.value()))
        values = self.values()
        self._values = values
        self.valuesChanged.emit(values)

    def _set_accent(self, color: str) -> None:
        color = normalize_accent(color)
        self._values = replace(self._values, accent=color)
        for toggle in (
            self.gregorian_toggle,
            self.topmost_toggle,
            self.startup_toggle,
        ):
            toggle.set_accent(color)
        self._apply_accent_ui(color)
        if not self._loading:
            self.valuesChanged.emit(self.values())

    def _apply_accent_ui(self, accent: str) -> None:
        matched = False
        for swatch, (_name, color) in zip(self.swatches, ACCENT_PRESETS):
            is_match = QColor(color).name().lower() == QColor(accent).name().lower()
            swatch.setChecked(is_match)
            matched = matched or is_match
        if not matched:
            self.custom_swatch.set_color(accent)
            self.custom_swatch.setVisible(True)
            self.custom_swatch.setChecked(True)
        else:
            self.custom_swatch.setVisible(False)
            self.custom_swatch.setChecked(False)
        if hasattr(self, "attribution_label"):
            self.attribution_label.setText(
                '<a href="https://open-meteo.com/" '
                f'style="color: {accent}; text-decoration: none;">'
                "دادهٔ هوا از Open-Meteo.com</a>"
            )

    def _pick_custom_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(self._values.accent), self, "انتخاب رنگ تأکید"
        )
        if color.isValid():
            self.custom_swatch.set_color(color.name())
            self._set_accent(color.name())

    def reset_values(self) -> None:
        defaults = replace(
            DEFAULTS,
            widget_x=self._values.widget_x,
            widget_y=self._values.widget_y,
            weather_city=self._values.weather_city,
            weather_latitude=self._values.weather_latitude,
            weather_longitude=self._values.weather_longitude,
            weather_timezone=self._values.weather_timezone,
            weather_country=self._values.weather_country,
            weather_admin1=self._values.weather_admin1,
            weather_location_id=self._values.weather_location_id,
            weather_temperature_unit=self._values.weather_temperature_unit,
            weather_wind_speed_unit=self._values.weather_wind_speed_unit,
        )
        self.load_values(defaults)
        self.error_label.clear()
        self.error_label.setVisible(False)
        self.valuesChanged.emit(self.values())

    # ---------------------------------------------------------------- actions
    def _save(self) -> None:
        self.error_label.setVisible(False)
        self.saveRequested.emit(self.values())

    def accept_and_close(self) -> None:
        if self._city_search is not None:
            cancel = getattr(self._city_search, "cancel", None)
            if cancel is not None:
                cancel()
        self._saved = True
        self.hide()

    def cancel(self) -> None:
        if self._city_search is not None:
            cancel = getattr(self._city_search, "cancel", None)
            if cancel is not None:
                cancel()
        if self._saved:
            self._saved = False
            self.hide()
            return
        self.cancelled.emit()
        self.hide()

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(bool(message))

    def show_window(self, values: SettingsValues, anchor: QWidget | None = None) -> None:
        self.load_values(values)
        self.adjust_to_screen(anchor)
        self.show_near(anchor)
        self.show_with_fade()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def adjust_to_screen(self, anchor: QWidget | None = None) -> None:
        screen = anchor.screen() if anchor is not None and anchor.isVisible() else None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        height = min(NATURAL_HEIGHT, max(440, available.height() - 16))
        self.setFixedSize(NATURAL_WIDTH, height)
        self.content.setMinimumHeight(0)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        event.ignore()
        self.cancel()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
        else:
            super().keyPressEvent(event)
