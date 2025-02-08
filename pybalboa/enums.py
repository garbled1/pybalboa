"""Enums module."""

from __future__ import annotations

import logging
from enum import Enum, IntEnum

_LOGGER = logging.getLogger(__name__)


class MessageType(IntEnum):
    """Message type."""

    DEVICE_PRESENT = 0x04
    TOGGLE_STATE = 0x11
    STATUS_UPDATE = 0x13
    SET_TEMPERATURE = 0x20
    SET_TIME = 0x21
    REQUEST = 0x22
    FILTER_CYCLE = 0x23
    SYSTEM_INFORMATION = 0x24
    SETUP_PARAMETERS = 0x25
    PREFERENCES = 0x26
    SET_TEMPERATURE_UNIT = 0x27
    FAULT_LOG = 0x28
    DEVICE_CONFIGURATION = 0x2E
    SET_WIFI = 0x92
    MODULE_IDENTIFICATION = 0x94

    UNKNOWN = -1

    @classmethod
    def _missing_(cls, _: object) -> MessageType:
        """Return default if not found."""
        return cls.UNKNOWN


class SettingsCode(IntEnum):
    """Settings code."""

    DEVICE_CONFIGURATION = 0x00
    FILTER_CYCLE = 0x01
    SYSTEM_INFORMATION = 0x02
    SETUP_PARAMETERS = 0x04
    FAULT_LOG = 0x20

    UNKNOWN = -1

    @classmethod
    def _missing_(cls, _: object) -> SettingsCode:
        """Return default if not found."""
        return cls.UNKNOWN


class ControlType(Enum):
    """Control type."""

    AUX = "Aux"
    BLOWER = "Blower"
    CIRCULATION_PUMP = "Circulation pump"
    HEAT_MODE = "Heat mode"
    LIGHT = "Light"
    MISTER = "Mister"
    PUMP = "Pump"
    TEMPERATURE_RANGE = "Temperature range"


class AccessibilityType(IntEnum):
    """Accessibility type."""

    PUMP_LIGHT = 0
    NONE = 1
    ALL = 2


class HeatState(IntEnum):
    """Heat state."""

    OFF = 0
    HEATING = 1
    HEAT_WAITING = 2


class SpaState(IntEnum):
    """Spa state."""

    RUNNING = 0x00
    INITIALIZING = 0x01
    HOLD_MODE = 0x05
    AB_TEMPS_ON = 0x14
    TEST_MODE = 0x17

    UNKNOWN = -1

    @classmethod
    def _missing_(cls, value: object) -> SpaState:
        """Handle unknown values by returning UNKNOWN instead of raising an error."""
        _LOGGER.warning("Received unknown value %s for %s", value, cls.__name__)
        return cls.UNKNOWN


class TemperatureUnit(IntEnum):
    """Tempeature unit."""

    FAHRENHEIT = 0
    CELSIUS = 1


class ToggleItemCode(IntEnum):
    """Toggle item code."""

    NORMAL_OPERATION = 0x01
    CLEAR_NOTIFICATION = 0x03
    PUMP_1 = 0x04
    PUMP_2 = 0x05
    PUMP_3 = 0x06
    PUMP_4 = 0x07
    PUMP_5 = 0x08
    PUMP_6 = 0x09
    BLOWER = 0x0C
    MISTER = 0x0E
    LIGHT_1 = 0x11
    LIGHT_2 = 0x12
    LIGHT_3 = 0x13
    LIGHT_4 = 0x14
    AUX_1 = 0x16
    AUX_2 = 0x17
    SOAK_MODE = 0x1D
    HOLD_MODE = 0x3C
    CIRCULATION_PUMP = 0x3D
    TEMPERATURE_RANGE = 0x50
    HEAT_MODE = 0x51


class WiFiState(IntEnum):
    """Wi-Fi state."""

    OK = 0
    SPA_NOT_COMMUNICATING = 1
    STARTUP = 2
    PRIME = 3
    HOLD = 4
    PANEL = 5


class HeatMode(IntEnum):
    """Heat modes."""

    READY = 0
    REST = 1
    READY_IN_REST = 2


class LowHighRange(IntEnum):
    """Low/high range."""

    LOW = 0
    HIGH = 1


class OffOnState(IntEnum):
    """On/off state."""

    OFF = 0
    ON = 1


class OffLowHighState(IntEnum):
    """Off/low/high state."""

    OFF = 0
    LOW = 1
    HIGH = 2


class OffLowMediumHighState(IntEnum):
    """Off/low/medium/high state."""

    OFF = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class UnknownState(IntEnum):
    """Unknown state."""

    UNKNOWN = -1
