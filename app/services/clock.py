"""One-second-aligned local clock.

The timer is deliberately coarse and single: the widget only needs one update
per second, and aligning to the wall-clock second keeps the displayed seconds
from visibly drifting.
"""

from __future__ import annotations

import datetime as dt
import time

from PySide6.QtCore import QObject, QTimer, Qt, Signal


class Clock(QObject):
    tick = Signal(object)  # datetime.datetime

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._timer.timeout.connect(self._emit)

        self._align = QTimer(self)
        self._align.setSingleShot(True)
        self._align.setTimerType(Qt.TimerType.PreciseTimer)
        self._align.timeout.connect(self._start_periodic)

        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._emit()
        delay_ms = max(10, int((1.0 - (time.time() % 1.0)) * 1000))
        self._align.start(delay_ms)

    def stop(self) -> None:
        self._running = False
        self._align.stop()
        self._timer.stop()

    def _start_periodic(self) -> None:
        if not self._running:
            return
        self._emit()
        self._timer.start()

    def _emit(self) -> None:
        if self._running:
            self.tick.emit(dt.datetime.now())
