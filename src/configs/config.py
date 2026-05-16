"""FBMC configuration parameters."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Any
from src.enums import BaseCaseStrategy, GSKStrategy


def merge_config_overrides(
    config: "FBMCConfig" | None,
    config_overrides: dict[str, Any] | None,
) -> "FBMCConfig":
    """Return a config instance with validated field overrides applied."""
    base_config = config if config is not None else FBMCConfig()
    merged_values = deepcopy(vars(base_config))
    if not config_overrides:
        return FBMCConfig(**merged_values)

    valid_fields = {field.name for field in field_list(FBMCConfig)}
    unknown_fields = sorted(set(config_overrides) - valid_fields)
    if unknown_fields:
        raise ValueError(
            "Unknown config override field(s): "
            f"{', '.join(unknown_fields)}. "
            f"Valid fields are: {', '.join(sorted(valid_fields))}."
        )

    for key, value in config_overrides.items():
        if isinstance(value, dict) and isinstance(merged_values.get(key), dict):
            merged_values[key] = _deep_merge_dicts(merged_values[key], value)
        else:
            merged_values[key] = value

    _normalize_config_enums_in_place(merged_values)
    return FBMCConfig(**merged_values)


def coerce_enum_value(value: Any, enum_type: type[Enum], field_name: str) -> Enum:
    """Convert a string or enum instance to the requested enum member."""
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type[value]
        except KeyError:
            for member in enum_type:
                if member.value == value:
                    return member
    raise ValueError(
        f"Invalid value for {field_name}: {value}. "
        f"Expected one of: {', '.join(member.name for member in enum_type)} "
        f"or values: {', '.join(str(member.value) for member in enum_type)}."
    )


def _deep_merge_dicts(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge dict values where both sides are mappings."""
    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_config_enums_in_place(config_values: dict[str, Any]) -> None:
    """Normalize enum-like config values to enum members."""
    enum_fields: dict[str, type[Enum]] = {
        "base_case_strategy": BaseCaseStrategy,
        "cne_reference_case_flows": BaseCaseStrategy,
        "gsk_method": GSKStrategy,
    }
    for key, enum_type in enum_fields.items():
        if key in config_values and config_values[key] is not None:
            config_values[key] = coerce_enum_value(config_values[key], enum_type, key)


def field_list(config_type: type["FBMCConfig"]):
    return fields(config_type)



@dataclass
class FBMCConfig:
    """Configuration parameters for FBMC calculations."""
    reliability_margin_factor: float = 0.0
    min_ram: float = 0.0

    cne_setting: str = "all"  
    line_usage_threshold: float = 0.2
    cne_list: list[str] = None
    cne_reference_case_flows: BaseCaseStrategy = BaseCaseStrategy.NODAL_OPTIMUM
    security_constraint_bodf_size_threshold: float = 0.2
    security_constraint_bodf_columnwise_matrix_size_limit: int = 5_000_000

    # GSK Method options:
    # "ADJUSTABLE_CAP" - Share of Adjustable Capacity
    # "CURRENT_GENERATION" - Current Generation
    # "ITERATIVE_UNCERTAINTY" - Iterative Uncertainty
    # "ITERATIVE_FBMC" - Iterative FBMC
    
    # use the GSKStrategy class 
    gsk_method: str = 'CURRENT_GENERATION'
    gsk_kwargs: dict[str, dict[str, Any]] = field(default_factory=lambda: {
        'ADJUSTABLE_CAP': {
            "adjustable_carriers": ("CCGT", 'coal', 'lignite', 'OCGT', 'oil'),
        },
        'ITERATIVE_UNCERTAINTY': {
            "uncertain_carriers": ("offshore-wind", "onshore-wind"),
            "num_scenarios": 100,
            "gen_variation_std_dev": 0.5,
            "load_variation_std_dev": 0.5,
        },
        'ITERATIVE_FBMC': {
            "uncertain_carriers": ("offshore-wind", "onshore-wind"),
            "num_scenarios": 100,
            "max_gsk_iterations": 5,
            "initial_gsk_method": 'BUS_P',
            "gen_variation_std_dev": 0.5,
            "load_variation_std_dev": 0.5,
        },
        'MERIT_ORDER': {
            "standard_deviation": 5,
        },
        'BUS_P': {},
    })
    

    base_case_strategy: BaseCaseStrategy = BaseCaseStrategy.ZERO_FLOWS
    marginal_cost_load_shedding: float = 1e5
    

    add_security_constraints: bool = True
    

    advanced_hybrid_coupling_flag: bool = False

    run_redispatch: bool = True
    security_constrained_redispatch: bool = False
    deviation_factor_redispatch: float = 0.9