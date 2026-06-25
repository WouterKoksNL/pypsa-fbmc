import pypsa
import pandas as pd
import importlib
from pathlib import Path
import logging
from collections.abc import Sequence
from typing import Any

from fbmc.core.derived_parameters.bridge_branches import find_bridges_network

from fbmc.core.results_extraction import extract_model_results
from fbmc.settings import FBMCConfig
from fbmc.core.main import setup_fbmc_model
from fbmc.core.input_parameters.main import calc_input_parameters

from fbmc.post_processing.lpf import do_lpf_contingency_check
from fbmc.types import DispatchResult, FBMCResult
from fbmc.core.input_checks import do_input_checks





configure_run_logging = importlib.import_module("fbmc.core.logging_setup").configure_run_logging


def run_fbmc(
        zonal_net: pypsa.Network,
        nodal_net: pypsa.Network,
        config: FBMCConfig,
        gsk: dict = None,
        cnecs: Sequence[Sequence] | None = None,
    ) -> FBMCResult:
    """Run the flow-based market clearing algorithm. Steps:
        Prepare base-case, depending on base case strategy
        If gsk is None, calculate gsk according to strategy
        Set up and solve FBMC model

    Args:
        zonal_net (pypsa.Network): Zonal network to which FBMC model will be added.
        nodal_net (pypsa.Network): Nodal network to be used as reference for FBMC model creation.
        config (FBMCConfig): Configuration object. 
        gsk (dict, optional): Dictionary of GSK matrices for each snapshot. 
            The values need to be pd.DataFrames with index Zone and column Bus.
            Defaults to None.
        cnecs (Sequence[Sequence] | None, optional): Custom CNECs input, required when
            config.cnec_setting == CNECStrategy.CUSTOM. See
            fbmc.core.input_parameters.cnec.cnec_subnet_router() for the expected format.
            Defaults to None.

    Returns:
        FBMCResult: FBMCResult object containing
            Solved zonal net
            Net positions
            Dispatch results (generator dispatch, storage dispatch, link flows, storage levels, water values)
            FBMC parameters (zPTDFs, etc.)
            Base case nodal network
    """
    logger = logging.getLogger(__name__)
    do_input_checks(nodal_net, zonal_net, gsk, config, cnecs_input=cnecs)


    if nodal_net.sub_networks.empty:
        nodal_net.determine_network_topology()

    input_parameters = calc_input_parameters(
        nodal_net,
        gsk,
        config,
        cnecs_input=cnecs,
    )

    logger.info("Calculating FBMC parameters and setting up FBMC model.")
    model, fbmc_parameters = setup_fbmc_model(
        zonal_net, 
        input_parameters,
        config=config
    )

    logger.info("Solving FBMC model.")
    solver_kwargs = config.solver_kwargs or {}

    # Run the optimization and save the results to the nodal network
    zonal_net.model.solve(**solver_kwargs)
    if zonal_net.model.termination_condition != 'optimal':
        raise ValueError("FBMC optimization did not solve to optimality.")
    extract_model_results(zonal_net)


    return FBMCResult(
        zonal_net=zonal_net,
        net_positions=zonal_net.model.solution["Zone-p"],
        dispatch_results=DispatchResult(zonal_net),
        fbmc_parameters=fbmc_parameters,
        base_case=input_parameters.base_case,
    )

