"""Tests module."""
import asyncio

from pybalboa.utils import (
    byte_parser,
    calculate_checksum,
    cancel_task,
    default,
    to_celsius,
)


def test_byte_parser() -> None:
    """Test byte_parser."""
    byte = int("0b01010101", 2)
    assert byte_parser(byte) == [1, 0] * 4
    assert byte_parser(byte, offset=1, count=3) == [0, 1, 0]
    assert byte_parser(byte, count=2, bits=2) == [1, 1]
    assert byte_parser(byte, offset=1, count=2, bits=2) == [2, 2]
    assert byte_parser(byte, count=3, bits=3) == [5, 2, 1]


def test_calculate_checksum() -> None:
    """Test calculate_checksum."""
    value = bytes.fromhex("1DFFAF13000064082D0000010000040000000000000000006400000006")
    assert calculate_checksum(value[:-1]) == value[-1]
    value = bytes.fromhex("050ABF0477")
    assert calculate_checksum(value[:-1]) == value[-1]


async def test_cancel_task() -> None:
    """Test cancel_task."""

    async def _long_wait() -> None:
        await asyncio.sleep(1000)

    task = asyncio.ensure_future(test_cancel_task())
    assert not task.done()
    await cancel_task(task)
    assert task.cancelled()


def test_default() -> None:
    """Test default."""
    assert default(12, 24) == 12
    assert default(None, 24) == 24


def test_to_celsius() -> None:
    """Test to_celsius."""
    assert to_celsius(32) == 0
    assert to_celsius(104) == 40
    assert to_celsius(80) == 26.5
