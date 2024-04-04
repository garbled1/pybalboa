"""Tests module."""

from pybalboa import __version__


def test_version() -> None:
    """Test the version."""
    assert __version__ == "1.0.1"
