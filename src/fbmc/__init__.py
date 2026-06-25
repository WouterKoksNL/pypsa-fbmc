"""Flow-Based Market Coupling (FBMC) extension for PyPSA."""

from . import accessor as accessor  # registers pypsa.Network.fbmc on import
from .api import run_fbmc
from .input_network_conversions.network_conversion import nodal_to_zonal
from .settings import FBMCConfig as FBMCConfig
from .settings import merge_config_overrides
from .enums import GSKStrategy as GSKStrategy
from .enums import BaseCaseStrategy as BaseCaseStrategy
from .enums import CNECStrategy as CNECStrategy
from .types import FBMCResult, DispatchResult

__all__ = [
    "run_fbmc",
    "FBMCConfig",
    "merge_config_overrides",
    "GSKStrategy",
    "BaseCaseStrategy",
    "create_case",
    "FBMCResult",
    "DispatchResult",
    "nodal_to_zonal",
]
