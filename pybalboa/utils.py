"""Utilities module."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from .exceptions import SpaMessageError

MESSAGE_DELIMETER_BYTE = b"~"
MESSAGE_DELIMETER = MESSAGE_DELIMETER_BYTE[0]


def byte_parser(
    value: int,
    offset: int = 0,
    count: int = 8,
    bits: int = 1,
    fn: Callable[[int], int] = lambda _: _,  # pylint: disable=invalid-name
) -> list[int]:
    """Parse a byte."""
    return [
        fn(value >> i * bits + offset & int("0b" + "1" * bits, 2)) for i in range(count)
    ]


def calculate_checksum(data: bytes) -> int:
    """Calculate the checksum byte for a message."""
    crc = 0xB5
    for _, cur in enumerate(data):
        for i in range(8):
            bit = crc & 0x80
            crc = ((crc << 1) & 0xFF) | ((cur >> (7 - i)) & 0x01)
            if bit:
                crc = crc ^ 0x07
        crc &= 0xFF
    for i in range(8):
        bit = crc & 0x80
        crc = (crc << 1) & 0xFF
        if bit:
            crc ^= 0x07
    return crc ^ 0x02


async def cancel_task(task: asyncio.Task | None) -> None:
    """Cancel a task."""
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def default(value: Any, default_value: Any) -> Any:
    """Return value if not None, else default."""
    return default_value if value is None else value


async def read_one_message(reader: asyncio.StreamReader, timeout: int = 15) -> bytes:
    """Read one message."""
    data = await asyncio.wait_for(reader.readexactly(2), timeout)
    if data[0] != MESSAGE_DELIMETER or data[1] == 0:
        # something went wrong reading a message, so
        # read to the next delimeter and discard
        data += await asyncio.wait_for(
            reader.readuntil(MESSAGE_DELIMETER_BYTE), timeout
        )
        raise SpaMessageError(f"Invalid message: {data.hex()}")
    data = data[1:] + (await reader.readexactly(data[1]))[:-1]
    if data[0] != len(data):
        raise SpaMessageError(f"Incomplete message: {data.hex()}")
    if calculate_checksum(data[:-1]) != data[-1]:
        raise SpaMessageError(f"Invalid checksum: {data.hex()}")
    return data


def to_celsius(fahrenheit: float) -> float:
    """Convert a Fahrenheit temperature to Celsius."""
    return 0.5 * round(((fahrenheit - 32) / 1.8) / 0.5)


def utcnow() -> datetime:
    """Get now in UTC time."""
    return datetime.now(timezone.utc)
