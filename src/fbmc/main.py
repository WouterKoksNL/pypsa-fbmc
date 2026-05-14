# -*- coding: utf-8 -*-
"""
Created on Mon Mar 17 13:01:07 2025

@author: ameldekok
"""

import pypsa
import pandas as pd
import logging
import linopy as lp 

from .parameters.main import calculate_fbmc_parameters_subnet
from .parameters.types import SubnetFBMCParameters
from .parameters.cnec import define_cne_reference_case_flows
from .constraints.main import create_zonal_generation
from .constraints.main import add_fbmc_constraints, remove_original_constraints, remove_original_constraints_by_bus
from .config import FBMCConfig
from .results_extraction import extract_model_results, get_net_positions
from .parameters.base_case import calc_base_net_positions, get_base_flows
logging.basicConfig(level=logging.INFO)


def calculate_fbmc_parameters(
        basecase_nodal_network: pypsa.Network, 
        gsk: pd.DataFrame | dict[pd.Timestamp, pd.DataFrame], 
        config: FBMCConfig = FBMCConfig(), 
    ) -> dict[str, SubnetFBMCParameters]:
    """
    Set up the FBMC model by calculating parameters and adding constraints.
    
    Parameters
    ----------
    basecase_nodal_network : pypsa.Network
        The base case nodal network to be used for FBMC.
    zonal_net : pypsa.Network
        The target zonal network to be used for FBMC.
    config : FBMCConfig
        Configuration object for FBMC parameters.
    
    Returns
    -------
    pypsa.Network
        The target zonal network with added FBMC constraints.
    """

    if config.advanced_hybrid_coupling_flag:
        basecase_link_data = {
            'df': basecase_nodal_network.links.loc[:, ['bus0', 'bus1']],
            'p0': basecase_nodal_network.links_t.p0,
            'p1': basecase_nodal_network.links_t.p1,
            'link_bus0_zone_mapping': basecase_nodal_network.links.bus0.map(basecase_nodal_network.buses.zone_name).rename("Zone"),
            'link_bus1_zone_mapping': basecase_nodal_network.links.bus1.map(basecase_nodal_network.buses.zone_name).rename("Zone"),
        }
    else: 
        basecase_link_data = None

    
    if basecase_nodal_network.sub_networks.empty:
        basecase_nodal_network.determine_network_topology()

    fbmc_parameters: dict[str, SubnetFBMCParameters] = {}

    net_positions_base_case = calc_base_net_positions(basecase_nodal_network)
    base_flows = get_base_flows(basecase_nodal_network)  # shape: (snapshots, branches)

    cne_reference_case_flows = define_cne_reference_case_flows(basecase_nodal_network, config)
    if cne_reference_case_flows is None:
        cne_reference_case_flows = base_flows
    for sub_network_name, sub_network_df in basecase_nodal_network.sub_networks.iterrows():
        sub_network = sub_network_df.obj
        if sub_network.buses_i().size < 3:
            logging.warning(f"Sub-network {sub_network_name} has less than 3 buses. Skipping FBMC parameter calculation and constraint addition for this sub-network.")
            continue

        subnet_fbmc_parameters: SubnetFBMCParameters = calculate_fbmc_parameters_subnet(sub_network, gsk, config=config, basecase_link_data=basecase_link_data, base_case_flows=base_flows, cne_reference_case_flows=cne_reference_case_flows, net_positions_base_case=net_positions_base_case)
        fbmc_parameters[sub_network_name] = subnet_fbmc_parameters
    
    return fbmc_parameters


