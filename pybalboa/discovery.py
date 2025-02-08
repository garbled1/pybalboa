"""Balboa spa discovery."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from socket import AF_INET, IPPROTO_UDP
from typing import Any

_LOGGER = logging.getLogger(__name__)

BROADCAST_ADDRESS = ("255.255.255.255", 30303)
BROADCAST_MESSAGE = b"Discovery"
BROADCAST_INTERVAL = 3


async def async_discover(
    return_once_found: bool = False, *, timeout: int = 10
) -> list[DiscoveredSpa]:
    """Discover spas on the network within a specified timeout."""
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: SpaDiscoveryProtocol(return_once_found),
        # local_addr=("0.0.0.0", 0),
        family=AF_INET,
        proto=IPPROTO_UDP,
        # reuse_port=True,
        allow_broadcast=True,
    )

    try:
        await asyncio.wait_for(protocol.discovery_complete.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        if not protocol.spas:
            _LOGGER.debug("Discovery timed out")
    finally:
        transport.close()

    return protocol.spas


@dataclass
class DiscoveredSpa:
    """Discovered spa."""

    address: str
    port: int
    mac_address: str
    hostname: str


class SpaDiscoveryProtocol(asyncio.DatagramProtocol):
    """Spa discovery protocol."""

    def __init__(self, return_once_found: bool = False) -> None:
        """Initialize a spa discovery protocol."""
        self.transport: asyncio.DatagramTransport | None = None
        self.broadcast_handle: asyncio.TimerHandle | None = None

        self.spas: list[DiscoveredSpa] = []
        self.discovery_complete = asyncio.Event()
        self.return_once_found = return_once_found

    def broadcast(self) -> None:
        """Send a broadcast message."""
        if self.return_once_found and self.spas:  # stop broadcasting if a spa is found
            self.discovery_complete.set()
            return
        if not (transport := self.transport) or transport.is_closing():
            return  # if the transport is closed, don't broadcast

        self.transport.sendto(BROADCAST_MESSAGE, BROADCAST_ADDRESS)
        _LOGGER.debug("UDP discovery broadcast sent")

        # Re-broadcast at BROADCAST_INTERVAL
        self.broadcast_handle = asyncio.get_running_loop().call_later(
            BROADCAST_INTERVAL, self.broadcast
        )

    def connection_lost(self, exc: Exception | None) -> None:
        """Called when the connection is lost or closed."""
        if self.broadcast_handle:
            self.broadcast_handle.cancel()

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:  # type: ignore[override]
        """Called when a connection is made."""
        self.transport = transport
        self.broadcast()

    def datagram_received(self, data: bytes, addr: tuple[str | Any, int]) -> None:
        """Called when some datagram is received."""
        _LOGGER.debug("Received response from %s: %s", addr[0], data)
        if b"BWGS" not in data.upper():
            return  # Unexpected response, ignore
        try:
            hostname, mac = map(str.strip, data.decode().splitlines()[:2])
            if (spa := DiscoveredSpa(*addr, mac, hostname)) not in self.spas:
                self.spas.append(spa)
            if self.return_once_found:
                self.discovery_complete.set()
        except Exception as ex:
            _LOGGER.error(ex)

    def error_received(self, exc: Exception) -> None:
        """Called when a send or receive operation raises an OSError."""
        _LOGGER.error(exc)
