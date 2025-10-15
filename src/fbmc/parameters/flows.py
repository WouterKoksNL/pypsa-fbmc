import pandas as pd
import pypsa
import xarray as xr


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





def calculate_branch_capacity(sub_network: pd.DataFrame) -> pd.Series:
    return sub_network.branches().s_nom.droplevel(0)

    
def calculate_ram(sub_network: pypsa.SubNetwork,
                  zonal_ptdf_dict,
                  base_flows: pd.DataFrame,
                  min_ram: float = 0.0,
                  reliability_margin_factor: float = 0.1,
                  net_positions_base_case: None | pd.DataFrame = None,
                  add_zptdf_np_term: bool = True,
                  flow_direction: int = 1,
                  ) -> pd.DataFrame:
    """
    Calculate the Remaining Available Margin (RAM) for a given power network.
    Optional: Add a zonal PTDF term to the RAM calculation: zPTDF * net_positions.

    Args:
        network: PyPSA network containing the initial state
        zonal_ptdf_dict: dict {snapshot: pd.DataFrame[zones, CNECs]}
        min_ram: Minimum RAM value as fraction of capacity (default 0.0)
        reliability_margin_factor: Safety factor for reliability margin (default 0.1)

    Returns:
        DataFrame (branches x snapshots) of RAM values
    """
    if sub_network.transformers_i().isin(sub_network.lines_i()).any():
        raise ValueError("Transformers and lines cannot have the same names")

    example_zptdf = list(zonal_ptdf_dict.values())[0]
    if net_positions_base_case is None:
        zones = example_zptdf.columns
        net_positions_base_case = pd.DataFrame(0., index=sub_network.snapshots, columns=zones)

    cnec = example_zptdf.index   # need to make the rest of the code to be able to handle full CNEC description. 
    # ideally, we have a CNEC labelling representing tuples of (line, outage, direction)

    ram_dict = {}

    for snapshot in sub_network.snapshots:
        if snapshot not in zonal_ptdf_dict:
            raise ValueError(f"Snapshot {snapshot} missing from zonal_ptdf dict.")
        
        zptdf_df = zonal_ptdf_dict[snapshot]
        net_positions_base_case_t = net_positions_base_case.loc[snapshot]
        branch_capacity = calculate_branch_capacity(sub_network)

        # Calculate flow reliability margin
        frm = calculate_flow_reliability_margin(branch_capacity, 
                                                reliability_margin_factor=reliability_margin_factor)

        partial_ram = branch_capacity - frm
        
        reference_flow = base_flows.loc[snapshot, cnec] 
        if add_zptdf_np_term:
            reference_flow -= zptdf_df @ net_positions_base_case_t.T

        ram = partial_ram.loc[cnec] - flow_direction * reference_flow
        if min_ram > 0:
            ram = ram.clip(lower=min_ram * branch_capacity)

        ram_dict[snapshot] = ram
    ram_df = pd.DataFrame(ram_dict) # shape: (branches, snapshots)
    ram_df.index.name = "cnec"

    return ram_df



def convert_RAM_to_xarray(RAM_df: pd.DataFrame) -> xr.DataArray:
    """
    Convert a DataFrame containing RAM values to a DataArray.
    """
    return xr.DataArray(
        RAM_df,
        dims=["cnec", "snapshot"],
        coords={"cnec": RAM_df.index, "snapshot": RAM_df.columns}
    )