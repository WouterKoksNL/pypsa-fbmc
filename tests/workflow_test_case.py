"""
Defines FBMCWorkflowTestCase — a dataclass describing a full workflow test scenario —
and run_workflow_test, which executes the scenario and returns the objective value.
"""
from dataclasses import dataclass, field
import pypsa 


from fbmc.settings import FBMCConfig
from fbmc.core.input_parameters.base_case import BaseCaseStrategy
from fbmc.core.input_parameters.gsk import GSKStrategy
from fbmc.types import FBMCResult
from src.redispatch.main import run_redispatch


@dataclass
class FBMCWorkflowTestCase:
    """Fully describes a single FBMC workflow test scenario."""
    case_name: str
    zonal_net: None | pypsa.Network = None
    nodal_net: None | pypsa.Network = None
    gsk: None | dict = None
    gsk_strategy: GSKStrategy | None = None
    base_case_strategy: BaseCaseStrategy | None = None
    advanced_hybrid_coupling_flag: bool | None = None
    config: FBMCConfig = field(default_factory=FBMCConfig)
    case_kwargs: dict = field(default_factory=dict)
    expected_objective: float | None = None
    expected_rd_objective: float | None = None
    """If set, the test asserts the objective value matches within `tolerance`."""
    tolerance: float = 1e-2


def run_workflow_test(
        test_case: FBMCWorkflowTestCase,
) -> tuple[FBMCResult, float]:
    """
    Run the full FBMC (and optionally redispatch) workflow for the given test case.

    Returns the FBMCResult so callers can do additional assertions.
    """
    from fbmc.api import run_fbmc

    config = test_case.config
    config.gsk_strategy = test_case.gsk_strategy 
    config.base_case_strategy = test_case.base_case_strategy
    config.advanced_hybrid_coupling_flag = test_case.advanced_hybrid_coupling_flag
    result = run_fbmc(
        zonal_net=test_case.zonal_net,
        nodal_net=test_case.nodal_net,
        gsk=test_case.gsk,
        config=test_case.config,
    )
    redispatch_kwargs = {
        'security_constrained_flag': test_case.config.security_constrained_redispatch, 
        'rt_deviation_factor': test_case.config.deviation_factor_redispatch,
    }
    if test_case.config.run_redispatch:
        nodal_net, rd_cost = run_redispatch(
            test_case.nodal_net, result.dispatch_results, **redispatch_kwargs   
        )
        breakpoint()
    return result, rd_cost if test_case.config.run_redispatch else None
