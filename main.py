import pypsa
import numpy as np
import pandas as pd
from logging import Logger 

from src.fbmc.parameters.bridge_branches import find_bridges_network
from src.configs.config import FBMCConfig, coerce_enum_value, merge_config_overrides
from src.fbmc.main import setup_fbmc_model, solve
from src.fbmc.parameters.base_case import prepare_base_case, BaseCaseStrategy
from src.post_processing.market_prices import calculate_zonal_prices

from src.case_creation.main import create_case, Cases

from src.redispatch.main import run_redispatch

from src.post_processing.lpf import do_lpf_contingency_check
from src.types import DispatchResults, FBMCWorkflowResult
from src.fbmc.parameters.gsk import calculate_gsk, GSKStrategy
from src.fbmc.input_checks import do_input_checks


def input_getter(zonal_net: pypsa.Network = None, nodal_net: pypsa.Network = None, case_name: Cases = Cases.BASIC_THREE_NODE, load_case_flag: bool = False, save_case_flag: bool = False, **case_kwargs):
    """_summary_

    Args:
        zonal_net (pypsa.Network, optional): _description_. Defaults to None.
        nodal_net (pypsa.Network, optional): _description_. Defaults to None.
        case_name (Cases, optional): _description_. Defaults to Cases.BASIC_THREE_NODE.
        load_case_flag (bool, optional): _description_. Defaults to False.
        save_case_flag (bool, optional): _description_. Defaults to False.

    Raises:
        ValueError: _description_

    Returns:
        pypsa.Network: Zonal net 
        pypsa.Network: Nodal net
        dict: GSK dict (if exists, else None)
    """
    logger = Logger(__name__)
    if zonal_net is None and nodal_net is None:
        case_data = create_case(case_name, load_case_flag=load_case_flag, save_case_flag=save_case_flag, **case_kwargs)
        logger.info(f"Running case: {case_name}")
        nodal_net: pypsa.Network = case_data['nodal_net']
        zonal_net: pypsa.Network = case_data['zonal_net']
        gsk: dict[pd.Timestamp, pd.DataFrame] | None = case_data.get('gsk_dict', None)
    # if only one is none, raise an error
    if nodal_net is not None and zonal_net is None:
        from src.case_creation.network_conversion import nodal_to_zonal
        zonal_net = nodal_to_zonal(nodal_net, bus_zone_map=nodal_net.buses.zone_name)
    if zonal_net is not None and nodal_net is None:
        raise ValueError("Nodal net must be provided if zonal net is provided. ")
    return zonal_net, nodal_net, gsk


def redispatch_workflow(nodal_net: pypsa.Network, dispatch_results: DispatchResults, **redispatch_kwargs: dict) -> tuple[pypsa.Network, float, DispatchResults]:

    nodal_net, cost = run_redispatch(
        nodal_net, 
        dispatch_results=dispatch_results, 
        **redispatch_kwargs
    )

    dispatch_results = DispatchResults(nodal_net)  # override dispatch results
    return nodal_net, cost, dispatch_results


