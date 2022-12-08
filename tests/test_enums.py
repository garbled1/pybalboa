"""Tests module."""
from pybalboa.enums import MessageType, SettingsCode


def test_enum_parsing() -> None:
    """Test enum parsing."""
    assert MessageType(0x22) == MessageType.REQUEST
    assert MessageType(0x99) == MessageType.UNKNOWN
    assert SettingsCode(0x20) == SettingsCode.FAULT_LOG
    assert SettingsCode(0x99) == SettingsCode.UNKNOWN
