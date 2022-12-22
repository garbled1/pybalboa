"""pybalboa exceptions."""


class SpaConnectionError(ConnectionError):
    """Spa connection could not be established."""


class SpaMessageError(Exception):
    """Spa message is invalid."""
