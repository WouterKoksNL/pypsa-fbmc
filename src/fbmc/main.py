# -*- coding: utf-8 -*-
"""
Created on Mon Mar 17 13:01:07 2025

@author: ameldekok
"""

import pypsa
import pandas as pd

from .parameters.main import calculate_fbmc_parameters
from .parameters.types import SubnetFBMCParameters
from .parameters.gsk import calculate_gsk

from .constraints.main import create_zonal_generation
from .constraints.main import add_fbmc_constraints, remove_original_constraints
from .config import FBMCConfig
from .results_extraction import extract_model_results




def setup_fbmc_model(basecase_nodal_network: pypsa.Network, zonal_net: pypsa.Network, config: FBMCConfig = FBMCConfig(), gsk=None, basecase_link_data=None,
                     ) -> tuple[pypsa.Network, dict[str, SubnetFBMCParameters]]:
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
    # Calculate parameters
    if gsk is None:
        gsk = calculate_gsk(basecase_nodal_network, config)
    if isinstance(gsk, pd.DataFrame):
        gsk = {snapshot: gsk.copy() for snapshot in zonal_net.snapshots}

    
    if zonal_net.model is None:
        zonal_net.optimize.create_model()

    if config.advanced_hybrid_coupling:
        basecase_link_data = {
            'df': basecase_nodal_network.links.loc[:, ['bus0', 'bus1']],
            'p0': basecase_nodal_network.links_t.p0,
            'p1': basecase_nodal_network.links_t.p1,
            'link_bus0_zone_mapping': basecase_nodal_network.links.bus0.map(basecase_nodal_network.buses.zone_name).rename("Zone"),
            'link_bus1_zone_mapping': basecase_nodal_network.links.bus1.map(basecase_nodal_network.buses.zone_name).rename("Zone"),
        }

    remove_original_constraints(zonal_net)
    create_zonal_generation(zonal_net)
    basecase_nodal_network.determine_network_topology()
    
    fbmc_parameters: dict[str, SubnetFBMCParameters] = {}

    for sub_network_name, sub_network_df in basecase_nodal_network.sub_networks.iterrows():
        sub_network = sub_network_df.obj

        subnet_fbmc_parameters: SubnetFBMCParameters = calculate_fbmc_parameters(sub_network, gsk, config=config, basecase_link_data=basecase_link_data)
        fbmc_parameters[sub_network_name] = subnet_fbmc_parameters

    add_fbmc_constraints_loop(zonal_net, fbmc_parameters)
    return zonal_net, fbmc_parameters


def add_fbmc_constraints_loop(
        zonal_net: pypsa.Network,
        fbmc_parameters: dict[str, SubnetFBMCParameters]
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
            link_ptdf_bus0,
            link_ptdf_bus1,
        )
        
        
def run_fbmc(
        nodal_network: pypsa.Network, 
        zonal_net: pypsa.Network, 
        config: FBMCConfig = FBMCConfig(), 
        gsk: None | pd.DataFrame | dict[pd.Timestamp, pd.DataFrame] = None
        ) -> tuple[pypsa.Network, pypsa.Network | None]:
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

    Returns
    -------
    pypsa.Network
        The updated zonal network after FBMC.
    """
    # Set up the model with FBMC parameters and constraints
    zonal_net, fbmc_parameters = setup_fbmc_model(nodal_network, zonal_net, config=config, gsk=gsk)

    # Run the optimization and save the results to the nodal network
    zonal_net.model.solve(solver_name="gurobi")
    extract_model_results(zonal_net)
    return zonal_net, nodal_network, fbmc_parameters