def setup_fbmc_model(
        zonal_net: pypsa.Network, 
        basecase_nodal_network: pypsa.Network,
        gsk: pd.DataFrame | dict[pd.Timestamp, pd.DataFrame] = None,
        config: FBMCConfig = FBMCConfig()
    ) -> tuple[lp.Model, dict[str, SubnetFBMCParameters]]:
    """_summary_

    Args:
        zonal_net (pypsa.Network): _description_
        basecase_nodal_network (pypsa.Network): _description_
        gsk (pd.DataFrame | dict[pd.Timestamp, pd.DataFrame]): _description_
        gsk_strategy (GSKStrategy): _description_
        config (FBMCConfig, optional): _description_. Defaults to FBMCConfig().

    Returns:
        lp.Model: _description_
    """

    fbmc_parameters = calculate_fbmc_parameters(basecase_nodal_network, gsk, config=config)

    if zonal_net.model is None:
        zonal_net.optimize.create_model()
    create_zonal_generation(zonal_net)
    remove_original_constraints_loop(zonal_net, basecase_nodal_network)
    add_fbmc_constraints_loop(zonal_net, fbmc_parameters, config.advanced_hybrid_coupling_flag)
    return zonal_net.model, fbmc_parameters


def remove_original_constraints_loop(
    zonal_net: pypsa.Network,
    basecase_nodal_network: pypsa.Network
    ) -> None:
    """Remove original nodal balance constraint from `zonal_net` for zones that have more than three buses such that FBMC constraints can be generated. 

    Args:
        zonal_net (pypsa.Network): Zonal net for which original constraints should be removed
        basecase_nodal_network (pypsa.Network): Base case nodal network to determine sub-network sizes
    """
    if basecase_nodal_network.sub_networks.empty:
        basecase_nodal_network.determine_network_topology()

    sub_net_lengths = basecase_nodal_network.sub_networks.obj.apply(lambda x: len(x.buses()))

    if not (sub_net_lengths < 3).any():
        remove_original_constraints(zonal_net)  
        return 
    
    for name, sub_network_df in basecase_nodal_network.sub_networks.iterrows():
        sub_network = sub_network_df.obj
        if sub_network.buses_i().size >= 3:
            remove_original_constraints_by_bus(zonal_net, sub_network.buses().zone_name.unique())
    return


def add_fbmc_constraints_loop(
        zonal_net: pypsa.Network,
        fbmc_parameters: dict[str, SubnetFBMCParameters],
        advanced_hybrid_flag: bool,
    ) -> None:
    """Add FBMC constraints for each sub-network in the zonal network."""

    for sub_network_name, parameters in fbmc_parameters.items():
        zPTDF_xr = parameters.z_ptdf
        upper_RAM_xr = parameters.upper_ram
        lower_RAM_xr = parameters.lower_ram
        zones = parameters.zones
        link_ptdf_bus0 = parameters.link_ptdf_bus0
        link_ptdf_bus1 = parameters.link_ptdf_bus1

        add_fbmc_constraints(
            zonal_net,
            sub_network_name,
            zones,
            zPTDF_xr,
            upper_RAM_xr,
            lower_RAM_xr,
            advanced_hybrid_flag,
            link_ptdf_bus0,
            link_ptdf_bus1,
        )
        
        
def solve(
        zonal_net: pypsa.Network, 
        advanced_hybrid_flag: bool = False,
        ) -> tuple[pypsa.Network, pd.DataFrame]:
    """
    Run the FBMC process on the given networks.

    Parameters
    ----------
    nodal_network : pypsa.Network
        The nodal network to be used for FBMC.
    zonal_net : pypsa.Network
        The zonal network to be used for FBMC.
    config : FBMCConfig
        Configuration object for FBMC parameters.
    gsk_strategy : GSKStrategy
    Returns
    -------
    pypsa.Network
        The updated zonal network after FBMC.
    """


    # Run the optimization and save the results to the nodal network
    zonal_net.model.solve(solver_name="gurobi")
    if zonal_net.model.termination_condition != 'optimal':
        raise ValueError("FBMC optimization did not solve to optimality.")
    extract_model_results(zonal_net)

    net_positions = get_net_positions(zonal_net, advanced_hybrid_flag=advanced_hybrid_flag)

    return zonal_net, net_positions

