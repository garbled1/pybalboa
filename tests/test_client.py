"""Tests module."""
from __future__ import annotations

import pytest

from pybalboa import SpaClient

HOST = "localhost"


@pytest.mark.asyncio
async def test_stil7(stil7_spa: int) -> None:
    """Test the spa client."""
    async with SpaClient(HOST, stil7_spa) as spa:
        assert spa.connected
        assert await spa.async_configuration_loaded()
        assert spa.configuration_loaded
        assert spa.pump_count == 1


@pytest.mark.asyncio
async def test_lpi501st(lpi501st: int) -> None:
    """Test the spa client."""
    async with SpaClient(HOST, lpi501st) as spa:
        assert spa.connected
        assert await spa.async_configuration_loaded()
        assert spa.configuration_loaded
        assert spa.pump_count == 2


@pytest.mark.asyncio
async def test_mxbp20(mxbp20: int) -> None:
    """Test the spa client."""
    async with SpaClient(HOST, mxbp20) as spa:
        assert spa.connected
        assert await spa.async_configuration_loaded()
        assert spa.configuration_loaded
        assert spa.pump_count == 2
