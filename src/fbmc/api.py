import pypsa
import pandas as pd
import importlib
from pathlib import Path
import logging
from typing import Any

from fbmc.core.parameters.bridge_branches import find_bridges_network
from fbmc.settings import FBMCConfig, coerce_enum_value, merge_config_overrides
from fbmc.core.main import setup_fbmc_model, solve
from fbmc.core.parameters.base_case import prepare_base_case, BaseCaseStrategy

from fbmc.case_creation.main import create_case, Cases
from fbmc.case_creation.main import alter_case_workflow
from fbmc.redispatch.main import run_redispatch

from fbmc.post_processing.lpf import do_lpf_contingency_check
from fbmc.types import DispatchResult, FBMCResult, RedispatchResult
from fbmc.core.parameters.gsk import calculate_gsk, GSKStrategy
from fbmc.core.input_checks import do_input_checks


from fbmc.post_processing.main import process_results
from fbmc.paths import get_case_results_dir


configure_run_logging = importlib.import_module("fbmc.core.logging_setup").configure_run_logging


def _extract_commitment_status(
        zonal_net: pypsa.Network,
        dispatch_results: DispatchResult,
    ) -> pd.DataFrame:
    """Return per-snapshot commitment status (True=on, False=off)."""
    snapshots = zonal_net.snapshots
    generators = zonal_net.generators.index
    if zonal_net.model is not None and hasattr(zonal_net.model, "solution") and "Generator-status" in zonal_net.model.solution:
        status_raw = zonal_net.model.solution["Generator-status"].to_pandas()
        if isinstance(status_raw, pd.Series):
            if isinstance(status_raw.index, pd.MultiIndex):
                status = status_raw.unstack()
            else:
                status = status_raw.to_frame().T
        else:
            status = status_raw
        status = status.reindex(index=snapshots, columns=generators, fill_value=0.0)
        return status > 0.5

    # Fallback if status variable is not available: infer on/off from dispatch.
    dispatch = dispatch_results.generators_p.reindex(index=snapshots, columns=generators, fill_value=0.0)
    return dispatch > 1e-6


def _fix_commitment_schedule_and_disable_uc(
        zonal_net: pypsa.Network,
        dispatch_results: DispatchResult,
    ) -> None:
    """Fix on/off schedule from UC run and disable UC binaries.

    For generators that are off, set p_max_pu = 0 and p_min_pu = 0.
    For generators that are on, keep p_max_pu and p_min_pu as in the UC parametrization.
    Ramp-rate parameters are left unchanged and therefore still active in the LP rerun.
    """
    snapshots = zonal_net.snapshots
    generators = zonal_net.generators.index
    status_on = _extract_commitment_status(zonal_net, dispatch_results)

    p_min_uc = zonal_net.get_switchable_as_dense("Generator", "p_min_pu").reindex(index=snapshots, columns=generators, fill_value=0.0)
    p_max_uc = zonal_net.get_switchable_as_dense("Generator", "p_max_pu").reindex(index=snapshots, columns=generators, fill_value=1.0)

    zonal_net.generators_t.p_min_pu = p_min_uc.where(status_on, 0.0)
    zonal_net.generators_t.p_max_pu = p_max_uc.where(status_on, 0.0)
    zonal_net.generators.loc[:, "committable"] = False



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
        from fbmc.case_creation.network_conversion import nodal_to_zonal
        zonal_net = nodal_to_zonal(nodal_net, bus_zone_map=nodal_net.buses.zone_name)
    if zonal_net is not None and nodal_net is None:
        raise ValueError("Nodal net must be provided if zonal net is provided. ")
    
    case_data = {
        'zonal_net': zonal_net,
        'nodal_net': nodal_net,
        'gsk_dict': gsk
    }
    return case_data


def redispatch_workflow(
        nodal_net: pypsa.Network,
        dispatch_results: DispatchResult,
        rd_solver_kwargs: dict[str, str] = None,
        rd_create_model_kwargs: dict[str, Any] = None,
        **redispatch_kwargs: dict,
    ) -> tuple[pypsa.Network, float, DispatchResult]:

    nodal_net, cost = run_redispatch(
        nodal_net, 
        dispatch_results=dispatch_results, 
        create_model_kwargs=rd_create_model_kwargs,
        solver_kwargs=rd_solver_kwargs,
        **redispatch_kwargs
    )

    dispatch_results = DispatchResult(nodal_net)  # override dispatch results
    return RedispatchResult(
        nodal_net=nodal_net,
        cost=cost,
        dispatch_results=dispatch_results,
    )


def run_fbmc(
        zonal_net: pypsa.Network = None,
        nodal_net: pypsa.Network = None,
        gsk: dict = None,
        config: FBMCConfig | None = None,

    ) -> FBMCResult:
    
    logger = logging.getLogger(__name__)
    do_input_checks(nodal_net, zonal_net, gsk)

    logger.info(f"Preparing base case with strategy {config.base_case_strategy}")
    base_case = prepare_base_case(
        nodal_net, 
        strategy=config.base_case_strategy,
        base_case_kwargs={'marginal_cost_load_shedding': config.marginal_cost_load_shedding}
        )
    logger.info("Base case prepared.")

    if gsk is None:
        gsk_strategy = coerce_enum_value(config.gsk_strategy, GSKStrategy, "gsk_strategy")
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
    zonal_net, net_positions = solve(zonal_net, advanced_hybrid_flag=config.advanced_hybrid_coupling_flag, solver_kwargs=config.fbmc_solver_kwargs)
    dispatch_results = DispatchResults(zonal_net)

    return FBMCResult(
        zonal_net=zonal_net,
        net_positions=net_positions,
        dispatch_results=DispatchResult(zonal_net),
        fbmc_parameters=fbmc_parameters,
        base_case=base_case,
    )


def main(
        save_path: Path,
        zonal_net: pypsa.Network = None,
        nodal_net: pypsa.Network = None,
        load_case_flag: bool = False,
        save_case_flag: bool = False,
        case_kwargs: dict[str, Any] | None = None,
        case_name=Cases.BASIC_THREE_NODE,
        config: FBMCConfig | None = None,
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
    if config.run_redispatch:
        find_bridges_network(nodal_net)
        # outaged_lines = nodal_net.lines.index.difference(bridges)
        redispatch_kwargs = {
            'security_constrained_flag': config.security_constrained_redispatch,
            # 'branch_outages': outaged_lines,
            'rt_deviation_factor': config.deviation_factor_redispatch,  # allow 20% deviation from base case flows in redispatch
        }

        nodal_net, rd_cost, rd_dispatch = redispatch_workflow(
            nodal_net,
            fbmc_result.dispatch_results,
            rd_solver_kwargs=config.rd_solver_kwargs,
            rd_create_model_kwargs=config.rd_create_model_kwargs,
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



