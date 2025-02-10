"""Tests module."""

from __future__ import annotations

from datetime import time, timedelta
from unittest.mock import patch

import pytest

from pybalboa import SpaClient
from pybalboa.enums import (
    HeatMode,
    LowHighRange,
    MessageType,
    OffLowHighState,
    OffOnState,
    SettingsCode,
    TemperatureUnit,
)

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
        assert spa.mac_address == "00:15:27:71:f1:9a"
        assert spa.software_version == "M100_220 V36.0"
        assert spa.pump_count == 1

        control = spa.pumps[0]
        assert control.name == "Pump 1"
        assert isinstance(control.state, OffLowHighState)
        assert control.state == OffLowHighState.OFF
        assert control.options == list(OffLowHighState)

        control = spa.lights[0]
        assert control.name == "Light 1"
        assert isinstance(control.state, OffOnState)
        assert control.state == OffOnState.ON
        assert control.options == list(OffOnState)
        await control.set_state(OffOnState.OFF)
        assert bfbp20s.received_messages[-1]

        control = spa.lights[1]
        assert control.name == "Light 2"
        assert isinstance(control.state, OffOnState)
        assert control.state == OffOnState.OFF
        assert control.options == list(OffOnState)

        assert spa.circulation_pump
        control = spa.circulation_pump
        assert control.name == "Circulation pump"
        assert isinstance(control.state, OffOnState)
        assert control.state == OffOnState.ON
        assert control.options == list(OffOnState)

        control = spa.temperature_range
        assert control.name == "Temperature range"
        assert isinstance(control.state, LowHighRange)
        assert control.state == LowHighRange.HIGH
        assert control.options == list(LowHighRange)

        control = spa.heat_mode
        assert control.name == "Heat mode"
        assert isinstance(control.state, HeatMode)
        assert control.state == HeatMode.READY
        assert control.options == list(HeatMode)[:2]

        with patch("pybalboa.client.SpaClient.send_message") as send_message:
            await spa.configure_filter_cycle(
                1, start=time(1, 30), duration=timedelta(hours=3, minutes=15)
            )
            # validate a configure filter cycle message was awaited
            expected_message = [MessageType.FILTER_CYCLE, 1, 30, 3, 15, 135, 0, 1, 5]
            send_message.assert_any_await(*expected_message)
            # validate a request filter cycle message was awaited
            send_message.assert_any_await(
                MessageType.REQUEST, SettingsCode.FILTER_CYCLE, 0x00, 0x00
            )

            send_message.reset_mock()
            await spa.configure_filter_cycle(
                2,
                start=time(13, 15),
                duration=timedelta(hours=3, minutes=45),
                enabled=False,
            )
            # validate a configure filter cycle message was awaited
            expected_message = [MessageType.FILTER_CYCLE, 19, 0, 2, 0, 13, 15, 3, 45]
            send_message.assert_any_await(*expected_message)


@pytest.mark.asyncio
async def test_lpi501st(lpi501st: SpaServer) -> None:
    """Test the spa client."""
    async with SpaClient(HOST, lpi501st.port) as spa:
        assert spa.connected
        assert await spa.async_configuration_loaded()
        assert spa.configuration_loaded
        assert spa.model == "LPI501ST"
        assert spa.mac_address == "00:15:27:73:d1:47"
        assert spa.software_version == "M100_201 V36.0"
        assert spa.pump_count == 2

        control = spa.pumps[0]
        assert control.name == "Pump 1"
        assert isinstance(control.state, OffLowHighState)
        assert control.state == OffLowHighState.OFF
        assert control.options == list(OffLowHighState)

        control = spa.pumps[1]
        assert control.name == "Pump 2"
        assert isinstance(control.state, OffOnState)
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
        assert isinstance(control.state, OffLowHighState)
        assert control.state == OffLowHighState.OFF
        assert control.options == list(OffLowHighState)

        control = spa.pumps[1]
        assert control.name == "Pump 2"
        assert isinstance(control.state, OffLowHighState)
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
        assert spa.mac_address == "00:15:27:73:5b:e2"
        assert spa.software_version == "M100_201 V20.0"
        assert spa.pump_count == 2

        assert len(spa.aux) == 0
        assert len(spa.blowers) == 0
        assert len(spa.lights) == 1
        assert len(spa.pumps) == 2

        assert spa.circulation_pump is None

        control = spa.pumps[0]
        assert control.name == "Pump 1"
        assert isinstance(control.state, OffLowHighState)
        assert control.state == OffLowHighState.LOW
        assert control.options == list(OffLowHighState)

        control = spa.pumps[1]
        assert control.name == "Pump 2"
        assert isinstance(control.state, OffOnState)
        assert control.state == OffOnState.ON
        assert control.options == list(OffOnState)

        control = spa.lights[0]
        assert control.name == "Light 1"
        assert isinstance(control.state, OffOnState)
        assert control.state == OffOnState.OFF
        assert control.options == list(OffOnState)
        await control.set_state(OffOnState.ON)
        assert bp501g1.received_messages[-1]

        control = spa.temperature_range
        assert control.name == "Temperature range"
        assert isinstance(control.state, LowHighRange)
        assert control.state == LowHighRange.HIGH
        assert control.options == list(LowHighRange)

        control = spa.heat_mode
        assert control.name == "Heat mode"
        assert isinstance(control.state, HeatMode)
        assert control.state == HeatMode.READY
        assert control.options == list(HeatMode)[:2]


