"""Flow-Based Market Coupling (FBMC) extension for PyPSA."""

from .api import run_fbmc
from .core.input_network_conversions.network_conversion import nodal_to_zonal
from .settings import FBMCConfig, merge_config_overrides
from .enums import GSKStrategy, BaseCaseStrategy

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
