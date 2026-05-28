"""FBMC configuration parameters."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from src.enums import BaseCaseStrategy, GSKStrategy


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_CONFIG_PATH = PROJECT_ROOT / "config" / "base_config.yaml"


def _default_config_values() -> dict[str, Any]:
    """Built-in fallback defaults used if YAML is absent or incomplete."""
    return {
        "reliability_margin_factor": 0.0,
        "min_ram": 0.0,
        "cne_setting": "all",
        "line_usage_threshold": 0.2,
        "cne_list": None,
        "cne_reference_case_flows": BaseCaseStrategy.NODAL_OPTIMUM,
        "security_constraint_bodf_size_threshold": 0.2,
        "security_constraint_bodf_columnwise_matrix_size_limit": 5_000_000,
        "gsk_strategy": GSKStrategy.CURRENT_GENERATION,
        "gsk_kwargs": {
            "ADJUSTABLE_CAP": {
                "adjustable_carriers": ("CCGT", "coal", "lignite", "OCGT", "oil"),
            },
            "ITERATIVE_UNCERTAINTY": {
                "uncertain_carriers": ("offshore-wind", "onshore-wind"),
                "num_scenarios": 100,
                "gen_variation_std_dev": 0.5,
                "load_variation_std_dev": 0.5,
            },
            "ITERATIVE_FBMC": {
                "uncertain_carriers": ("offshore-wind", "onshore-wind"),
                "num_scenarios": 100,
                "max_gsk_iterations": 5,
                "initial_gsk_strategy": "BUS_P",
                "gen_variation_std_dev": 0.5,
                "load_variation_std_dev": 0.5,
            },
            "MERIT_ORDER": {
                "standard_deviation": 5,
            },
            "BUS_P": {},
        },
        "base_case_strategy": BaseCaseStrategy.ZERO_FLOWS,
        "marginal_cost_load_shedding": 1e5,
        "add_security_constraints": True,
        "advanced_hybrid_coupling_flag": False,
        "fbmc_create_model_kwargs": {},
        "fbmc_solver_kwargs": {"solver_name": "gurobi"},
        "run_redispatch": True,
        "security_constrained_redispatch": False,
        "deviation_factor_redispatch": 0.9,
        "rd_create_model_kwargs": {},
        "rd_solver_kwargs": {"solver_name": "gurobi"},
        "transfer_limit_UA_flag": False,
        "transfer_limit_EUR_UA": None,
        "transfer_limit_UA_EUR": None,
        "net_position_limit_UA_flag": False,
        "net_position_UA_lower_limit": None,
        "net_position_UA_upper_limit": None,
    }


def load_base_config_yaml(path: Path = BASE_CONFIG_PATH) -> dict[str, Any]:
    """Load default config values from YAML and validate top-level keys."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected mapping in base config YAML, got: {type(loaded).__name__}.")
    return loaded


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
        "gsk_strategy": GSKStrategy,
    }
    for key, enum_type in enum_fields.items():
        if key in config_values and config_values[key] is not None:
            config_values[key] = coerce_enum_value(config_values[key], enum_type, key)


def field_list(config_type: type["FBMCConfig"]):
    return fields(config_type)


def _to_jsonable(value: Any) -> Any:
    """Recursively convert config values into JSON-serializable primitives."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _to_jsonable(inner_value) for key, inner_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(inner_value) for inner_value in value]
    return value


def config_to_dict(config: "FBMCConfig") -> dict[str, Any]:
    """Return a JSON-friendly representation of the config."""
    return _to_jsonable(asdict(config))



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
    gsk_strategy: str = "CURRENT_GENERATION"
    gsk_kwargs: dict[str, dict[str, Any]] = field(default_factory=lambda: {
        "ADJUSTABLE_CAP": {
            "adjustable_carriers": ("CCGT", "coal", "lignite", "OCGT", "oil"),
        },
        "ITERATIVE_UNCERTAINTY": {
            "uncertain_carriers": ("offshore-wind", "onshore-wind"),
            "num_scenarios": 100,
            "gen_variation_std_dev": 0.5,
            "load_variation_std_dev": 0.5,
        },
        "ITERATIVE_FBMC": {
            "uncertain_carriers": ("offshore-wind", "onshore-wind"),
            "num_scenarios": 100,
            "max_gsk_iterations": 5,
            "initial_gsk_strategy": "BUS_P",
            "gen_variation_std_dev": 0.5,
            "load_variation_std_dev": 0.5,
        },
        "MERIT_ORDER": {
            "standard_deviation": 5,
        },
        "BUS_P": {},
    })

    base_case_strategy: BaseCaseStrategy = BaseCaseStrategy.ZERO_FLOWS
    marginal_cost_load_shedding: float = 1e5
    

    add_security_constraints: bool = True
    

    advanced_hybrid_coupling_flag: bool = False

    fbmc_create_model_kwargs: dict[str, Any] = field(default_factory=dict)

    fbmc_solver_kwargs: dict[str, Any] = field(default_factory=lambda: {"solver_name": "gurobi"})

    run_redispatch: bool = True
    security_constrained_redispatch: bool = False
    deviation_factor_redispatch: float = 0.9
    rd_create_model_kwargs: dict[str, Any] = field(default_factory=dict)
    rd_solver_kwargs: dict[str, Any] = field(default_factory=lambda: {"solver_name": "gurobi"})

    use_unit_commitment: bool = False
    unit_commitment_path: str = "data/unit_commitment.csv"

    # Water values config
    load_water_values: bool = False  # Whether to load water values in case creation
    water_values_path: str = None  # Optional: path to water values file

    transfer_limit_UA_flag: bool = False  # Whether to apply an upper limit on total transfer in UA market design
    transfer_limit_EUR_UA: float = None  # Value for upper limit on total transfer in UA market design (if flag is True)
    transfer_limit_UA_EUR: float = None  # Value for upper limit on total transfer in UA market design (if flag is True)

    net_position_limit_UA_flag: bool = False  # Whether to apply a limit on net position in UA market design
    net_position_UA_lower_limit: float = None  # Value for lower limit on net position of Ukraine
    net_position_UA_upper_limit: float = None  # Value for upper limit on net position of Ukraine

    def __str__(self) -> str:
        """Return a readable multi-line view of the effective configuration."""
        config_dump = yaml.safe_dump(
            config_to_dict(self),
            sort_keys=False,
            default_flow_style=False,
        ).rstrip()
        return f"FBMCConfig:\n{config_dump}"

    @classmethod
    def from_base_yaml(cls, path: Path = BASE_CONFIG_PATH) -> "FBMCConfig":
        """Construct config by overlaying base YAML on top of built-in defaults."""
        merged_values = deepcopy(_default_config_values())
        yaml_values = load_base_config_yaml(path)

        valid_fields = {field.name for field in field_list(cls)}
        unknown_fields = sorted(set(yaml_values) - valid_fields)
        if unknown_fields:
            raise ValueError(
                "Unknown base config field(s): "
                f"{', '.join(unknown_fields)}. "
                f"Valid fields are: {', '.join(sorted(valid_fields))}."
            )

        for key, value in yaml_values.items():
            if isinstance(value, dict) and isinstance(merged_values.get(key), dict):
                merged_values[key] = _deep_merge_dicts(merged_values[key], value)
            else:
                merged_values[key] = value

        _normalize_config_enums_in_place(merged_values)
        return cls(**merged_values)