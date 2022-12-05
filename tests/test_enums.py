"""Tests module."""
from pybalboa.enums import MessageType


def test_message_type() -> None:
    """Test message type parsing."""
    assert MessageType([0x0A, 0xBF, 0x22]) == MessageType.PANEL_REQUEST
    assert MessageType([0x99] * 3) == MessageType.UNKNOWN
