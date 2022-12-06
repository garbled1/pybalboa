"""Conftest."""
from __future__ import annotations

import asyncio
import json
from asyncio import BaseEventLoop, StreamReader, StreamWriter
from collections.abc import Generator
from typing import Any

import pytest

from pybalboa.client import MESSAGE_DELIMETER_BYTE
from pybalboa.enums import MessageType2, SettingsCode
from pybalboa.utils import read_one_message

HOST = "localhost"

MODULE_IDENTIFICATION = "TEST"


def load_spa_from_json(name: str) -> Any:
    """Load spa from json file."""
    with open(f"tests/fixtures/{name}.json", encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture()
def lpi501st(
    event_loop: BaseEventLoop, unused_tcp_port: int
) -> Generator[SpaServer, None, None]:
    """Mock a LPI501ST spa."""
    yield from spa_server(event_loop, unused_tcp_port, "LPI501ST")


@pytest.fixture()
def mxbp20(
    event_loop: BaseEventLoop, unused_tcp_port: int
) -> Generator[SpaServer, None, None]:
    """Mock a MXBP20 spa."""
    yield from spa_server(event_loop, unused_tcp_port, "MXBP20")


@pytest.fixture()
def stil7_spa(
    event_loop: BaseEventLoop, unused_tcp_port: int
) -> Generator[SpaServer, None, None]:
    """Mock a Stil7 spa."""
    yield from spa_server(event_loop, unused_tcp_port, "stil7-2017")


def spa_server(
    event_loop: BaseEventLoop, unused_tcp_port: int, filename: str
) -> Generator[SpaServer, None, None]:
    """Generate a server with an unused tcp port."""
    messages = load_spa_from_json(filename)
    spa = SpaServer(unused_tcp_port, messages)
    task = asyncio.ensure_future(spa.start_server(), loop=event_loop)
    event_loop.run_until_complete(asyncio.sleep(0.01))

    try:
        yield spa
    finally:
        task.cancel()


class SpaServer:
    """Spa server."""

    def __init__(self, port: int, messages: dict[str, str]) -> None:
        """Initialize a spa server."""
        self.port = port
        self.messages = messages
        self.received_messages: list[bytes] = []

    async def start_server(self) -> None:
        """Start the server."""
        server = await asyncio.start_server(self.handle_message, HOST, self.port)

        addr = server.sockets[0].getsockname()
        print(f"SERVER: Serving on {addr[0:2]}")

        async with server:
            await server.serve_forever()

    async def handle_message(self, reader: StreamReader, writer: StreamWriter) -> None:
        """Handle a message."""
        timeout = 1
        while True:
            try:
                data = await read_one_message(reader, timeout)
                self.received_messages.append(data)
                message_type = MessageType2(data[3])
            except asyncio.TimeoutError:
                message_type = MessageType2.STATUS_UPDATE

            message = None
            if message_type == MessageType2.STATUS_UPDATE:
                message = self.messages["status_update"]
            elif message_type == MessageType2.DEVICE_PRESENT:
                message = self.messages["module_identification"]
            elif message_type == MessageType2.SETTINGS_REQUEST:
                settings_code = SettingsCode(data[4])
                if settings_code == SettingsCode.SYSTEM_INFORMATION:
                    message = self.messages["system_information"]
                elif settings_code == SettingsCode.SETUP_PARAMETERS:
                    message = self.messages["setup_parameters"]
                elif settings_code == SettingsCode.DEVICE_CONFIGURATION:
                    message = self.messages["device_configuration"]
                elif settings_code == SettingsCode.FILTER_CYCLE:
                    message = self.messages["filter_cycle"]
            # elif message_type == MessageType.DEVICE_PRESENT:
            #     message = ""
            if message:
                print(message)
                writer.write(
                    MESSAGE_DELIMETER_BYTE
                    + bytes.fromhex(message)
                    + MESSAGE_DELIMETER_BYTE
                )
                await writer.drain()
