from enum import Enum


class BaseCaseStrategy(Enum):
    ZERO_FLOWS = "zero_flows"
    NODAL_OPTIMUM = "nodal_optimum"
    SECURITY_CONSTRAINED_NODAL_OPTIMUM = "security_constrained"
    CUSTOM = "custom"


class GSKStrategy(Enum):
    ADJUSTABLE_CAP: str = "ADJUSTABLE_CAP"
    CURRENT_GENERATION: str = "CURRENT_GENERATION"
    ITERATIVE_UNCERTAINTY: str = "ITERATIVE_UNCERTAINTY"
    ITERATIVE_FBMC: str = "ITERATIVE_FBMC"
    MERIT_ORDER: str = "MERIT_ORDER"
    BUS_P: str = "BUS_P"
    P_NOM: str = "P_NOM"