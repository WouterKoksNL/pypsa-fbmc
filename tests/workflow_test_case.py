"""
Defines FBMCWorkflowTestCase — a dataclass describing a full workflow test scenario —
and run_workflow_test, which executes the scenario and returns the objective value.
"""
from dataclasses import dataclass, field
from PyPSA import pypsa 

from src.case_creation.main import Cases
from src.configs.config import FBMCConfig
from src.fbmc.parameters.base_case import BaseCaseStrategy
from src.fbmc.parameters.gsk import GSKStrategy
from src.types import FBMCWorkflowResult


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
) -> tuple[FBMCWorkflowResult, float]:
    """
    Run the full FBMC (and optionally redispatch) workflow for the given test case.

    Returns the FBMCWorkflowResult so callers can do additional assertions.
    """
    from main import fbmc_workflow, redispatch_workflow


    result = fbmc_workflow(
        zonal_net=test_case.zonal_net,
        nodal_net=test_case.nodal_net,
        gsk=test_case.gsk,
        gsk_strategy=test_case.gsk_strategy,
        base_case_strategy=test_case.base_case_strategy,
        advanced_hybrid_coupling_flag=test_case.advanced_hybrid_coupling_flag,
        config=test_case.config,
    )
    redispatch_kwargs = {
        'with_security_constraints': test_case.config.security_constrained_redispatch, 
        'rt_deviation_factor': test_case.config.deviation_factor_redispatch,
    }
    if test_case.config.run_redispatch:
        nodal_net, cost, result.dispatch_results = redispatch_workflow(
            test_case.nodal_net, result.dispatch_results, **redispatch_kwargs   
        )
        breakpoint()
    return result, cost
