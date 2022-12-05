"""Balboa spa module."""
__version__ = "1.0.0"

__uri__ = "https://github.com/garbled1/pybalboa"
__title__ = "pybalboa"
__description__ = "Interface Library for Balboa Spa"
__doc__ = __description__ + " <" + __uri__ + ">"
__author__ = "Tim Rightnour, Nathan Spencer"
__email__ = "root@garbled.net"
__license__ = "Apache 2.0"

__copyright__ = "Copyright (c) 2019 Tim Rightnour"

from .client import SpaClient

__all__ = ["SpaClient"]

if __name__ == "__main__":
    print(__version__)
