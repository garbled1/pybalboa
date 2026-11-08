"""Tests module."""

from __future__ import annotations

import asyncio
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


@pytest.mark.asyncio
async def test_require_first_frame_rejects_zombie(
    bfbp20s_silent: SpaServer,
) -> None:
    """A TCP handshake that never produces a spa frame is treated as failure."""
    spa = SpaClient(
        HOST,
        bfbp20s_silent.port,
        require_first_frame=True,
        first_frame_timeout=1,
    )
    try:
        assert await spa.connect() is False
        assert spa.connected is False
    finally:
        await spa.disconnect()


@pytest.mark.asyncio
async def test_require_first_frame_accepts_normal_spa(bfbp20s: SpaServer) -> None:
    """A responsive spa still connects successfully with the guard enabled."""
    async with SpaClient(
        HOST,
        bfbp20s.port,
        require_first_frame=True,
        first_frame_timeout=5,
    ) as spa:
        assert spa.connected
        assert await spa.async_configuration_loaded()
        assert spa.model == "BFBP20S"


@pytest.mark.asyncio
async def test_stale_teardown_closes_zombie_socket(
    bfbp20s_silent_after: SpaServer,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Listener tears down the writer after ``max_stale_windows`` of silence."""
    spa = SpaClient(
        HOST,
        bfbp20s_silent_after.port,
        stale_after=1,
        max_stale_windows=2,
    )
    try:
        assert await spa.connect()
        # Server stops responding ~1s after connect; after 2 silent windows
        # of 1s each, the listener should close the writer. The connection
        # monitor will reconnect quickly on localhost so we watch the log
        # for the tear-down warning rather than a transient `connected` flip.
        with caplog.at_level("WARNING", logger="pybalboa.client"):
            for _ in range(60):  # ~6s ceiling — enough for 1s + 2×1s + margin
                await asyncio.sleep(0.1)
                if any(
                    "tearing down zombie socket" in r.message for r in caplog.records
                ):
                    break
            else:  # pragma: no cover — only fires if tear-down never happened
                pytest.fail("stale_after tear-down never fired")
    finally:
        await spa.disconnect()


@pytest.mark.asyncio
async def test_default_kwargs_preserve_legacy_behavior(bfbp20s: SpaServer) -> None:
    """Constructing SpaClient without new kwargs."""
    spa = SpaClient(HOST, bfbp20s.port)
    assert spa._stale_after is None
    assert spa._require_first_frame is False
    # Backoff defaults reproduce the historical `min(1 * 2**attempt + jitter, 60)`.
    assert spa._backoff_initial == 1.0
    assert spa._backoff_factor == 2.0
    assert spa._backoff_max == 60.0
