"""
Workflow-level tests: each test defines a FBMCWorkflowTestCase, runs the workflow,
and asserts the objective value matches the known expected value.

To add a new test:
1. Define a FBMCWorkflowTestCase with the desired parameters and expected_objective.
2. Add a test method that calls _assert_objective(test_case).
"""
import unittest
from copy import deepcopy

from src.case_creation.main import Cases
from src.configs.config import FBMCConfig
from src.enums import BaseCaseStrategy

from tests.workflow_test_case import FBMCWorkflowTestCase, run_workflow_test


# Keep test defaults explicit so tests do not implicitly depend on FBMCConfig internals.
EXPLICIT_TEST_CONFIG_DEFAULTS = {
    "reliability_margin_factor": 0.0,
    "min_ram": 0.0,
    "cne_setting": "utilization_threshold",
    "line_usage_threshold": 0.2,
    "cne_list": None,
    "cne_reference_case_flows": BaseCaseStrategy.NODAL_OPTIMUM,
    "security_constraint_bodf_size_threshold": 0.2,
    "security_constraint_bodf_columnwise_matrix_size_limit": 5_000_000,
    "gsk_method": "CURRENT_GENERATION",
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
            "initial_gsk_method": "BUS_P",
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
    "add_security_constraints": False,
    "advanced_hybrid_coupling_flag": True,
    "run_redispatch": True,
    "security_constrained_redispatch": False,
    "deviation_factor_redispatch": 0.9,
}


def _make_config(**kwargs) -> FBMCConfig:
    explicit_values = deepcopy(EXPLICIT_TEST_CONFIG_DEFAULTS)
    explicit_values.update(kwargs)
    return FBMCConfig(**explicit_values)


class TestFBMCWorkflow(unittest.TestCase):

    def _assert_objective(self, test_case: FBMCWorkflowTestCase):

        result, rd_objective = run_workflow_test(
            test_case=test_case
        )
        objective = result.zonal_net.model.objective.value
        if test_case.expected_objective is not None:
            self.assertAlmostEqual(
                objective,
                test_case.expected_objective,
                delta=test_case.tolerance,
                msg=(
                    f"Objective mismatch for {test_case.case_name}: "
                    f"got {objective:.4f}, expected {test_case.expected_objective:.4f}"
                ),
            )
        if test_case.config.run_redispatch and test_case.expected_rd_objective is not None:
            self.assertAlmostEqual(
                rd_objective,
                test_case.expected_rd_objective,
                delta=test_case.tolerance,
                msg=(
                    f"Redispatch objective mismatch for {test_case.case_name}: "
                    f"got {rd_objective:.4f}, expected {test_case.expected_rd_objective:.4f}"
                ),
            )
        return objective

    # ------------------------------------------------------------------
    # Example test cases — fill in expected_objective after a first run
    # ------------------------------------------------------------------

    # def test_linear(self):
    #     from main import input_getter 
    #     zonal_net, nodal_net, gsk = input_getter(
    #         case_name=Cases.LINEAR,
    #     )

        # test_case = FBMCWorkflowTestCase(
        #     case_name=Cases.LINEAR,
        #     zonal_net=zonal_net,
        #     nodal_net=nodal_net,
        #     gsk=gsk,
        #     gsk_strategy=GSKStrategy.P_NOM,
        #     base_case_strategy=BaseCaseStrategy.ZERO_FLOWS,
        #     advanced_hybrid_coupling_flag=False,
        #     expected_objective=4800,  
        #     expected_rd_objective=100.,  
        # )
        # self._assert_objective(test_case)

    def test_three_node_redispatch(self):
        from main import input_getter
        zonal_net, nodal_net, gsk_dict = input_getter(
            case_name=Cases.THREE_NODE_REDISPATCH,
        )
        test_case = FBMCWorkflowTestCase(
            case_name=Cases.THREE_NODE_REDISPATCH,
            gsk=gsk_dict,
            zonal_net=zonal_net,
            nodal_net=nodal_net,
            base_case_strategy=BaseCaseStrategy.ZERO_FLOWS,
            advanced_hybrid_coupling_flag=False,
            config=_make_config(run_redispatch=True),
            expected_objective=3600,  
            expected_rd_objective=6300,  
        )
        self._assert_objective(test_case)

    def test_three_node_redispatch_with_storage(self):
        from main import input_getter
        zonal_net, nodal_net, gsk_dict = input_getter(
            case_name=Cases.THREE_NODE_REDISPATCH,
        )
        nodal_net.add("StorageUnit", "Storage", bus="A1", p_nom=1, max_hours=2)
        nodal_net.loads_t.p_set.loc['1', 'load_A1'] *= 0.5
        zonal_net.add("StorageUnit", "Storage", bus="A", p_nom=1, max_hours=2)  
        zonal_net.loads_t.p_set.loc['1', 'load_A1'] *= 0.5
        test_case = FBMCWorkflowTestCase(
            case_name='Three Node Redispatch with Storage',
            gsk=gsk_dict,
            zonal_net=zonal_net,
            nodal_net=nodal_net,
            base_case_strategy=BaseCaseStrategy.ZERO_FLOWS,
            advanced_hybrid_coupling_flag=False,
            config=_make_config(run_redispatch=True),
            expected_objective=2700,  
            expected_rd_objective=3750.0,  
        )
        self._assert_objective(test_case)

    def test_three_node_redispatch_with_storage_redispatching(self):
        """A case in which storage is being used in DA but gets adapted in redispatch. 
        Dispatch results zonal clearing:

        Generator  gen_B1  gen_B2
        snapshot                 
        1            14.0     0.0
        2             8.5     0.0
        3            18.0     0.0

        StorageUnit  Storage
        snapshot            
        1               -5.0
        2                5.0
        3                0.0

        Redispatch results: (no load shedding)
        Generator  gen_B1  gen_B2  
        snapshot                                                                       
        1            13.5     0.0    
        2             8.5     5.0    
        3            13.5     0.0  
        StorageUnit  Storage
        snapshot            
        1               -4.5
        2                0.0
        3                4.5
        
        13.5 is the maximum flow from zone B to A in case of a flow from a single node (B1). 
        """
        from main import input_getter
        zonal_net, nodal_net, gsk_dict = input_getter(
            case_name=Cases.THREE_NODE_REDISPATCH,
        )
        
        nodal_net.set_snapshots(['1', '2', '3'])
        zonal_net.set_snapshots(['1', '2', '3'])
        gsk_dict = {snapshot: gsk_dict['1'].copy() for snapshot in zonal_net.snapshots}
        nodal_net.add("StorageUnit", "Storage", bus="A1", p_nom=5, max_hours=2)
        nodal_net.loads_t.p_set.loc[:, 'load_A1'] = [9, 13.5, 18]
        nodal_net.remove('Generator', 'gen_A1')
        zonal_net.add("StorageUnit", "Storage", bus="A", p_nom=5, max_hours=2)  
        zonal_net.loads_t.p_set.loc[:, 'load_A1'] = [9, 13.5, 18]
        zonal_net.remove('Generator', 'gen_A1')
        config = _make_config(run_redispatch=True)
        config.deviation_factor_redispatch = 0.9
        config.security_constrained_redispatch = False
        test_case = FBMCWorkflowTestCase(
            case_name='Three Node Redispatch with Storage Duration',
            gsk=gsk_dict,
            zonal_net=zonal_net,
            nodal_net=nodal_net,
            base_case_strategy=BaseCaseStrategy.ZERO_FLOWS,
            advanced_hybrid_coupling_flag=False,
            config=config,
            expected_objective=4050,  
            expected_rd_objective=4050,  
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
