"""
Domain exceptions for Tenda HG7 controller.
"""

class TendaError(Exception):
    """Base exception for all Tenda controller operations."""
    pass

class TendaAuthError(TendaError):
    """Raised when authentication against the router fails."""
    pass

class TendaConnectionError(TendaError):
    """Raised when the router cannot be reached over the network."""
    pass

class TendaSessionLockedError(TendaError):
    """Raised when an active session lock prevents concurrent management."""
    pass

class TendaValidationError(TendaError):
    """Raised when an invalid parameter or forbidden character is passed."""
    pass

class TendaDangerousOperationError(TendaError):
    """Raised when a command targets a protected subsystem (e.g. WAN, GPON PLOAM, Factory Reset)."""
    pass
