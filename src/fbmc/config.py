"""FBMC configuration parameters."""

from dataclasses import dataclass
import enum

class GSKMethod(enum.Enum):
    """Tracks implemented GSK methods."""
    ADJUSTABLE_CAP: str = "ADJUSTABLE_CAP"
    CURRENT_GENERATION: str = "CURRENT_GENERATION"
    ITERATIVE_UNCERTAINTY: str = "ITERATIVE_UNCERTAINTY"
    ITERATIVE_FBMC: str = "ITERATIVE_FBMC"
    MERIT_ORDER: str = "MERIT_ORDER"
    BUS_P: str = "BUS_P"

@dataclass
class FBMCConfig:
    """Configuration parameters for FBMC calculations."""
    reliability_margin_factor: float = 0.1
    min_ram: float = 0.0

    cne_setting: str = "all"
    line_usage_threshold: float = 0.2
    cne_list: list[str] = None

    # GSK Method options:
    # "ADJUSTABLE_CAP" - Share of Adjustable Capacity
    # "CURRENT_GENERATION" - Current Generation
    # "ITERATIVE_UNCERTAINTY" - Iterative Uncertainty
    # "ITERATIVE_FBMC" - Iterative FBMC
    
    # use the GSKMethod class 
    gsk_method: str = GSKMethod.CURRENT_GENERATION
    gsk_kwargs = {
        GSKMethod.ADJUSTABLE_CAP: {
            "adjustable_carriers": ("CCGT", 'coal', 'lignite', 'OCGT', 'oil'),
        },
        GSKMethod.ITERATIVE_UNCERTAINTY: {
            "uncertain_carriers": ("offshore-wind", "onshore-wind"),
            "num_scenarios": 100,
            "gen_variation_std_dev": 0.5,
            "load_variation_std_dev": 0.5,
        },
        GSKMethod.ITERATIVE_FBMC: {
            "uncertain_carriers": ("offshore-wind", "onshore-wind"),
            "num_scenarios": 100,
            "max_gsk_iterations": 5,
            "initial_gsk_method": GSKMethod.BUS_P,
            "gen_variation_std_dev": 0.5,
            "load_variation_std_dev": 0.5,
        },
        GSKMethod.MERIT_ORDER: {
            "standard_deviation": 5,
        },
        GSKMethod.BUS_P: {},
    }
    
    use_zero_base_flows_flag: bool = False

    

    add_security_constraints: bool = True

    advanced_hybrid_coupling: bool = False

    run_redispatch: bool = False

