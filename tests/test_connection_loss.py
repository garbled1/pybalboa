"""Tests for connection loss handling.

The Balboa BWA Wi-Fi module regularly closes the TCP connection from its side
(EOF / half-close) or resets it. The client must neither spin in its listener
loop (which blocks the whole event loop of the host application) nor stop
reconnecting after the first reconnect.
"""

from __future__ import annotations

import asyncio
import contextlib
import time

import pytest

from pybalboa import SpaClient

from .conftest import HOST, SpaServer, load_spa_from_json

pytestmark = pytest.mark.timeout(30)


class FlakySpaServer(SpaServer):
    """Spa server that ends every connection after a short time."""

    def __init__(self, port: int, messages: dict[str, str], mode: str) -> None:
        """Initialize the flaky spa server."""
        super().__init__(port, messages)
        self.mode = mode
        self.connections = 0

    async def handle_message(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Serve normally for a moment, then drop the connection."""
        self.connections += 1
        with contextlib.suppress(TimeoutError, ConnectionError):
            await asyncio.wait_for(super().handle_message(reader, writer), 0.3)
        if self.mode == "eof":
            # half-close: the client sees EOF, the transport stays open
            writer.write_eof()
            with contextlib.suppress(Exception):
                await asyncio.sleep(10)
        else:
            # hard close
            writer.close()


async def _start(port: int, mode: str) -> tuple[FlakySpaServer, asyncio.Task]:
    server = FlakySpaServer(port, load_spa_from_json("bfbp20s"), mode)
    task = asyncio.create_task(server.start_server())
    await asyncio.sleep(0.05)
    return server, task


async def _measure_loop_responsiveness(duration: float) -> float:
    """Return the largest gap between event loop iterations in seconds."""
    worst = 0.0
    end = time.monotonic() + duration
    last = time.monotonic()
    while time.monotonic() < end:
        await asyncio.sleep(0.01)
        now = time.monotonic()
        worst = max(worst, now - last)
        last = now
    return worst


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["eof", "close"])
async def test_event_loop_not_blocked_on_connection_loss(
    unused_tcp_port: int, mode: str
) -> None:
    """The listener must not block the event loop when the spa drops us."""
    _server, task = await _start(unused_tcp_port, mode)
    spa = SpaClient(HOST, unused_tcp_port)
    try:
        assert await spa.connect()
        worst_gap = await asyncio.wait_for(_measure_loop_responsiveness(1.5), 5)
        assert worst_gap < 0.5, f"event loop blocked for {worst_gap:.2f}s"
    finally:
        await asyncio.wait_for(spa.disconnect(), 5)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["eof", "close"])
async def test_reconnects_repeatedly(unused_tcp_port: int, mode: str) -> None:
    """The client must keep reconnecting, not only after the first drop."""
    server, task = await _start(unused_tcp_port, mode)
    spa = SpaClient(HOST, unused_tcp_port)
    try:
        assert await spa.connect()
        deadline = time.monotonic() + 15
        while server.connections < 4 and time.monotonic() < deadline:
            await asyncio.sleep(0.1)
        assert server.connections >= 4, f"only {server.connections} connections"
    finally:
        await asyncio.wait_for(spa.disconnect(), 5)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
