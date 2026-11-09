"""Balboa Chromazone (Chromazon3) lighting, read only.

Chromazone is a separate lighting module on the spa's panel bus with up to three
zones (A, B, C). The controller broadcasts its messages, so they arrive on the
Wi-Fi channel like any other status message.

0x32 - status, about once a second, 19 bytes::

    00     01 (always seen)
    01-06  zone A: mode, speed, brightness, red, green, blue
    07-12  zone B: same
    13-18  zone C: same

    mode        00 off, 01-08 palette colour 1-8, 09 custom colour (any RGB),
                10 Color Wheel, 11 Party, 13 Lounge (see ChromazoneEffect)
    speed       effect speed as a duration: one full Color Wheel cycle takes
                about 5 s per unit (1 -> 5 s, 2 -> 10 s, 6 -> 30 s, 12 -> 60 s);
                0 pauses. The panel offers 2, 4, 6, 12 and 24.
    brightness  0-100
    RGB         the colour the zone shows right now (changes while an effect runs)

A zone set up as a status indicator (e.g. "Status Pro") reports mode 00 while
showing a colour (green = spa OK); it is not a light.

0x33 - configuration, sent in reply to a 0x31 ``0e 00 00`` request. Two layouts
are known::

    18 bytes  0e 00 83 81 00 00 00 00 00 00 05 01 06 06 04 13 14 07   (MQBP20UX, 2026)
    14 bytes  10 00 00 00 07 03 00 00 00 00 05 01 00 06               (2022 capture)

    18-byte layout:
    02-04  zone A-C, probably capability: 0x80 zone in use, 0x02 colour
           (A 83 colour, B 81 white only, C 00 status indicator on the spa it
           was decoded on; but the 14-byte layout shows 00 for three colour
           zones, so this is only used as a hint)
    12-14  zone A-C, unknown (function or light type?)
    15-17  zone A-C name index (CHROMAZONE_ZONE_NAMES), set with the panel
    other bytes unknown

0x34 - palette, sent in reply to a 0x31 ``0e 00 01`` request, 25 bytes:
``00`` then 8 x RGB (palette colours 1-8).

0x31 messages are commands (the panel's, echoed by the controller); they are
not used here yet.

Raw configuration and palette bytes are kept (``raw_configuration``,
``raw_palette``) so that undecoded parts can be compared across spas.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .enums import ChromazoneEffect

_LOGGER = logging.getLogger(__name__)

RGB = tuple[int, int, int]

CHROMAZONE_ZONES = ("A", "B", "C")
STATUS_LENGTH = 19
PALETTE_LENGTH = 25
NAMED_CONFIGURATION_LENGTH = 18

MODE_OFF = 0x00
MODE_CUSTOM_COLOR = 0x09
MODE_EFFECT = 0x10

CAPABILITY_IN_USE = 0x80
CAPABILITY_COLOR = 0x02

# Zone name list of the topside panel; configuration bytes 15-17 hold the index.
CHROMAZONE_ZONE_NAMES: tuple[str | None, ...] = (
    None,
    "Water",
    "Water 1",
    "Water 2",
    "Water 3",
    "Accent",
    "Perimeter",
    "Cabinet",
    "Outside",
    "Outside 1",
    "Outside 2",
    "Outside 3",
    "Steps",
    "Entry",
    "Adult",
    "Cool Down",
    "Captains Chair",
    "Main",
    "Jets",
    "Interior",
    "Exterior",
)


@dataclass(frozen=True)
class ChromazoneZone:
    """State of one Chromazone zone (a snapshot; replaced on every change)."""

    zone: str
    mode: int = MODE_OFF
    speed: int = 0
    brightness: int = 0
    rgb: RGB = (0, 0, 0)
    name: str | None = None
    is_light: bool = False
    supports_color: bool | None = None
    is_indicator: bool = False

    @property
    def is_on(self) -> bool:
        """Return True if the zone is a light and is lit."""
        return self.is_light and self.mode != MODE_OFF

    @property
    def effect(self) -> ChromazoneEffect | None:
        """Return the running light show, if any."""
        if self.mode < MODE_EFFECT:
            return None
        try:
            return ChromazoneEffect(self.mode)
        except ValueError:
            return None

    @property
    def color_index(self) -> int | None:
        """Return the palette index (0-7) of a solid palette colour."""
        return self.mode - 1 if 1 <= self.mode <= 8 else None

    @property
    def is_custom_color(self) -> bool:
        """Return True if the zone shows a custom (non-palette) colour."""
        return self.mode == MODE_CUSTOM_COLOR

    def describe(self) -> str:
        """Return a one-line, human readable description (used for logging)."""
        name = f" ({self.name})" if self.name else ""
        colour = "#{:02x}{:02x}{:02x}".format(*self.rgb)
        if self.is_indicator:
            state = f"status indicator {colour}"
        elif self.mode == MODE_OFF:
            state = "off"
        elif (index := self.color_index) is not None:
            state = f"palette colour {index + 1} ({colour})"
        elif self.is_custom_color:
            state = f"custom colour {colour}"
        elif (effect := self.effect) is not None:
            state = f"{effect.name.lower()}, speed {self.speed}"
        else:
            state = f"mode {self.mode:02x}, speed {self.speed}, {colour}"
        if self.mode != MODE_OFF:
            state += f", brightness {self.brightness}"
        kind = (
            "colour light"
            if self.is_light and self.supports_color
            else "white light"
            if self.is_light and self.supports_color is False
            else "light"
            if self.is_light
            else "not a light"
        )
        return f"zone {self.zone}{name}: {state} [{kind}]"


class Chromazone:
    """Chromazone lighting state, built from 0x32 / 0x33 / 0x34 messages."""

    def __init__(self, log_prefix: str = "") -> None:
        """Initialize."""
        self._log_prefix = log_prefix
        self._zones: dict[str, ChromazoneZone] = {}
        self._raw_configuration: bytes | None = None
        self._raw_palette: bytes | None = None
        self._palette: list[RGB] | None = None
        self._capabilities: dict[str, int] = {}
        self._names: dict[str, str | None] = {}
        self._seen_lit: set[str] = set()
        self._seen_color: set[str] = set()
        self._indicators: set[str] = set()

    @property
    def zones(self) -> dict[str, ChromazoneZone]:
        """Return the zones reported by the spa, keyed "A", "B", "C"."""
        return dict(self._zones)

    @property
    def lights(self) -> list[ChromazoneZone]:
        """Return the zones that are lights."""
        return [zone for zone in self._zones.values() if zone.is_light]

    @property
    def palette(self) -> list[RGB] | None:
        """Return the 8 palette colours, once received."""
        return list(self._palette) if self._palette is not None else None

    @property
    def raw_configuration(self) -> bytes | None:
        """Return the 0x33 configuration payload as received."""
        return self._raw_configuration

    @property
    def raw_palette(self) -> bytes | None:
        """Return the 0x34 palette payload as received."""
        return self._raw_palette

    def update_status(self, data: bytes) -> bool:
        """Process a 0x32 status payload. Return True if anything changed."""
        if len(data) < STATUS_LENGTH:
            _LOGGER.debug(
                "%s ## short Chromazone status: %s", self._log_prefix, data.hex()
            )
            return False
        changed = False
        for index, zone_id in enumerate(CHROMAZONE_ZONES):
            mode, speed, brightness, red, green, blue = data[
                1 + 6 * index : 7 + 6 * index
            ]
            if mode != MODE_OFF:
                self._seen_lit.add(zone_id)
                if mode != 1:  # anything but palette colour 1 (white) shows colour
                    self._seen_color.add(zone_id)
            elif brightness and (red or green or blue):
                self._indicators.add(zone_id)
            new = self._build(zone_id, mode, speed, brightness, (red, green, blue))
            changed |= self._store(new)
        return changed

    def update_configuration(self, data: bytes) -> bool:
        """Process a 0x33 configuration payload. Return True if it changed."""
        if data == self._raw_configuration:
            return False
        self._raw_configuration = bytes(data)
        # capability and name bytes are only known in the 18-byte layout; in the
        # 14-byte one, byte 4 is 07 on a spa with three colour zones
        self._capabilities = {}
        self._names = {}
        if len(data) >= NAMED_CONFIGURATION_LENGTH:
            self._capabilities = {
                zone_id: data[2 + index]
                for index, zone_id in enumerate(CHROMAZONE_ZONES)
                if data[2 + index]
            }
            for index, zone_id in enumerate(CHROMAZONE_ZONES):
                name_index = data[15 + index]
                self._names[zone_id] = (
                    CHROMAZONE_ZONE_NAMES[name_index]
                    if name_index < len(CHROMAZONE_ZONE_NAMES)
                    else f"Name {name_index}"
                )
        _LOGGER.debug(
            "%s -- Chromazone configuration (%d bytes): %s",
            self._log_prefix,
            len(data),
            data.hex(" "),
        )
        for zone_id in CHROMAZONE_ZONES:
            if zone_id in self._zones:
                self._store(self._zones[zone_id], force=True)
        return True

    def update_palette(self, data: bytes) -> bool:
        """Process a 0x34 palette payload. Return True if it changed."""
        if len(data) < PALETTE_LENGTH or data == self._raw_palette:
            return False
        self._raw_palette = bytes(data)
        self._palette = [
            (data[1 + 3 * i], data[2 + 3 * i], data[3 + 3 * i]) for i in range(8)
        ]
        _LOGGER.debug(
            "%s -- Chromazone palette: %s",
            self._log_prefix,
            " ".join("#{:02x}{:02x}{:02x}".format(*c) for c in self._palette),
        )
        return True

    def _build(
        self, zone_id: str, mode: int, speed: int, brightness: int, rgb: RGB
    ) -> ChromazoneZone:
        capability = self._capabilities.get(zone_id, 0)
        is_indicator = zone_id in self._indicators and zone_id not in self._seen_lit
        is_light = not is_indicator and (
            zone_id in self._seen_lit or bool(capability & CAPABILITY_IN_USE)
        )
        if capability:
            supports_color: bool | None = bool(capability & CAPABILITY_COLOR)
        elif zone_id in self._seen_color:
            supports_color = True
        else:
            supports_color = None
        return ChromazoneZone(
            zone=zone_id,
            mode=mode,
            speed=speed,
            brightness=brightness,
            rgb=rgb,
            name=self._names.get(zone_id),
            is_light=is_light,
            supports_color=supports_color if is_light else None,
            is_indicator=is_indicator,
        )

    def _store(self, zone: ChromazoneZone, force: bool = False) -> bool:
        """Store a zone (rebuilding derived fields when forced); log notable changes."""
        if force:
            zone = self._build(
                zone.zone, zone.mode, zone.speed, zone.brightness, zone.rgb
            )
        old = self._zones.get(zone.zone)
        if old == zone:
            return False
        self._zones[zone.zone] = zone
        # an effect changes the colour every second - only log the rest
        if (
            old is None
            or force
            or (old.mode, old.speed, old.brightness, old.name, old.is_light)
            != (zone.mode, zone.speed, zone.brightness, zone.name, zone.is_light)
            or (zone.effect is None and old.rgb != zone.rgb)
        ):
            _LOGGER.debug("%s -- Chromazone %s", self._log_prefix, zone.describe())
        return True
