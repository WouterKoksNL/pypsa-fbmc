"""
Defines FBMCWorkflowTestCase — a dataclass describing a full workflow test scenario —
and run_workflow_test, which executes the scenario and returns the objective value.
"""
from dataclasses import dataclass, field

from src.case_creation.main import Cases
from src.fbmc.config import FBMCConfig
from src.fbmc.parameters.base_case import BaseCaseStrategy
from src.fbmc.parameters.gsk import GSKStrategy
from src.fbmc.parameters.types import FBMCWorkflowResult


@dataclass
class FBMCWorkflowTestCase:
    """Fully describes a single FBMC workflow test scenario."""
    case_name: Cases
    gsk_strategy: GSKStrategy | None = None
    base_case_strategy: BaseCaseStrategy | None = None
    advanced_hybrid_coupling_flag: bool | None = None
    config: FBMCConfig = field(default_factory=FBMCConfig)
    case_kwargs: dict = field(default_factory=dict)
    expected_objective: float | None = None
    expected_rd_objective: float | None = None
    """If set, the test asserts the objective value matches within `tolerance`."""
    tolerance: float = 1e-2


def run_workflow_test(test_case: FBMCWorkflowTestCase) -> FBMCWorkflowResult:
    """
    Run the full FBMC (and optionally redispatch) workflow for the given test case.

    Returns the FBMCWorkflowResult so callers can do additional assertions.
    """
    from main import input_getter, fbmc_workflow, redispatch_workflow

    zonal_net, nodal_net, gsk = input_getter(
        case_name=test_case.case_name,
        **test_case.case_kwargs,
    )

    result = fbmc_workflow(
        zonal_net=zonal_net,
        nodal_net=nodal_net,
        gsk=gsk,
        gsk_strategy=test_case.gsk_strategy,
        base_case_strategy=test_case.base_case_strategy,
        advanced_hybrid_coupling_flag=test_case.advanced_hybrid_coupling_flag,
        config=test_case.config,
    )

    if test_case.config.run_redispatch:
        nodal_net, cost, result.dispatch_results = redispatch_workflow(
            nodal_net, result.dispatch_results
        )

    return result, cost
