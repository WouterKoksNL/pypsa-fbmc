"""
Add the FBMC constraints to the network
"""

import pypsa
import pandas as pd
import xarray as xr

from .fbmc_constraints import construct_cne_constraint, construct_zonal_balance_constraint
from .zonal_generation import define_net_positions_constraint, add_net_position_variable
from .link_flows import construct_cne_constraint_advanced_hybrid

def create_zonal_generation(network: pypsa.Network):
    """
    Main function to add zonal generation variables and constraints to the network.
    """
    # Add the zonal generation variable to the model
    zones = network.buses.index.to_list()
    snapshots = network.snapshots.to_list()
    add_net_position_variable(network, zones, snapshots)
    define_net_positions_constraint(network)

    return 

def add_fbmc_constraints(
        network: pypsa.Network, 
        sub_network_name: str,
        zones: pd.Index,
        zPTDF_xr: xr.DataArray,
        upper_RAM_xr: xr.DataArray,
        lower_RAM_xr: xr.DataArray,
        advanced_hybrid_flag: bool,
        link_ptdf_bus0: pd.DataFrame | None = None,
        link_ptdf_bus1: pd.DataFrame | None = None
    ) -> pypsa.Network:
    """
    Main function to add FBMC constraints to the network.
    
    Parameters
    ----------
    network : pypsa.Network
        The zonal PyPSA network to add constraints to.
    zPTDF_df : pd.DataFrame or dict of pd.DataFrame
        Either a single DataFrame containing zPTDF values (static GSKs),
        or a dictionary of DataFrames with snapshots as keys (snapshot-based GSKs).
    RAM_df : pd.DataFrame
        DataFrame containing RAM values.
    """
    # xarray conversion

    link_flows = network.model.variables["Link-p"] if ("Link-p" in network.model.variables) and advanced_hybrid_flag else None

    # Restrict the load on CNEs by the Remaining Available Margin (RAM)
    upper_cne_constraint = construct_cne_constraint_advanced_hybrid(
        zPTDF_xr, 
        network.model.variables["Zone-p"],
        upper_RAM_xr, 
        upper_bool=True, 
        advanced_hybrid_flag=advanced_hybrid_flag,
        link_flows=link_flows,
        link_ptdf_bus0=link_ptdf_bus0, 
        link_ptdf_bus1=link_ptdf_bus1)
    network.model.add_constraints(upper_cne_constraint, name=f"CNEC-upper-RAM-subnet-{sub_network_name}")

    # Restrict the load on CNEs by the Remaining Available Margin (RAM)
    lower_cne_constraint = construct_cne_constraint_advanced_hybrid(
        zPTDF_xr, 
        network.model.variables["Zone-p"], 
        lower_RAM_xr, 
        upper_bool=False, 
        advanced_hybrid_flag=advanced_hybrid_flag,
        link_flows=link_flows,
        link_ptdf_bus0=link_ptdf_bus0, 
        link_ptdf_bus1=link_ptdf_bus1)
    network.model.add_constraints(lower_cne_constraint, name=f"CNEC-lower-RAM-subnet-{sub_network_name}")

    # Ensure the Net Position of all zones adds up to 0
    zonal_balance_constraint = construct_zonal_balance_constraint(network.model.variables["Zone-p"].sel(Zone=zones))
    network.model.add_constraints(zonal_balance_constraint, name=f"Zonal_balance-subnet-{sub_network_name}")

    

def remove_original_constraints(network):
    """"
    Remove the original constraints introduced by pyPSA from the network model.
    
    Parameters
    ----------
    network : pypsa.Network
        The zonal PyPSA network from which to remove constraints.

    """

    # network.model.remove_variables("Link-p")
    # network.model.remove_constraints("Link-fix-p-lower")
    # network.model.remove_constraints("Link-fix-p-upper")
    network.model.remove_constraints("Bus-nodal_balance")
    
    # if it exists, remove the bus-meshed-nodal_balance constraint as well.
    if "Bus-meshed-nodal_balance" in network.model.constraints:
        network.model.remove_constraints("Bus-meshed-nodal_balance")
