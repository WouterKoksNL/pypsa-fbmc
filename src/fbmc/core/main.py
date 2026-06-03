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
from ..types import SubnetFBMCParameters
from .parameters.cnec import define_cne_reference_case_flows
from .constraints.main import create_zonal_generation
from .constraints.main import add_fbmc_constraints, remove_original_constraints, remove_original_constraints_by_bus
from ..settings import FBMCConfig
from .results_extraction import extract_model_results, get_net_positions
from .parameters.base_case import calc_base_net_positions, get_base_flows
logging.basicConfig(level=logging.INFO)


def _create_model_without_meshed_split(network: pypsa.Network, create_model_kwargs: dict = None) -> lp.Model:
    """Create PyPSA model without separate meshed/weakly-meshed nodal balance."""
    from pypsa.optimization import optimize as optimize_module

    if create_model_kwargs is None:
        create_model_kwargs = {}

    original_get_meshed = optimize_module.get_strongly_meshed_buses

    def _no_meshed_buses(n: pypsa.Network, threshold: int = 45) -> pd.Index:
        return pd.Index([], name=n.buses.index.name)

    optimize_module.get_strongly_meshed_buses = _no_meshed_buses

    model = network.optimize.create_model(**create_model_kwargs)
    logging.info("Created optimization model without meshed split.")

    optimize_module.get_strongly_meshed_buses = original_get_meshed

    return model

def post_model_creation_workflow(zonal_net: pypsa.Network, config: FBMCConfig):
    if config.transfer_limit_UA_flag:
        logging.info(f"Applying limit of {config.transfer_limit_EUR_UA} (EUR->UA) and {config.transfer_limit_UA_EUR} (UA->EUR) on total transfer to UA/MD.")
        ua_links = zonal_net.links.index[(zonal_net.links.bus0 == "UA") | (zonal_net.links.bus1 == "UA")]
        zonal_net.model.add_constraints(zonal_net.model.variables["Link-p"].sel(Link=ua_links).sum(dim="Link") <= config.transfer_limit_EUR_UA, name="total_transfer_limit_EUR_UA")
        zonal_net.model.add_constraints(-zonal_net.model.variables["Link-p"].sel(Link=ua_links).sum(dim="Link") <= config.transfer_limit_UA_EUR, name="total_transfer_limit_UA_EUR")
        

    if config.net_position_limit_UA_flag:
        logging.info(f"Applying limits of {config.net_position_UA_lower_limit} and {config.net_position_UA_upper_limit} on net position of UA.")
        
        zonal_net.model.add_constraints(
            zonal_net.model.variables["Zone-p"].sel(Zone="UA") >= config.net_position_UA_lower_limit, name="net_position_lower_limit_UA"
            )
        zonal_net.model.add_constraints(
            zonal_net.model.variables["Zone-p"].sel(Zone="UA") <= config.net_position_UA_upper_limit, name="net_position_upper_limit_UA"
            )
        
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
    logging.info(f"Determined {len(basecase_nodal_network.sub_networks)} sub-networks in the base case nodal network.")
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
        lp.Model: linopy model with FBMC constraints added
        dict[str, SubnetFBMCParameters]: dict of FBMC parameters for each sub-network
    """

    fbmc_parameters = calculate_fbmc_parameters(basecase_nodal_network, gsk, config=config)

    if zonal_net.model is None:
        model = _create_model_without_meshed_split(zonal_net, create_model_kwargs=config.fbmc_create_model_kwargs)
    
    create_zonal_generation(zonal_net)
    remove_original_constraints_loop(zonal_net, basecase_nodal_network)
    add_fbmc_constraints_loop(zonal_net, fbmc_parameters, 
                              config.advanced_hybrid_coupling_flag, 
                              config.upper_ram_only_flag)
    post_model_creation_workflow(zonal_net, config)
    return model, fbmc_parameters


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
            zones = sub_network.buses().zone_name.unique()
            zonal_buses = zonal_net.buses.index[zonal_net.buses.index.isin(zones)]
            remove_original_constraints_by_bus(zonal_net, zonal_buses)
    return


def add_fbmc_constraints_loop(
        zonal_net: pypsa.Network,
        fbmc_parameters: dict[str, SubnetFBMCParameters],
        advanced_hybrid_flag: bool,
        upper_ram_only_flag: bool,
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
            upper_ram_only_flag
        )
        
        
def solve(
        zonal_net: pypsa.Network, 
        advanced_hybrid_flag: bool = False,
        solver_kwargs: dict[str, str] = None
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
    if solver_kwargs is None:
        solver_kwargs = {}

    # Run the optimization and save the results to the nodal network
    zonal_net.model.solve(**solver_kwargs)
    if zonal_net.model.termination_condition != 'optimal':
        raise ValueError("FBMC optimization did not solve to optimality.")
    extract_model_results(zonal_net)

    net_positions = get_net_positions(zonal_net, advanced_hybrid_flag=advanced_hybrid_flag)

    return zonal_net, net_positions

