"""Best-effort single-instance guard built on QLocalServer/QLocalSocket."""

from __future__ import annotations

import getpass
import hashlib
import time

from PySide6.QtCore import QCoreApplication, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

APP_KEY = "PersianCalendarWidget"


def server_name(suffix: str = "") -> str:
    user = getpass.getuser() or "user"
    digest = hashlib.sha1(user.encode("utf-8", "replace")).hexdigest()[:10]
    return f"PCW-{digest}-{suffix}" if suffix else f"PCW-{digest}"


class SingleInstance(QObject):
    messageReceived = Signal(str)

    def __init__(self, name: str | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.name = name or server_name()
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._accept_connections)
        self._primary = False

    @property
    def is_primary(self) -> bool:
        return self._primary

    def acquire(self) -> bool:
        """Return True when this process became the primary instance."""
        if self._primary:
            return False
        probe = QLocalSocket()
        probe.connectToServer(self.name)
        if probe.waitForConnected(350):
            probe.write(b"activate\n")
            probe.flush()
            probe.waitForBytesWritten(500)
            # On Windows named pipes waitForBytesWritten() can return False
            # while the bytes are still queued.  Disconnecting immediately
            # aborts the connection and can discard the notification, so spin
            # the local event loop briefly until Qt has handed the bytes over.
            deadline = time.monotonic() + 0.5
            while probe.bytesToWrite() > 0 and time.monotonic() < deadline:
                QCoreApplication.processEvents()
                time.sleep(0.005)
            probe.disconnectFromServer()
            return False

        QLocalServer.removeServer(self.name)
        if self._server.listen(self.name):
            self._primary = True
            return True
        # Another process may have removed/created the pipe between the probe
        # and listen; one retry is enough.
        QLocalServer.removeServer(self.name)
        if self._server.listen(self.name):
            self._primary = True
            return True
        return False

    def _accept_connections(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                continue
            socket.readyRead.connect(lambda s=socket: self._read(s))
            socket.disconnected.connect(socket.deleteLater)
            if socket.bytesAvailable():
                self._read(socket)

    def _read(self, socket: QLocalSocket) -> None:
        data = bytes(socket.readAll()).decode("utf-8", "replace").strip()
        socket.disconnectFromServer()
        self.messageReceived.emit(data or "activate")

    def close(self) -> None:
        self._server.close()
        if self._primary:
            QLocalServer.removeServer(self.name)
        self._primary = False
