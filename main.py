import pypsa
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging
from typing import Any

from src.fbmc.parameters.bridge_branches import find_bridges_network
from src.config import FBMCConfig, coerce_enum_value, merge_config_overrides
from src.fbmc.main import setup_fbmc_model, solve
from src.fbmc.parameters.base_case import prepare_base_case, BaseCaseStrategy

from src.case_creation.main import create_case, Cases
from src.case_creation.main import alter_case_workflow
from src.redispatch.main import run_redispatch

from src.post_processing.lpf import do_lpf_contingency_check
from src.types import DispatchResults, FBMCWorkflowResult
from src.fbmc.parameters.gsk import calculate_gsk, GSKStrategy
from src.fbmc.input_checks import do_input_checks


from src.post_processing.main import process_results
from src.paths import get_case_results_dir


RUN_FILE_HANDLER_NAME = "pypsa_fbmc_run_file"


def _configure_run_logging(save_path: Path) -> Path:
    """Attach a per-run file handler while keeping console logging enabled."""
    save_path = Path(save_path)
    save_path.mkdir(parents=True, exist_ok=True)

    log_path = save_path / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    has_stream_handler = any(
        isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
        for handler in root_logger.handlers
    )
    if not has_stream_handler:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    for handler in list(root_logger.handlers):
        if isinstance(handler, logging.FileHandler) and handler.get_name() == RUN_FILE_HANDLER_NAME:
            root_logger.removeHandler(handler)
            handler.close()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.set_name(RUN_FILE_HANDLER_NAME)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    return log_path




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
        from src.case_creation.network_conversion import nodal_to_zonal
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
        dispatch_results: DispatchResults,
        rd_solver_kwargs: dict[str, str] = None,
        rd_create_model_kwargs: dict[str, Any] = None,
        **redispatch_kwargs: dict,
    ) -> tuple[pypsa.Network, float, DispatchResults]:

    nodal_net, cost = run_redispatch(
        nodal_net, 
        dispatch_results=dispatch_results, 
        create_model_kwargs=rd_create_model_kwargs,
        solver_kwargs=rd_solver_kwargs,
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
    
    logger = logging.getLogger(__name__)
    
    config = merge_config_overrides(config, config_overrides)

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
    return FBMCWorkflowResult(
        zonal_net=zonal_net,
        net_positions=net_positions,
        dispatch_results=dispatch_results,
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
    run_log_path = _configure_run_logging(save_path)
    logging.getLogger(__name__).info("Writing run logs to %s", run_log_path)

    case_kwargs = case_kwargs or {}
    merged_config_overrides = {
        **(config_overrides or {}),
        **config_kwargs,
    }
    config = merge_config_overrides(config, merged_config_overrides)

    case_data = input_getter(zonal_net, nodal_net, case_name, load_case_flag, save_case_flag, **case_kwargs)
    case_data = alter_case_workflow(case_data, case_alteration_kwargs or {})
    zonal_net = case_data['zonal_net']
    nodal_net = case_data['nodal_net']
    gsk = case_data.get('gsk_dict', None)
    fbmc_result = fbmc_workflow(
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
        }
    )  



