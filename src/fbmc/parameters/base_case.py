import pandas as pd
import pypsa


def get_base_flows(sub_network: pypsa.SubNetwork, use_zero_base_flows_flag: bool) -> pd.DataFrame:
    """Get the base case power flows from transformers, links and lines.
    Assumes there are no transformers, links or lines with the same name."""

    if use_zero_base_flows_flag:
        return pd.DataFrame(0., index=sub_network.snapshots, columns=sub_network.branches_i().droplevel(0))
    return pd.concat([
        sub_network.pnl('transformers')['p0'].T, 
        sub_network.pnl('lines')['p0'].T
    ]).T


def calc_base_net_positions(sub_network: pypsa.Network, use_zero_base_flows_flag: bool) -> pd.DataFrame:
    """Calculate net positions for each zone based on bus power values.
    
    Args:
        buses: DataFrame containing bus data with zone_name column
        buses_t: DataFrame containing time series bus power values
        zones: Index of zone names to calculate positions for
        
    Returns:
        DataFrame with net positions per zone
    """
    # zonal_p_generators = nodal_net.generators_t.p.T.groupby(nodal_net.generators.bus.map(nodal_net.buses.zone_name)).sum().T.reindex(columns=zones, fill_value=0.0)
    # zonal_p_storage_units = nodal_net.storage_units_t.p.T.groupby(nodal_net.storage_units.bus.map(nodal_net.buses.zone_name)).sum().T.reindex(columns=zones, fill_value=0.0)
    # zonal_p_link_p0 = nodal_net.links_t.p0.T.groupby(nodal_net.links.bus0.map(nodal_net.buses.zone_name)).sum().T.reindex(columns=zones, fill_value=0.0)
    # zonal_p_link_p1 = nodal_net.links_t.p1.T.groupby(nodal_net.links.bus1.map(nodal_net.buses.zone_name)).sum().T.reindex(columns=zones, fill_value=0.0)
    # zonal_p_link_total = zonal_p_link_p0 + zonal_p_link_p1
    # zonal_p_loads = nodal_net.loads_t.p.T.groupby(nodal_net.loads.bus.map(nodal_net.buses.zone_name)).sum().T.reindex(columns=zones, fill_value=0.0)

    # return zonal_p_generators + zonal_p_storage_units - zonal_p_link_total - zonal_p_loads
    if use_zero_base_flows_flag:
        net_positions = pd.DataFrame(0., index=sub_network.snapshots, columns=sub_network.buses()['zone_name'].unique())
        return net_positions
    net_positions = sub_network.pnl('buses')['p'].T.groupby(sub_network.df('buses').zone_name).sum().T
    if net_positions.sum(axis=1).abs().max() > 1e-6:
        raise ValueError("Net positions do not sum to zero.")
    return net_positions