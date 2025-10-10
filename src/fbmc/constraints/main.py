"""
Add the FBMC constraints to the network
"""

import pypsa
from typing import Union, Dict
import pandas as pd
import xarray as xr

from .redispatch import add_gen_up_and_down_regulators, update_objective_function
from .fbmc_constraints import construct_cne_constraint, construct_zonal_balance_constraint
from .zonal_generation import define_net_positions_constraint, add_net_position_variable


def create_zonal_generation(network: pypsa.Network):
    """
    Main function to add zonal generation variables and constraints to the network.
    """
    # Add the zonal generation variable to the model
    zones = network.buses.index.to_list()
    snapshots = network.snapshots.to_list()
    add_net_position_variable(network, zones, snapshots)
    define_net_positions_constraint(network, network.snapshots, network.buses.index)
    return 

def add_fbmc_constraints(network: pypsa.Network, 
                         sub_network_name: str,
                         sub_network: pypsa.SubNetwork,
                         zPTDF_xr: xr.DataArray,
                         upper_RAM_xr: xr.DataArray,
                         lower_RAM_xr: xr.DataArray,
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
    zPTDF_xr = convert_zPTDF_to_xarray(zPTDF_df)
    RAM_xr = convert_RAM_to_xarray(RAM_df)



    # Restrict the load on CNEs by the Remaining Available Margin (RAM)
    upper_cne_constraint = construct_cne_constraint(zPTDF_xr, network.model.variables["Zone-p"], upper_RAM_xr, upper_bool=True)
    network.model.add_constraints(upper_cne_constraint, name=f"CNEC-upper-RAM-subnet-{sub_network_name}")

    # Restrict the load on CNEs by the Remaining Available Margin (RAM)
    lower_cne_constraint = construct_cne_constraint(zPTDF_xr, network.model.variables["Zone-p"], lower_RAM_xr, upper_bool=False)
    network.model.add_constraints(lower_cne_constraint, name=f"CNEC-lower-RAM-subnet-{sub_network_name}")

    # Ensure the Net Position of all zones adds up to 0
    zonal_balance_constraint = construct_zonal_balance_constraint(network.model.variables["Zone-p"])
    network.model.add_constraints(zonal_balance_constraint, name="Zonal_balance")


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

def add_redispatch_constraints(rd_nodal_network):
    """
    Add the redispatch constraints to the network.
    
    Parameters
    ----------
    rd_nodal_network : pypsa.Network
        The PyPSA network after Market Clearing, to add constraints to.
    
    Returns
    -------
    pypsa.Network
        The network with added redispatch constraints.
    """

    rd_nodal_network.optimize.create_model()

    # Add up- and down- regulators.
    add_gen_up_and_down_regulators(rd_nodal_network)

    # Add redispatch constraints
    rd_nodal_network = update_objective_function(rd_nodal_network)

    return rd_nodal_network
