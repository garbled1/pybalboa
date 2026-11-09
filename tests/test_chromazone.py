"""Tests for Chromazone lighting (read only)."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
from collections.abc import Callable

import pytest

from pybalboa import Chromazone, ChromazoneZone, SpaClient
from pybalboa.chromazone import CHROMAZONE_ZONE_NAMES
from pybalboa.client import EVENT_UPDATE
from pybalboa.enums import ChromazoneEffect, MessageType

from .conftest import SpaServer

HOST = "localhost"


def payload(message: str) -> bytes:
    """Return the payload of a hex message (length, channel, type ... checksum)."""
    return bytes.fromhex(message)[4:-1]


def three_colour_zones() -> dict[str, str]:
    """Load the 2022 capture of a spa with three colour zones (14-byte config)."""
    with open(
        "tests/fixtures/chromazone_three_colour_zones.json", encoding="utf-8"
    ) as file:
        data: dict[str, str] = json.load(file)
    return data


async def wait_for(condition: Callable[[], bool], timeout: float = 3) -> None:
    """Wait until condition() is true."""
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_mqbp20ux(mqbp20ux: SpaServer, caplog: pytest.LogCaptureFixture) -> None:
    """A spa with a colour zone, a white zone and a status indicator."""
    caplog.set_level(logging.DEBUG, logger="pybalboa")
    async with SpaClient(HOST, mqbp20ux.port) as spa:
        updates: list[None] = []
        spa.on(EVENT_UPDATE, lambda: updates.append(None))
        assert await spa.async_configuration_loaded()
        await wait_for(
            lambda: (
                spa.chromazone is not None
                and spa.chromazone.raw_configuration is not None
                and spa.chromazone.palette is not None
            )
        )
        chromazone = spa.chromazone
        assert chromazone is not None

        # the client asked for configuration (0e 00 00) and palette (0e 00 01)
        requests = [
            message[4:7]
            for message in mqbp20ux.received_messages
            if message[3] == MessageType.CHROMAZONE_COMMAND
        ]
        assert bytes.fromhex("0e0000") in requests
        assert bytes.fromhex("0e0001") in requests

        assert chromazone.raw_configuration == payload(
            mqbp20ux.messages["chromazone_configuration"]
        )
        assert chromazone.raw_palette == payload(
            mqbp20ux.messages["chromazone_palette"]
        )
        palette = chromazone.palette
        assert palette is not None
        assert len(palette) == 8
        assert palette[0] == (0xFF, 0xFF, 0xFF)
        assert palette[6] == (0xFF, 0x64, 0x00)

        zones = chromazone.zones
        assert list(zones) == ["A", "B", "C"]

        zone_a = zones["A"]
        assert zone_a.name == "Interior"
        assert zone_a.is_light and zone_a.is_on
        assert zone_a.supports_color is True
        assert zone_a.color_index == 6
        assert zone_a.rgb == (0xFF, 0x64, 0x00)
        assert zone_a.brightness == 100
        assert zone_a.effect is None
        assert not zone_a.is_custom_color

        zone_b = zones["B"]
        assert zone_b.name == "Exterior"
        assert zone_b.is_light and zone_b.is_on
        assert zone_b.supports_color is False
        assert zone_b.color_index == 0
        assert zone_b.brightness == 22

        zone_c = zones["C"]
        assert zone_c.name == "Cabinet"
        assert zone_c.is_indicator
        assert not zone_c.is_light and not zone_c.is_on
        assert zone_c.supports_color is None
        assert zone_c.rgb == (0x00, 0xFF, 0x00)

        assert [zone.zone for zone in chromazone.lights] == ["A", "B"]
        assert updates

    assert "Chromazone lighting detected" in caplog.text
    assert "possible Chromazone flag" in caplog.text
    assert "Chromazone configuration (18 bytes): 0e 00 83 81" in caplog.text
    assert "zone A (Interior): palette colour 7 (#ff6400)" in caplog.text
    assert "zone C (Cabinet): status indicator #00ff00 [not a light]" in caplog.text


@pytest.mark.asyncio
async def test_mqbp20ux_status_pro(mqbp20ux_status_pro: SpaServer) -> None:
    """A spa that sends Chromazone status but never answers for configuration."""
    async with SpaClient(HOST, mqbp20ux_status_pro.port) as spa:
        assert await spa.async_configuration_loaded()
        await wait_for(
            lambda: spa.chromazone is not None and bool(spa.chromazone.zones)
        )
        chromazone = spa.chromazone
        assert chromazone is not None
        assert chromazone.raw_configuration is None
        assert chromazone.palette is None

        zones = chromazone.zones
        assert not zones["A"].is_light
        assert not zones["B"].is_light
        assert zones["C"].is_indicator
        assert zones["C"].rgb == (0x00, 0xFF, 0x00)
        assert chromazone.lights == []
        assert all(zone.name is None for zone in zones.values())


@pytest.mark.asyncio
async def test_no_chromazone(bfbp20s: SpaServer) -> None:
    """A spa without Chromazone has no chromazone."""
    async with SpaClient(HOST, bfbp20s.port) as spa:
        assert await spa.async_configuration_loaded()
        await asyncio.sleep(0.2)
        assert spa.chromazone is None


def test_three_colour_zones() -> None:
    """The 14-byte configuration has no names and zero capability bytes."""
    capture = three_colour_zones()
    chromazone = Chromazone()

    assert chromazone.update_configuration(payload(capture["configuration"]))
    assert not chromazone.update_configuration(payload(capture["configuration"]))
    assert chromazone.update_palette(payload(capture["palette"]))
    assert chromazone.zones == {}

    # all off: nothing known about the zones yet
    assert chromazone.update_status(payload(capture["status_off"]))
    assert chromazone.lights == []
    assert all(not zone.is_indicator for zone in chromazone.zones.values())

    # all white: lights, colour still unknown
    chromazone.update_status(payload(capture["status_all_white"]))
    assert [zone.zone for zone in chromazone.lights] == ["A", "B", "C"]
    assert all(zone.supports_color is None for zone in chromazone.lights)
    assert all(zone.name is None for zone in chromazone.lights)

    chromazone.update_status(payload(capture["status_a_red_b_blue_c_green"]))
    zones = chromazone.zones
    assert all(zone.supports_color for zone in zones.values())
    assert zones["A"].rgb == (0xFF, 0, 0)
    assert zones["B"].color_index == 2
    assert zones["C"].rgb == (0, 0xFF, 0)

    chromazone.update_status(payload(capture["status_all_color_wheel"]))
    zones = chromazone.zones
    assert all(zone.effect == ChromazoneEffect.COLOR_WHEEL for zone in zones.values())
    assert zones["A"].speed == 2

    chromazone.update_status(payload(capture["status_a_party_b_yellow"]))
    zones = chromazone.zones
    assert zones["A"].effect == ChromazoneEffect.PARTY
    assert zones["B"].rgb == (0xFF, 0xFF, 0)
    assert zones["C"].is_light and not zones["C"].is_on

    chromazone.update_status(payload(capture["status_all_lounge"]))
    assert all(
        zone.effect == ChromazoneEffect.LOUNGE for zone in chromazone.zones.values()
    )

    chromazone.update_status(payload(capture["status_ab_custom_color"]))
    zones = chromazone.zones
    assert zones["A"].is_custom_color
    assert zones["A"].rgb == (0xD9, 0x74, 0x6A)
    assert zones["A"].describe() == (
        "zone A: custom colour #d9746a, brightness 100 [colour light]"
    )

    # a zone that has been lit stays a light, never an indicator
    chromazone.update_status(payload(capture["status_c_only_green"]))
    assert not chromazone.zones["C"].is_indicator
    assert chromazone.zones["C"].is_light


def test_status_and_names() -> None:
    """Short messages are ignored, unknown names are kept, zones are frozen."""
    chromazone = Chromazone()
    assert not chromazone.update_status(b"\x01\x00")
    assert not chromazone.update_palette(b"\x00")

    configuration = bytearray.fromhex("0e0083810000000000000501060604131407")
    configuration[15] = len(CHROMAZONE_ZONE_NAMES)  # a name we don't know
    configuration[16] = 0  # no name
    chromazone.update_configuration(bytes(configuration))
    chromazone.update_status(bytes.fromhex("0110180064ff0000010064ffffff000000000000"))
    zones = chromazone.zones
    assert zones["A"].name == f"Name {len(CHROMAZONE_ZONE_NAMES)}"
    assert zones["B"].name is None
    assert zones["A"].effect == ChromazoneEffect.COLOR_WHEEL
    assert zones["A"].describe().startswith("zone A (Name 21): color_wheel, speed 24")

    zone = zones["A"]
    assert isinstance(zone, ChromazoneZone)
    with pytest.raises(dataclasses.FrozenInstanceError):
        zone.mode = 0  # type: ignore[misc]

    # an unknown light show mode
    chromazone.update_status(bytes.fromhex("0112010064ff0000010064ffffff000000000000"))
    assert chromazone.zones["A"].effect is None
    assert "mode 12" in chromazone.zones["A"].describe()
