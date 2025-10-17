import pypsa
import pandas as pd
import numpy as np


from .cnec import cnec_router
from .flows import calculate_ram
from .gsk import calculate_gsk
from .ptdf import calculate_zonal_ptdf, get_subnetwork_ptdf
from ..config import FBMCConfig
from .base_case import calc_base_net_positions, get_base_flows


def calculate_fbmc_parameters(
        sub_network: pypsa.SubNetwork,
        gsk: dict[pd.Timestamp, pd.DataFrame] | pd.DataFrame,
        config: FBMCConfig = FBMCConfig(),
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

    cnes = cnec_router(sub_network, config)

    ptdf = get_subnetwork_ptdf(sub_network)

    z_ptdf = {}
    for snapshot, gsk_snapshot in gsk.items():
        z_ptdf[snapshot] = calculate_zonal_ptdf(ptdf, gsk_snapshot, cnes)

                    reliability_margin_factor = config.reliability_margin_factor,
                    net_positions_base_case=net_positions_base_case,
                    add_zptdf_np_term=add_zptdf_np_term,
                    flow_direction=1)
    lower_ram =  -1 * calculate_ram(sub_network,
    net_positions_base_case = calc_base_net_positions(sub_network, config.use_zero_base_flows_flag)
    base_flows = get_base_flows(sub_network, config.use_zero_base_flows_flag)  # shape: (snapshots, branches)
    upper_ram, lower_ram = calculate_ram(sub_network,
                    zonal_ptdf_dict = z_ptdf, 
                    base_flows = base_flows,
                    min_ram = config.min_ram, 
                    reliability_margin_factor = config.reliability_margin_factor,
                    net_positions_base_case=net_positions_base_case,
                    )
    return upper_ram, lower_ram, z_ptdf

    