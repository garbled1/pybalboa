"""Enums module."""
from __future__ import annotations

from enum import Enum, IntEnum


class MessageType2(IntEnum):
    """Message type."""

    DEVICE_PRESENT = 0x04
    TOGGLE_STATE = 0x11
    STATUS_UPDATE = 0x13
    SET_TEMPERATURE = 0x20
    SET_TIME = 0x21
    SETTINGS_REQUEST = 0x22
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
    def _missing_(cls, _: object) -> MessageType2:
        """Return default if not found."""
        return cls.UNKNOWN


class SettingsCode(IntEnum):
    """Settings code."""

    DEVICE_CONFIGURATION = 0x00
    FILTER_CYCLE = 0x01
    SYSTEM_INFORMATION = 0x02
    SETUP_PARAMETERS = 0x04
    FAULT_LOG = 0x20


class MessageType(Enum):
    """Message types."""

    DEVICE_PRESENT = [0x0A, 0xBF, 0x04]

    PANEL_REQUEST = [0x0A, 0xBF, 0x22]
    DEVICE_CONFIGURATION_REQUEST = [*PANEL_REQUEST, 0x00, 0x00, 0x01]
    FAULT_LOG_REQUEST = [*PANEL_REQUEST, 0x20]
    FILTER_CYCLE_REQUEST = [*PANEL_REQUEST, 0x01, 0x00, 0x00]
    SETUP_PARAMETERS_REQUEST = [*PANEL_REQUEST, 0x04, 0x00, 0x00]
    STATUS_UPDATE_REQUEST = [*PANEL_REQUEST, 0x00, 0x00, 0x00]
    SYSTEM_INFORMATION_REQUEST = [*PANEL_REQUEST, 0x02, 0x00, 0x00]

    DEVICE_CONFIGURATION = [0x0A, 0xBF, 0x2E]
    FAULT_LOG = [0x0A, 0xBF, 0x28]
    FILTER_CYCLE = [0x0A, 0xBF, 0x23]
    MODULE_IDENTIFICATION = [0x0A, 0xBF, 0x94]
    PREFERENCES = [0xFF, 0xAF, 0x26]
    SETUP_PARAMETERS = [0x0A, 0xBF, 0x25]
    STATUS_UPDATE = [0xFF, 0xAF, 0x13]
    SYSTEM_INFORMATION = [0x0A, 0xBF, 0x24]

    SET_TEMPERATURE = [0x0A, 0xBF, 0x20]
    SET_TEMPERATURE_UNIT = [0x0A, 0xBF, 0x27, 0x01]
    SET_TIME = [0x0A, 0xBF, 0x21]
    SET_WIFI = [0x0A, 0xBF, 0x92]

    TOGGLE_STATE = [0x0A, 0xBF, 0x11]
    TOGGLE_HEAT_MODE = [*TOGGLE_STATE, 0x51]
    TOGGLE_TEMPERATURE_RANGE = [*TOGGLE_STATE, 0x50]

    UNKNOWN: list[int] = []

    @classmethod
    def _missing_(cls, _: object) -> MessageType:
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


class TemperatureUnit(IntEnum):
    """Tempeature unit."""

    FAHRENHEIT = 0
    CELSIUS = 1


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
