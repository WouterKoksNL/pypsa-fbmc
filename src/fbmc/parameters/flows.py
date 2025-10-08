import pandas as pd
import pypsa

from .helpers import get_net_positions


def calculate_flow_reliability_margin(line_capacities: pd.Series, reliability_margin_factor: float = 0.1) -> pd.Series:
    """Calculate Flow Reliability Margin (FRM) for transmission lines.
    
    Args:
        line_capacities: Thermal capacity limits in MW
        reliability_margin_factor: Safety factor (0-1, default 0.1)
        
    Returns:
        Flow Reliability Margin values in MW
    """
    if not 0 <= reliability_margin_factor <= 1:
        raise ValueError("Reliability margin factor must be between 0 and 1")
    
    if (line_capacities < 0).any():
        raise ValueError("Line capacities must be positive")

    return line_capacities * reliability_margin_factor


def get_base_flows(sub_network: pypsa.SubNetwork) -> pd.DataFrame:
    """Get the base case power flows from transformers, links and lines.
    Assumes there are no transformers, links or lines with the same name."""
    return pd.concat([
        basecase.lines_t.p0.T
    ])
        sub_network.pnl('lines')['p0'].T
    ]).T


def calculate_branch_capacity(sub_network: pd.DataFrame) -> pd.Series:
    return sub_network.branches().s_nom.droplevel(0)


                  min_ram: float = 0.0,
                  reliability_margin_factor: float = 0.1,
                  net_positions_base_case: None | pd.DataFrame = None,
                  add_zptdf_np_term: bool = True,
                  ) -> pd.DataFrame:
    """
    Calculate the Remaining Available Margin (RAM) for a given power network.
    Optional: Add a zonal PTDF term to the RAM calculation: zPTDF * net_positions

    Args:
        network: PyPSA network containing the initial state
        min_ram: Minimum RAM value as fraction of capacity (default 0.0)
        reliability_margin_factor: Safety factor for reliability margin (default 0.1)

    Returns:
        DataFrame (snapshots x branches) of RAM values
    """
    if network.transformers.index.isin(network.lines.index).any():
    if sub_network.transformers_i().isin(sub_network.lines_i()).any():
        raise ValueError("Transformers and lines cannot have the same names")
    if not network.links.empty:

    # Get base state
    base_flows = get_base_flows(network)  # shape: (branches, snapshots)
    branch_capacity = network.branches().s_nom
    branch_capacity.index = branch_capacity.index.droplevel(0)  # Drop MultiIndex

    base_flows = get_base_flows(sub_network)  # shape: (snapshots, branches)
    if net_positions_base_case is None:
        zones = zonal_ptdf_dict[list(zonal_ptdf_dict.keys())[0]].index
        net_positions_base_case = pd.DataFrame(0., index=sub_network.snapshots, columns=zones)

            

    ram_dict = {}

            ram = (partial_ram - base_flows.loc[zptdf_df.index, snapshot])
                zptdf_term = zptdf_df @ net_positions.T  # shape: (branches,)
    for snapshot in sub_network.snapshots:
        if snapshot not in zonal_ptdf_dict:
            raise ValueError(f"Snapshot {snapshot} missing from zonal_ptdf dict.")
        
        zptdf_df = zonal_ptdf_dict[snapshot]
        net_positions_base_case_t = net_positions_base_case.loc[snapshot]
        branch_capacity = calculate_branch_capacity(sub_network)

        # Calculate flow reliability margin
        frm = calculate_flow_reliability_margin(branch_capacity, 

        partial_ram = branch_capacity - frm
        partial_ram = partial_ram.loc[zonal_ptdf.index]

        ram = (partial_ram.loc[zptdf_df.index] - base_flows.loc[snapshot, zptdf_df.index])

        if add_zptdf_np_term:

        if min_ram > 0:
            ram = ram.clip(lower=min_ram * branch_capacity)
    ram_df = pd.DataFrame(ram_dict) # shape: (branches, snapshots)
    ram_df.index.name = "CNE"

    return ram_df
