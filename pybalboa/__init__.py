"""Balboa spa module."""
__version__ = "1.0.0b2"

__uri__ = "https://github.com/garbled1/pybalboa"
__title__ = "pybalboa"
__description__ = "Interface Library for Balboa Spa"
__doc__ = __description__ + " <" + __uri__ + ">"
__author__ = "Tim Rightnour, Nathan Spencer"
__email__ = "root@garbled.net"
__license__ = "Apache 2.0"

__copyright__ = "Copyright (c) 2019 Tim Rightnour"

from .client import SpaClient
from .control import EVENT_UPDATE, SpaControl
from .exceptions import SpaConnectionError

__all__ = ["SpaClient", "SpaControl", "SpaConnectionError", "EVENT_UPDATE"]
