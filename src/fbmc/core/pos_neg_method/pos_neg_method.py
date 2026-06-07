# -*- coding: utf-8 -*-
"""
Created on Mon Mar 17 13:01:07 2025

@author: wouterko
"""

import pypsa
import pandas as pd
from scipy.stats import norm
from scipy.stats import halfnorm

from ..derived_parameters.main import calculate_fbmc_parameters
from ..constraints import create_zonal_generation, remove_original_constraints, add_pos_neg_fbmc_constraints
from ...settings import FBMCConfig
from ..input_parameters.gsk import calc_pos_neg_gsk

def setup_pos_neg_fbmc_model(basecase_nodal_network: pypsa.Network, target_zonal_network: pypsa.Network, config: FBMCConfig = FBMCConfig()) -> pypsa.Network:
    """
    Set up the FBMC model with split positive and negative GSKs for the target zonal network.
    
    Parameters
    ----------
    basecase_nodal_network : pypsa.Network
        The base case nodal network to be used for FBMC.
    target_zonal_network : pypsa.Network
        The target zonal network to be used for FBMC.
    config : FBMCConfig
        Configuration object for FBMC parameters.
    
    Returns
    -------
    pypsa.Network
        The target zonal network with added FBMC constraints.
    """
    # Calculate parameters
    pos_isk, neg_isk = calc_pos_neg_gsk(basecase_nodal_network, standard_deviation=config.gsk_std_dev)
    ram_cnes, z_ptdf_cnes_pos, _ = calculate_fbmc_parameters(basecase_nodal_network, config=config, gsk=pos_isk, add_zptdf_np_term=False)
    ram_cnes, z_ptdf_cnes_neg, _ = calculate_fbmc_parameters(basecase_nodal_network, config=config, gsk=neg_isk, add_zptdf_np_term=False)
    
    
    net_position_base_case = (
        basecase_nodal_network.generators_t.p.T.groupby(target_zonal_network.generators.bus).sum().T.reindex(columns=target_zonal_network.buses.index, fill_value=0.)
        -
        basecase_nodal_network.loads_t.p.T.groupby(target_zonal_network.loads.bus).sum().T.reindex(columns=target_zonal_network.buses.index, fill_value=0.)
    )
    # Add constraints
    target_zonal_network = create_zonal_generation(target_zonal_network)
    target_zonal_network = add_pos_neg_fbmc_constraints(target_zonal_network, z_ptdf_cnes_pos, z_ptdf_cnes_neg, ram_cnes, net_position_base_case)
    remove_original_constraints(target_zonal_network)

    return target_zonal_network

