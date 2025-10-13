import pypsa
import pandas as pd
import numpy as np


from .cne import cne_router
from .flows import get_base_flows, calculate_ram
from .gsk import calculate_gsk
from .ptdf import calculate_zonal_ptdf, get_subnetwork_ptdf
from ..config import FBMCConfig
from .net_positions import calc_net_positions_sub_network


def calculate_fbmc_parameters(
        sub_network: pypsa.SubNetwork,
        gsk: dict,
        config: FBMCConfig = FBMCConfig(),
        add_zptdf_np_term: bool = True,
        ) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.DataFrame], (dict | pd.DataFrame)]:
    """
    Calculate the Flow-Based Market Coupling (FBMC) parameters for a given power network basecase.

    Parameters:
        basecase (pypsa.Network): The power network basecase object containing network data such as lines, generators, and buses.
        config (FBMCConfig): Configuration object containing parameters for FBMC calculations. Defaults to FBMCConfig().

    Returns:
        Tuple[pd.DataFrame, Dict[pd.Timestamp, pd.DataFrame]]: 
            - ram_cnes: A DataFrame containing the Remaining Available Margin (RAM) filtered on Critical Network Elements (CNEs).
            - z_ptdf_cnes: A dictionary of DataFrames containing the zonal Power Transfer Distribution Factors (PTDF) filtered on CNEs,
              with one DataFrame per snapshot if using snapshot-based GSKs.

    Notes:
        - The function calculates the maximum absolute flow on lines, determines the CNEs, computes the Generation Shift Key (GSK),
          and calculates the PTDF and zonal PTDF.
        - The RAM is computed using a reliability margin factor and a minimum RAM threshold.
        - Both RAM and zonal PTDF are filtered based on the identified CNEs.
        - When using ITERATIVE_UNCERTAINTY GSK method, the zonal PTDF will vary by snapshot.
    """

    # Calculate the FBMC parameters

    if isinstance(gsk, pd.DataFrame):
        gsk = {snapshot: gsk.copy() for snapshot in sub_network.snapshots}

    ptdf = get_subnetwork_ptdf(sub_network)

    z_ptdf = {}
    for snapshot, gsk_snapshot in gsk.items():
        z_ptdf[snapshot] = calculate_zonal_ptdf(ptdf, gsk_snapshot)


    # Calculate RAM - this remains the same as it's already snapshot-based
    net_positions_base_case = calc_net_positions_sub_network(sub_network)
    base_flows = get_base_flows(sub_network)  # shape: (snapshots, branches)
    upper_ram = calculate_ram(sub_network,
                    zonal_ptdf_dict = z_ptdf, 
                    base_flows = base_flows,
                    min_ram = config.min_ram, 
                    reliability_margin_factor = config.reliability_margin_factor,
                    net_positions_base_case=net_positions_base_case,
                    add_zptdf_np_term=add_zptdf_np_term,
                    flow_direction=1)
    lower_ram =  -1 * calculate_ram(sub_network,
                    zonal_ptdf_dict = z_ptdf, 
                    base_flows = base_flows,
                    min_ram = config.min_ram, 
                    reliability_margin_factor = config.reliability_margin_factor,
                    net_positions_base_case=net_positions_base_case,
                    add_zptdf_np_term=add_zptdf_np_term,
                    flow_direction=-1)
    upper_ram, z_ptdf = cne_router(sub_network, upper_ram, z_ptdf, config)
    lower_ram, _ = cne_router(sub_network, lower_ram, z_ptdf, config)
    return upper_ram, lower_ram, z_ptdf

    