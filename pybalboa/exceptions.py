"""pybalboa exceptions."""


class SpaConnectionError(ConnectionError):
    """Spa connection could not be established."""


class SpaConfigurationNotLoadedError(Exception):
    """Raised when an operation requires a loaded spa configuration, but it has not been loaded."""

    def __init__(
        self,
        message: str = (
            "Spa configuration not loaded. "
            "Wait for async_configuration_loaded() to complete before proceeding."
        ),
    ):
        super().__init__(message)


class SpaMessageError(Exception):
    """Spa message is invalid."""
