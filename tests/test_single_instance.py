"""Single-instance guard tests using real local sockets."""

from __future__ import annotations

import uuid

from app.core.single_instance import SingleInstance, server_name


def test_server_name_is_stable_and_supports_suffix() -> None:
    base = server_name()
    assert base.startswith("PCW-")
    assert server_name() == base
    assert server_name("test") == f"{base}-test"
    assert server_name("other") != server_name("test")


def test_second_instance_notifies_the_primary(qtbot) -> None:
    name = server_name(f"test-{uuid.uuid4().hex}")
    first = SingleInstance(name)
    second = SingleInstance(name)
    received: list[str] = []
    first.messageReceived.connect(received.append)
    assert first.acquire() is True
    assert first.is_primary is True
    try:
        assert second.acquire() is False
        assert second.is_primary is False
        # The notification is delivered through the local-socket event loop.
        qtbot.wait(250)
        assert received == ["activate"]
    finally:
        first.close()
        second.close()
    assert first.is_primary is False


def test_lock_is_released_after_close(qtbot) -> None:
    name = server_name(f"test-{uuid.uuid4().hex}")
    first = SingleInstance(name)
    assert first.acquire()
    first.close()

    replacement = SingleInstance(name)
    try:
        assert replacement.acquire()
        assert replacement.is_primary
    finally:
        replacement.close()


def test_primary_does_not_connect_to_itself(qtbot) -> None:
    name = server_name(f"test-{uuid.uuid4().hex}")
    instance = SingleInstance(name)
    assert instance.acquire()
    # A second acquire from the same process probes its own listener and must
    # not turn into a second primary.
    assert instance.acquire() is False
    instance.close()
