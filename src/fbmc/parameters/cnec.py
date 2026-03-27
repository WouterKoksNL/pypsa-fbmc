

import pandas as pd
import numpy as np
import networkx as nx
import logging
import pypsa

from .base_case import get_base_flows
from src.fbmc.config import FBMCConfig

logging.basicConfig(level=logging.INFO)

def cnec_router(
        sub_network: pypsa.SubNetwork,
        config: FBMCConfig
        ) -> pd.Index | pd.MultiIndex:
    bridge_branches = find_bridges_sub_network(sub_network)
    bridge_branches = bridge_branches.droplevel(0)  # Drop MultiIndex level for lines and transformers (SHOULD BE FIXED LATER)
    breakpoint()
    logging.info(f"Identified {len(bridge_branches)} bridge branches that will be excluded from CNECs: {bridge_branches}.")
    if config.cne_setting == 'all':
        cnes = sub_network.branches().index.droplevel(0).tolist()  # All lines and transformers
        outages = list(set(cnes) - set(bridge_branches))  # Remove bridges from CNEs
        cnecs = [(cne, outage) for cne in cnes for outage in outages if cne != outage]
    elif config.cne_setting == 'manual':
        # cnes = config.cne_list
        raise NotImplementedError('Manual CNE selection not implemented yet.')
    elif config.cne_setting == 'utilization_threshold':
        max_absolute_flow = get_base_flows(sub_network, config.use_zero_base_flows_flag).abs().max()
        line_capacity = sub_network.branches().s_nom.droplevel(0)
        cnes = _determine_cnes_threshold(
            max_absolute_flow,
            line_capacity,
            line_usage_threshold = config.line_usage_threshold
            )
        
    else:
        raise ValueError(f'cnec_setting {config.cnec_setting} not recognized. Choices are "all", "manual" or "utilization_threshold".')
    
    if config.add_security_constraints:
        cnecs = pd.MultiIndex.from_tuples(cnecs, names=['branch', 'outage'])
        return cnecs

    cnes = pd.Index(cnes, name='cnec')
    return cnes

def _determine_cnes_threshold(max_absolute_flow, line_capacity, line_usage_threshold) -> list:
    """
    Determine Critical Network Elements (CNEs) based on line usage.
    This function identifies the lines in the network that are considered 
    Critical Network Elements (CNEs) by comparing their maximum absolute power 
    flow to a predefined threshold. Lines with a maximum usage above the 
    threshold are classified as CNEs.
    Args:
        max_absolute_flow (pd.Series): The maximum absolute power flow for each line.
        line_capacity (pd.Series): The capacity of each line.
    Returns:
        list: A list of line indices that are considered Critical Network Elements (CNEs).
    """
    assert (0 < line_usage_threshold <= 1), 'Threshold is out of acceptable bounds: (0,1]'
    assert (max_absolute_flow.index == line_capacity.index).all(), 'Indices of max_absolute_flow and line_capacity do not match.'
    assert (max_absolute_flow >= 0).all(), 'Max absolute flow contains non-positive values.'
    assert (line_capacity > 0).all(), 'Line capacity contains non-positive values.'

    # TODO: Use data from a whole year to determine the critical network elements.
    # TODO: Include non-lines in the CNEs. NOTE: Wouter said this is not necessary for now.

    # Calculate the mean line usage
    max_line_usage = max_absolute_flow / line_capacity

    # Get the lines that are above the threshold
    cne_lines = max_line_usage[max_line_usage > line_usage_threshold].index.tolist()

    assert len(cne_lines) != 0, f'There are no Critical Network Elements for threshold {line_usage_threshold}.'
    return cne_lines


def filter_on_cne(ptdf_parameter: pd.DataFrame, cne_lines: list) -> pd.DataFrame:
    """
    Filters the PTDF parameter DataFrame to include only the specified critical network elements (CNEs).
    Args:
        ptdf_parameter (pd.DataFrame): A DataFrame with a multi-index, where the second level of the index 
                                        represents the critical network elements.
        cne_lines (list): A list of critical network elements to filter on.
    Returns:
        pd.DataFrame: A DataFrame filtered to include only the specified critical network elements, 
                        with the original multi-index restored and index names removed.
    Example:
        >>> import pandas as pd
        >>> data = {
        ...     'level_0': ['A', 'A', 'B', 'B'],
        ...     'level_1': ['CNE1', 'CNE2', 'CNE1', 'CNE3'],
        ...     'value': [10, 20, 30, 40]
        ... }
        >>> df = pd.DataFrame(data).set_index(['level_0', 'level_1'])
        >>> cne_lines = ['CNE1', 'CNE3']
        >>> filter_on_cne(df, cne_lines)
                value
        A CNE1     10
        B CNE1     30
        B CNE3     40
    """
    
    # Get the critical network elements (level_1) equal to the cne_lines
    cne_filtered_parameter = ptdf_parameter[ptdf_parameter.index.isin(cne_lines)]

    return cne_filtered_parameter


def find_bridges_sub_network(sub_network: pypsa.SubNetwork) -> pd.MultiIndex:
    """
    Identify bridges in the sub-network. A bridge is a line or transformer that, if removed, would increase the number of connected components in the network.
    These cannot be included as outages considered for CNECs since their outage would disconnect the network (BODF value of NaN).

    Parameters
    ----------
    sub_network : pypsa.SubNetwork

    Returns
    -------
    pd.MultiIndex
        MultiIndex of bridges in the network. (First level: branch type, second level: branch name)
    """

    G = sub_network.graph()
    bridges = list(nx.bridges(G))
    # find all components connecting the bus0 and bus1 pairs of the bridges
    bus0 = sub_network.branches().bus0
    bus1 = sub_network.branches().bus1
    
    bridge_branches = pd.MultiIndex(levels=[[], []], codes=[[], []])
    for u, v in bridges:
        mask = ((bus0 == u) & (bus1 == v)) | ((bus0 == v) & (bus1 == u))
        bridge_branches = bridge_branches.append(sub_network.branches().index[mask])  
    return bridge_branches

def find_bridges_network(net) -> pd.MultiIndex:
    """Loops over all sub-networks (connected AC) in a net and returns the bridge branches for each using the find_bridges_sub_network function.

    Args:
        net (pypsa.Network)

    Returns:
        pd.MultiIndex: MultiIndex of bridges in the network. (First level: branch type, second level: branch name)
    """
    bridge_branches = pd.MultiIndex(levels=[[], []], codes=[[], []])
    for subnet in net.sub_networks.obj:
        bridge_branches = bridge_branches.append(find_bridges_sub_network(subnet))
    return bridge_branches