@pytest.mark.asyncio
async def test_bp6013g1(bp6013g1: SpaServer) -> None:
    """Test the spa client."""
    async with SpaClient(HOST, bp6013g1.port) as spa:
        assert spa.connected
        assert await spa.async_configuration_loaded()
        assert spa.configuration_loaded
        assert spa.model == "BP6013G1"
        assert spa.mac_address == "00:15:27:e4:00:9d"
        assert spa.software_version == "M100_226 V43.0"
        assert spa.pump_count == 1

        assert len(spa.aux) == 0
        assert len(spa.blowers) == 1
        assert len(spa.lights) == 1
        assert len(spa.pumps) == 1

        assert spa.temperature_unit == TemperatureUnit.CELSIUS

        assert spa.circulation_pump

        control = spa.pumps[0]
        assert control.name == "Pump 1"
        assert isinstance(control.state, OffOnState)
        assert control.state == OffOnState.OFF
        assert control.options == list(OffOnState)

        control = spa.lights[0]
        assert control.name == "Light 1"
        assert isinstance(control.state, OffOnState)
        assert control.state == OffOnState.ON
        assert control.options == list(OffOnState)
        await control.set_state(OffOnState.OFF)
        assert bp6013g1.received_messages[-1]

        control = spa.blowers[0]
        assert control.name == "Blower 1"
        assert isinstance(control.state, OffOnState)
        assert control.state == OffOnState.OFF
        assert control.options == list(OffOnState)
        await control.set_state(OffOnState.ON)
        assert bp6013g1.received_messages[-1]

        control = spa.temperature_range
        assert control.name == "Temperature range"
        assert isinstance(control.state, LowHighRange)
        assert control.state == LowHighRange.HIGH
        assert control.options == list(LowHighRange)

        control = spa.heat_mode
        assert control.name == "Heat mode"
        assert isinstance(control.state, HeatMode)
        assert control.state == HeatMode.READY
        assert control.options == list(HeatMode)[:2]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "error_message", "method", "params"),
    [
        (
            ValueError,
            "Invalid filter cycle",
            "configure_filter_cycle",
            {"filter_cycle": None},
        ),
        (
            ValueError,
            "Invalid filter cycle",
            "configure_filter_cycle",
            {"filter_cycle": 3},
        ),
        (ValueError, "At least one of", "configure_filter_cycle", {"filter_cycle": 1}),
        (
            ValueError,
            "Only one of",
            "configure_filter_cycle",
            {"filter_cycle": 1, "end": time(), "duration": timedelta(hours=1)},
        ),
        (
            ValueError,
            "Filter cycle 1 cannot be disabled",
            "configure_filter_cycle",
            {"filter_cycle": 1, "start": time(), "enabled": False},
        ),
        (
            ValueError,
            "Filter cycle 1 requires",
            "configure_filter_cycle",
            {"filter_cycle": 1, "enabled": True},
        ),
        (
            ValueError,
            "Invalid duration",
            "configure_filter_cycle",
            {"filter_cycle": 1, "duration": timedelta()},
        ),
        (
            ValueError,
            "Invalid duration",
            "configure_filter_cycle",
            {"filter_cycle": 1, "duration": timedelta(minutes=5)},
        ),
        (ValueError, "Invalid fault log entry", "request_fault_log", {"entry": -1}),
        (ValueError, "Invalid fault log entry", "request_fault_log", {"entry": 25}),
        (ValueError, "Invalid temperature", "set_temperature", {"temperature": 0}),
        (ValueError, "Invalid time", "set_time", {"hour": 45, "minute": 0}),
    ],
)
async def test_client_errors(
    bfbp20s: SpaServer,
    error: Exception,
    error_message: str,
    method: str,
    params: dict | None,
) -> None:
    """Test the spa client."""
    async with SpaClient(HOST, bfbp20s.port) as spa:
        with pytest.raises(error, match=error_message):
            await getattr(spa, method)(**(params or {}))
