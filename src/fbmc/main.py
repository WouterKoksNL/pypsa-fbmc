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

def setup_fbmc_model(basecase_nodal_network: pypsa.Network, zonal_net: pypsa.Network, config: FBMCConfig = FBMCConfig(), gsk=None) -> pypsa.Network:
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


    remove_original_constraints(zonal_net)
    create_zonal_generation(zonal_net)
    basecase_nodal_network.determine_network_topology()
    z_ptdf_dict = {}
    ram_dict = {}
    cnecs_dict = {}
    for sub_network_name, sub_network_data in basecase_nodal_network.sub_networks.iterrows():
        sub_network = sub_network_data.obj

        if sub_network.buses_i().size < 3:
            raise NotImplementedError("Sub-networks with less than 3 buses are not supported.")
        
        fbmc_parameters: FBMCParameters = calculate_fbmc_parameters(sub_network, gsk, config=config)

        z_ptdf_xr = convert_zPTDF_to_xarray(fbmc_parameters.z_ptdf_dict)
        upper_ram_xr = convert_RAM_to_xarray(fbmc_parameters.upper_ram_dict)
        lower_ram_xr = convert_RAM_to_xarray(fbmc_parameters.lower_ram_dict)

        z_ptdf_dict[sub_network_name] = z_ptdf_xr
        ram_dict[sub_network_name] = upper_ram_xr
        cnecs_dict[sub_network_name] = fbmc_parameters.cnecs
        add_fbmc_constraints(zonal_net, sub_network_name, sub_network, z_ptdf_xr, upper_ram_xr, lower_ram_xr)

    return zonal_net, fbmc_parameters


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

    # Set up the model
    if config.pos_neg_method:
        zonal_net = setup_pos_neg_fbmc_model(nodal_network, zonal_net, config=config)
    else:
        zonal_net, fbmc_parameters = setup_fbmc_model(nodal_network, zonal_net, config=config, gsk=gsk)


    # Run the optimization and save the results to the nodal network
    zonal_net.model.solve(solver_name="gurobi")
    breakpoint()
    return zonal_net, nodal_network, fbmc_parameters

