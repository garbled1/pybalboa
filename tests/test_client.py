"""Tests module."""
from __future__ import annotations

import pytest

from pybalboa import SpaClient
from pybalboa.enums import HeatMode, LowHighRange, OffLowHighState, OffOnState

from .conftest import SpaServer

HOST = "localhost"


@pytest.mark.asyncio
async def test_bfbp20s(bfbp20s: SpaServer) -> None:
    """Test the spa client."""
    async with SpaClient(HOST, bfbp20s.port) as spa:
        assert spa.connected
        assert await spa.async_configuration_loaded()
        assert spa.configuration_loaded
        assert spa.model == "BFBP20S"
        assert spa.pump_count == 1

        control = spa.pumps[0]
        assert control.name == "Pump 1"
        assert control.state == OffLowHighState.OFF
        assert control.options == list(OffLowHighState)

        control = spa.lights[0]
        assert control.name == "Light 1"
        assert control.state == OffOnState.ON
        assert control.options == list(OffOnState)
        await control.set_state(OffOnState.OFF)
        assert bfbp20s.received_messages[-1]

        control = spa.lights[1]
        assert control.name == "Light 2"
        assert control.state == OffOnState.OFF
        assert control.options == list(OffOnState)

        assert spa.circulation_pump
        control = spa.circulation_pump
        assert control.name == "Circulation pump"
        assert control.state == OffOnState.ON
        assert control.options == list(OffOnState)

        control = spa.temperature_range
        assert control.name == "Temperature range"
        assert control.state == LowHighRange.HIGH
        assert control.options == list(LowHighRange)

        control = spa.heat_mode
        assert control.name == "Heat mode"
        assert control.state == HeatMode.READY
        assert control.options == list(HeatMode)[:2]


@pytest.mark.asyncio
async def test_lpi501st(lpi501st: SpaServer) -> None:
    """Test the spa client."""
    async with SpaClient(HOST, lpi501st.port) as spa:
        assert spa.connected
        assert await spa.async_configuration_loaded()
        assert spa.configuration_loaded
        assert spa.model == "LPI501ST"
        assert spa.pump_count == 2

        control = spa.pumps[0]
        assert control.name == "Pump 1"
        assert control.state == OffLowHighState.OFF
        assert control.options == list(OffLowHighState)

        control = spa.pumps[1]
        assert control.name == "Pump 2"
        assert control.state == OffOnState.OFF
        assert control.options == list(OffOnState)


@pytest.mark.asyncio
async def test_mxbp20(mxbp20: SpaServer) -> None:
    """Test the spa client."""
    async with SpaClient(HOST, mxbp20.port) as spa:
        assert spa.connected
        assert await spa.async_configuration_loaded()
        assert spa.configuration_loaded
        assert spa.model == "MXBP20"
        assert spa.pump_count == 2

        control = spa.pumps[0]
        assert control.name == "Pump 1"
        assert control.state == OffLowHighState.OFF
        assert control.options == list(OffLowHighState)

        control = spa.pumps[1]
        assert control.name == "Pump 2"
        assert control.state == OffLowHighState.OFF
        assert control.options == list(OffLowHighState)


@pytest.mark.asyncio
async def test_bp501g1(bp501g1: SpaServer) -> None:
    """Test the spa client."""
    async with SpaClient(HOST, bp501g1.port) as spa:
        assert spa.connected
        assert await spa.async_configuration_loaded()
        assert spa.configuration_loaded
        assert spa.model == "BP501G1"
        assert spa.pump_count == 2

        assert len(spa.aux) == 0
        assert len(spa.blowers) == 0
        assert len(spa.lights) == 1
        assert len(spa.pumps) == 2

        control = spa.pumps[0]
        assert control.name == "Pump 1"
        assert control.state == OffLowHighState.LOW
        assert control.options == list(OffLowHighState)

        control = spa.pumps[1]
        assert control.name == "Pump 2"
        assert control.state == OffOnState.ON
        assert control.options == list(OffOnState)

        control = spa.lights[0]
        assert control.name == "Light 1"
        assert control.state == OffOnState.OFF
        assert control.options == list(OffOnState)
        await control.set_state(OffOnState.ON)
        assert bp501g1.received_messages[-1]

        assert spa.circulation_pump is None

        control = spa.temperature_range
        assert control.name == "Temperature range"
        assert control.state == LowHighRange.HIGH
        assert control.options == list(LowHighRange)

        control = spa.heat_mode
        assert control.name == "Heat mode"
        assert control.state == HeatMode.READY
        assert control.options == list(HeatMode)[:2]
