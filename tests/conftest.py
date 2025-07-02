"""Conftest."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator, Callable
from typing import Any

import pytest

from pybalboa.client import MESSAGE_DELIMETER_BYTE
from pybalboa.enums import MessageType, SettingsCode
from pybalboa.utils import read_one_message

HOST = "localhost"

MODULE_IDENTIFICATION = "TEST"


def load_spa_from_json(name: str) -> Any:
    """Load spa from json file."""
    with open(f"tests/fixtures/{name}.json", encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture()
async def bfbp20s(
    spa_server: Callable[[int, str], AsyncGenerator[SpaServer, None]],
    unused_tcp_port: int,
) -> AsyncGenerator[SpaServer, None]:
    """Mock a BFBP20S spa."""
    async for server in spa_server(unused_tcp_port, "bfbp20s"):
        yield server


@pytest.fixture()
async def bp501g1(
    spa_server: Callable[[int, str], AsyncGenerator[SpaServer, None]],
    unused_tcp_port: int,
) -> AsyncGenerator[SpaServer, None]:
    """Mock a BP501G1 spa."""
    async for server in spa_server(unused_tcp_port, "bp501g1"):
        yield server


@pytest.fixture()
async def lpi501st(
    spa_server: Callable[[int, str], AsyncGenerator[SpaServer, None]],
    unused_tcp_port: int,
) -> AsyncGenerator[SpaServer, None]:
    """Mock a LPI501ST spa."""
    async for server in spa_server(unused_tcp_port, "lpi501st"):
        yield server


@pytest.fixture()
async def mxbp20(
    spa_server: Callable[[int, str], AsyncGenerator[SpaServer, None]],
    unused_tcp_port: int,
) -> AsyncGenerator[SpaServer, None]:
    """Mock a MXBP20 spa."""
    async for server in spa_server(unused_tcp_port, "mxbp20"):
        yield server


@pytest.fixture()
async def bp6013g1(
    spa_server: Callable[[int, str], AsyncGenerator[SpaServer, None]],
    unused_tcp_port: int,
) -> AsyncGenerator[SpaServer, None]:
    """Mock a BP6013G1 spa."""
    async for server in spa_server(unused_tcp_port, "bp6013g1"):
        yield server


@pytest.fixture(name="spa_server")
def spa_server_factory() -> Callable[[int, str], AsyncGenerator[SpaServer, None]]:
    """
    Provides a factory that creates and starts a SpaServer for a given fixture name and port.

    Returns:
        A factory function accepting (unused_tcp_port, fixture_name) and yielding a started SpaServer instance.
    """

    async def _factory(
        unused_tcp_port: int, fixture_name: str
    ) -> AsyncGenerator[SpaServer, None]:
        messages = load_spa_from_json(fixture_name)
        spa = SpaServer(unused_tcp_port, messages)
        task = asyncio.create_task(spa.start_server())
        await asyncio.sleep(0.01)

        try:
            yield spa
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    return _factory


class SpaServer:
    """Test server that simulates a spa device."""

    def __init__(self, port: int, messages: dict[str, str]) -> None:
        """Initialize the spa server."""
        self.port = port
        self.messages = messages
        self.received_messages: list[bytes] = []

    async def start_server(self) -> None:
        """Start the async TCP server."""
        server = await asyncio.start_server(self.handle_message, HOST, self.port)

        addr = server.sockets[0].getsockname()
        print(f"SERVER: Serving on {addr[0:2]}")

        async with server:
            await server.serve_forever()

    async def handle_message(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming messages from the client."""
        timeout = 1
        while True:
            try:
                data = await read_one_message(reader, timeout)
                self.received_messages.append(data)
                message_type = MessageType(data[3])
            except asyncio.TimeoutError:
                message_type = MessageType.STATUS_UPDATE

            message = None
            if message_type == MessageType.STATUS_UPDATE:
                message = self.messages["status_update"]
            elif message_type == MessageType.DEVICE_PRESENT:
                message = self.messages["module_identification"]
            elif message_type == MessageType.REQUEST:
                settings_code = SettingsCode(data[4])
                message = self.messages.get(settings_code.name.lower())

            if message:
                print(message)
                writer.write(
                    MESSAGE_DELIMETER_BYTE
                    + bytes.fromhex(message)
                    + MESSAGE_DELIMETER_BYTE
                )
                await writer.drain()
