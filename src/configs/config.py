"""FBMC configuration parameters."""

from dataclasses import dataclass, field
from typing import Any
from src.enums import BaseCaseStrategy



@dataclass
class FBMCConfig:
    """Configuration parameters for FBMC calculations."""
    reliability_margin_factor: float = 0.0
    min_ram: float = 0.0

    cne_setting: str = "utilization_threshold"  
    line_usage_threshold: float = 0.2
    cne_list: list[str] = None
    cne_reference_case_flows: BaseCaseStrategy = BaseCaseStrategy.NODAL_OPTIMUM
    security_constraint_bodf_size_threshold: float = 0.2

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
    

    add_security_constraints: bool = False
    

    advanced_hybrid_coupling_flag: bool = True

    run_redispatch: bool = True
    security_constrained_redispatch: bool = False
    deviation_factor_redispatch: float = 0.9