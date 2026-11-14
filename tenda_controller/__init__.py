"""
Tenda HG7 GPON ONT Router Controller & Autonomous AI Ecosystem.

Author: Dulith Divisekara
"""

from .client import TendaClient
from .models import (
    DeviceStatus,
    PonStatus,
    ConnectedDevice,
    WifiConfig,
    PingResult,
    WanProfile,
    VoipConfig,
    AclRule,
    Tr069Config,
)
from .exceptions import (
    TendaError,
    TendaAuthError,
    TendaConnectionError,
    TendaSessionLockedError,
    TendaValidationError,
    TendaDangerousOperationError,
)

__version__ = "1.2.0"
__all__ = [
    "TendaClient",
    "DeviceStatus",
    "PonStatus",
    "ConnectedDevice",
    "WifiConfig",
    "PingResult",
    "WanProfile",
    "VoipConfig",
    "AclRule",
    "Tr069Config",
    "TendaError",
    "TendaAuthError",
    "TendaConnectionError",
    "TendaSessionLockedError",
    "TendaValidationError",
    "TendaDangerousOperationError",
]
