

import pandas as pd
import numpy as np
import networkx as nx
import logging
import pypsa
import xarray as xr

from fbmc.settings import FBMCConfig

from fbmc.core.parameters.derived.base_case import get_base_flows

from ..derived.bridge_branches import find_bridges_sub_network

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cnecs_from_combinatorial_cne_and_outages(cnes: xr.Coordinates, outages: xr.Coordinates) -> xr.Coordinates:
    """Create a MultiIndex of (cne, outage) pairs for all combinations of cnes and outages, excluding pairs where cne == outage."""
    mask = cnes['branch'] != outages['outage']  # broadcasts to (branch, outage)
    cnecs_stacked = mask.where(mask).stack(cnec=('branch', 'outage')).dropna('cnec').coords

    return cnecs_stacked


def cnec_router(
        net: pypsa.Network,
        config: FBMCConfig,
        **kwargs
        ) -> dict[str, xr.Coordinates]:
    """Router function to determine CNECs based on the configuration. This function can be extended in the future to include more complex logic for determining CNECs.
    """
    cnecs_dict = {}
    for subnet in net.sub_networks.obj:
        cnecs = cnec_subnet_router(subnet, config, **kwargs)
        cnecs_dict[subnet.name] = cnecs
    return cnecs_dict


def cnec_subnet_router(
        sub_network: pypsa.SubNetwork,
        config: FBMCConfig,
        **kwargs
        ) -> xr.Coordinates:
    bridge_branches = find_bridges_sub_network(sub_network)

    logging.info(f"Identified {len(bridge_branches)} bridge branches that will be excluded from CNECs: {bridge_branches}.")
    if config.cnec_setting == 'all':
        cnes = sub_network.branches().index.droplevel(0) 
        cnes = xr.DataArray(
            data=cnes.values,
            coords={'branch': cnes.values},
            dims=['branch']
        ).assign_coords(branch_component=('branch', sub_network.branches().index.get_level_values(0).values))
        mask = ~xr.DataArray(
            np.isin(cnes.coords['branch'].values, bridge_branches),
            dims='branch'
        )
        outages = cnes.sel(branch=mask).copy().rename({'branch': 'outage', 'branch_component': 'outage_component'})
        cnecs = cnecs_from_combinatorial_cne_and_outages(cnes, outages)
        breakpoint()
    elif config.cnec_setting == 'manual':
        # cnes = config.cne_list
        raise NotImplementedError('Manual CNE selection not implemented yet.')
    else:
        raise ValueError(f'cnec_setting {config.cnec_setting} not recognized. Choices are "all", "manual".')
    
    if config.add_security_constraints:
        return cnecs
    else:
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
        xr.DataArray: A DataArray containing the identified CNEs, with coords (branch, component) and dimension 'branch'.
    """
    assert (0 <= line_usage_threshold <= 1), 'Threshold is out of acceptable bounds: [0,1]'
    assert (max_absolute_flow.coords['branch'] == line_capacity.coords['branch']).all(), 'Indices of max_absolute_flow and line_capacity do not match.'
    assert (max_absolute_flow >= 0).all(), 'Max absolute flow contains non-positive values.'
    assert (line_capacity > 0).all(), 'Line capacity contains non-positive values.'

    max_line_usage = max_absolute_flow / line_capacity
    cne = max_line_usage[max_line_usage > line_usage_threshold].coords
    assert len(cne) != 0, f'There are no Critical Network Elements for threshold {line_usage_threshold}.'
    return cne


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

