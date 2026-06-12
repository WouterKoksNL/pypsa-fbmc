import pypsa
from pathlib import Path
import logging
from typing import Any
import pandas as pd

from fbmc.core.derived_parameters.bridge_branches import find_bridges_network

from fbmc.core.logging_setup import configure_run_logging
from fbmc.settings import FBMCConfig, merge_config_overrides


from example_networks.main import create_case, Cases
from example_networks.main import alter_case_workflow

from fbmc.enums import GSKStrategy, BaseCaseStrategy



from fbmc.post_processing.main import process_results
from fbmc.paths import get_case_results_dir

from fbmc.api import run_fbmc
from redispatch.main import run_redispatch




def input_getter(zonal_net: pypsa.Network = None, nodal_net: pypsa.Network = None, case_name: str | Cases = Cases.BASIC_THREE_NODE, load_case_flag: bool = False, save_case_flag: bool = False, **case_kwargs):
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
    logger = logging.getLogger(__name__)
    gsk = None
    if zonal_net is None and nodal_net is None:
        if case_name is None:
            raise ValueError("Either zonal_net and nodal_net or case_name must be provided.")
        case_data = create_case(case_name, load_case_flag=load_case_flag, save_case_flag=save_case_flag, **case_kwargs)
        logger.info(f"Loading case data for case: {case_name}")
        nodal_net: pypsa.Network = case_data['nodal_net']
        zonal_net: pypsa.Network = case_data['zonal_net']
        gsk: dict[pd.Timestamp, pd.DataFrame] | None = case_data.get('gsk_dict', None)
    # if only one is none, raise an error
    if nodal_net is not None and zonal_net is None:
        logger.info("Only nodal net provided, converting to zonal net.")
        from fbmc.input_network_conversions.network_conversion import nodal_to_zonal
        zonal_net = nodal_to_zonal(nodal_net, bus_zone_map=nodal_net.buses.zone_name)
    if zonal_net is not None and nodal_net is None:
        raise ValueError("Nodal net must be provided if zonal net is provided. ")
    
    case_data = {
        'zonal_net': zonal_net,
        'nodal_net': nodal_net,
        'gsk_dict': gsk
    }
    return case_data



def main(
        save_path: Path,
        zonal_net: pypsa.Network = None,
        nodal_net: pypsa.Network = None,
        load_case_flag: bool = False,
        save_case_flag: bool = False,
        case_kwargs: dict[str, Any] | None = None,
        case_name=Cases.BASIC_THREE_NODE,
        config: FBMCConfig | None = None,
        run_redispatch_flag: bool = True,
        config_overrides: dict[str, Any] | None = None,
        case_alteration_kwargs: dict[str, Any] | None = None,
        **config_kwargs: Any,
):
    run_log_path = configure_run_logging(save_path)
    logger = logging.getLogger(__name__)
    logger.info("Writing run logs to %s", run_log_path)

    case_kwargs = case_kwargs or {}
    merged_config_overrides = {
        **(config_overrides or {}),
        **config_kwargs,
    }
    config = merge_config_overrides(config, merged_config_overrides)

    case_data = input_getter(zonal_net, nodal_net, case_name, load_case_flag, save_case_flag, **case_kwargs)
    case_alteration_kwargs = case_alteration_kwargs or {}
    case_data = alter_case_workflow(case_data, case_alteration_kwargs)
    zonal_net = case_data['zonal_net']
    nodal_net = case_data['nodal_net']

    gsk = case_data.get('gsk_dict', None)
    # use_unit_commitment = case_alteration_kwargs.get("use_unit_commitment", False)
    # if use_unit_commitment:
    #     logger.info("Running initial UC solve before fixed-commitment LP rerun.")
    #     uc_result = fbmc_workflow(
    #         zonal_net=zonal_net,
    #         nodal_net=nodal_net,
    #         gsk=gsk,
    #         config=config,
    #     )
    #     _fix_commitment_schedule_and_disable_uc(uc_result.zonal_net, uc_result.dispatch_results)
    #     zonal_net_fixed_dispatch = uc_result.zonal_net.copy()

    #     logger.info("Running fixed-commitment LP solve with committable=False for final prices/results.")
    #     fbmc_result = fbmc_workflow(
    #         zonal_net=zonal_net_fixed_dispatch,
    #         nodal_net=nodal_net,
    #         gsk=gsk,
    #         config=config,
    #     )
    # else:
    fbmc_result = run_fbmc(
            zonal_net=zonal_net,
            nodal_net=nodal_net,
            gsk=gsk,
            config=config,
        )
    rd_cost = None
    rd_dispatch = fbmc_result.dispatch_results
    if run_redispatch_flag:
        find_bridges_network(nodal_net)
        # outaged_lines = nodal_net.lines.index.difference(bridges)
        redispatch_kwargs = {
            'security_constrained_flag': config.security_constrained_redispatch,
            # 'branch_outages': outaged_lines,
            'rt_deviation_factor': config.deviation_factor_redispatch,  # allow 20% deviation from base case flows in redispatch
        }

        nodal_net, rd_cost = run_redispatch(
            nodal_net,
            fbmc_result.dispatch_results,
            solver_kwargs=config.rd_solver_kwargs,
            create_model_kwargs=config.rd_create_model_kwargs,
            **redispatch_kwargs,
        )

    # do_lpf_contingency_check(nodal_net, rd_dispatch, fbmc_result.fbmc_parameters)

    process_results(
        fbmc_results=fbmc_result,
        rd_cost=rd_cost,
        rd_dispatch=rd_dispatch,
        save_path=save_path,
        config=config,
    )

    return fbmc_result.zonal_net.model.objective.value
    

if __name__ == "__main__":
    config_path = Path("config/base_config.yaml")
    config = FBMCConfig.from_base_yaml(config_path)
    save_path = Path(get_case_results_dir(Cases.PYPSA_EUR_UA.value)) # / f"n-0_RM_{str(config.reliability_margin_factor)}"
    obj3 = main(
        save_path=save_path,
        case_name=Cases.PYPSA_EUR_UA, 
        config=config,
        config_overrides={
            "gsk_strategy": GSKStrategy.P_NOM,
            "base_case_strategy": BaseCaseStrategy.ZERO_FLOWS,
            "advanced_hybrid_coupling_flag": False,
            "reliability_margin_factor": 0.3,
            "add_security_constraints": False,
            "security_constrained_redispatch": False,
        },
        load_case_flag=False,
        case_kwargs={
            # 'drop_countries': ["UA"]
        },
        case_alteration_kwargs={
            'snapshot_i_range': slice(0, 2),
            'use_unit_commitment': True,
            'unit_commitment_path': "data/unit_commitment_halve_su_sd.csv",
            'add_zonal_load_shedding': False,
            'load_shedding_cost': 100_000,
        }
    )  



