"""
Workflow-level tests: each test defines a FBMCWorkflowTestCase, runs the workflow,
and asserts the objective value matches the known expected value.

To add a new test:
1. Define a FBMCWorkflowTestCase with the desired parameters and expected_objective.
2. Add a test method that calls _assert_objective(test_case).
"""
import unittest

from src.case_creation.main import Cases
from src.fbmc.config import FBMCConfig
from src.fbmc.parameters.base_case import BaseCaseStrategy
from src.fbmc.parameters.gsk import GSKStrategy

from tests.workflow_test_case import FBMCWorkflowTestCase, run_workflow_test


def _make_config(**kwargs) -> FBMCConfig:
    config = FBMCConfig()
    for key, value in kwargs.items():
        setattr(config, key, value)
    return config


class TestFBMCWorkflow(unittest.TestCase):

    def _assert_objective(self, test_case: FBMCWorkflowTestCase):
        result, rd_objective = run_workflow_test(test_case)
        objective = result.zonal_net.model.objective.value
        if test_case.expected_objective is not None:
            self.assertAlmostEqual(
                objective,
                test_case.expected_objective,
                delta=test_case.tolerance,
                msg=(
                    f"Objective mismatch for {test_case.case_name.value}: "
                    f"got {objective:.4f}, expected {test_case.expected_objective:.4f}"
                ),
            )
        if test_case.config.run_redispatch and test_case.expected_rd_objective is not None:
            self.assertAlmostEqual(
                rd_objective,
                test_case.expected_rd_objective,
                delta=test_case.tolerance,
                msg=(
                    f"Redispatch objective mismatch for {test_case.case_name.value}: "
                    f"got {rd_objective:.4f}, expected {test_case.expected_rd_objective:.4f}"
                ),
            )
        return objective

    # ------------------------------------------------------------------
    # Example test cases — fill in expected_objective after a first run
    # ------------------------------------------------------------------

    def test_linear(self):
        test_case = FBMCWorkflowTestCase(
            case_name=Cases.LINEAR,
            gsk_strategy=GSKStrategy.P_NOM,
            base_case_strategy=BaseCaseStrategy.ZERO_FLOWS,
            advanced_hybrid_coupling_flag=False,
            expected_objective=20.0,  
            expected_rd_objective=88.,  
        )
        self._assert_objective(test_case)
    # def test_basic_three_node_p_nom_gsk(self):
    #     test_case = FBMCWorkflowTestCase(
    #         case_name=Cases.BASIC_THREE_NODE,
    #         gsk_strategy=GSKStrategy.P_NOM,
    #         base_case_strategy=BaseCaseStrategy.SECURITY_CONSTRAINED_NODAL_OPTIMUM,
    #         expected_objective=None,  # TODO: fill in after first passing run
    #     )
    #     self._assert_objective(test_case)

    # def test_double_three_node_link_and_line_advanced_hybrid(self):
    #     test_case = FBMCWorkflowTestCase(
    #         case_name=Cases.DOUBLE_THREE_NODE_LINK_AND_LINE,
    #         gsk_strategy=GSKStrategy.P_NOM,
    #         base_case_strategy=BaseCaseStrategy.SECURITY_CONSTRAINED_NODAL_OPTIMUM,
    #         advanced_hybrid_coupling_flag=True,
    #         expected_objective=None,  # TODO: fill in after first passing run
    #     )
    #     self._assert_objective(test_case)


if __name__ == "__main__":
    unittest.main()