def fbmc_workflow(
        zonal_net: pypsa.Network = None,
        nodal_net: pypsa.Network = None,
        gsk: dict = None,
        config: FBMCConfig | None = None,
        config_overrides: dict[str, Any] | None = None,
    ) -> FBMCWorkflowResult:
    
    logger = Logger(__name__)
    
    config = merge_config_overrides(config, config_overrides)

    if base_case_strategy is not None:
        config.base_case_strategy = base_case_strategy
    if advanced_hybrid_coupling_flag is not None:
        config.advanced_hybrid_coupling_flag = advanced_hybrid_coupling_flag

    logger.info(f"Preparing base case with strategy {config.base_case_strategy}")
    base_case = prepare_base_case(
        nodal_net, 
        strategy=config.base_case_strategy,
        base_case_kwargs={'marginal_cost_load_shedding': config.marginal_cost_load_shedding}
        )
    logger.info("Base case prepared.")

    if gsk is None:
        gsk_strategy = coerce_enum_value(config.gsk_method, GSKStrategy, "gsk_method")
        gsk = calculate_gsk(base_case, gsk_strategy, config)

    if nodal_net.sub_networks.empty:
        nodal_net.determine_network_topology()

    logger.info("Calculating FBMC parameters and setting up FBMC model.")
    model, fbmc_parameters = setup_fbmc_model(
        zonal_net, 
        basecase_nodal_network=base_case, 
        gsk=gsk,
        config=config
    )

    logger.info("Solving FBMC model.")
    zonal_net, net_positions = solve(zonal_net, advanced_hybrid_flag=config.advanced_hybrid_coupling_flag)
    dispatch_results = DispatchResults(zonal_net)
    return FBMCWorkflowResult(
        zonal_net=zonal_net,
        net_positions=net_positions,
        dispatch_results=dispatch_results,
        fbmc_parameters=fbmc_parameters,
        base_case=base_case,
    )


def main(
        zonal_net: pypsa.Network = None,
        nodal_net: pypsa.Network = None,
        load_case_flag: bool = False,
        save_case_flag: bool = False,
        case_kwargs: dict[str, Any] | None = None,
        case_name=Cases.BASIC_THREE_NODE,
        config: FBMCConfig | None = None,
        config_overrides: dict[str, Any] | None = None,
        **config_kwargs: Any,
):
    case_kwargs = case_kwargs or {}
    merged_config_overrides = {
        **(config_overrides or {}),
        **config_kwargs,
    }
    config = merge_config_overrides(config, merged_config_overrides)

    zonal_net, nodal_net, gsk = input_getter(zonal_net, nodal_net, case_name, load_case_flag, save_case_flag, **case_kwargs)
    zonal_net.remove("Link", zonal_net.links.index)  # remove links if they exist, as they will be re-created in the FBMC model setup based on the base case flows
    nodal_net.remove("Link", nodal_net.links.index)  # remove links if they exist, as they will be re-created in the FBMC model setup based on the base case flows
    result = fbmc_workflow(
            zonal_net=zonal_net,
            nodal_net=nodal_net,
            gsk=gsk,
            gsk_strategy=gsk_strategy,
            base_case_strategy=base_case_strategy,
            advanced_hybrid_coupling_flag=advanced_hybrid_coupling_flag,
            config=config
            config=config,
        )
    if config.run_redispatch:
        bridges = find_bridges_network(nodal_net)
        # outaged_lines = nodal_net.lines.index.difference(bridges)
        redispatch_kwargs = {
            'with_security_constraints': config.security_constrained_redispatch,
            # 'branch_outages': outaged_lines,
            'rt_deviation_factor': config.deviation_factor_redispatch,  # allow 20% deviation from base case flows in redispatch
        }

        nodal_net, cost, result.dispatch_results = redispatch_workflow(nodal_net, result.dispatch_results, **redispatch_kwargs)
  
    do_lpf_contingency_check(nodal_net, result.dispatch_results, result.fbmc_parameters)
    
    return result.zonal_net.model.objective.value
    

if __name__ == "__main__":
    rm_list = [0.0, 0.1, 0.2, 0.3]
    for r in rm_list:
        obj3 = main(
            case_name=Cases.PYPSA_EUR_UA, 
            config_overrides={
                "gsk_method": GSKStrategy.P_NOM,
                "base_case_strategy": BaseCaseStrategy.ZERO_FLOWS,
                "advanced_hybrid_coupling_flag": False,
                "reliability_margin_factor": r,
                "add_security_constraints": False,
                "security_constrained_redispatch": False,
            },
            load_case_flag=False,
            case_kwargs={
                'snapshot_i_range': slice(0, 24),
                # 'drop_countries': ["UA"]
            },
        )  



