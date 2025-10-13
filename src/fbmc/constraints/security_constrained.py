import pypsa
from itertools import product
import pandas as pd
import xarray as xr
from typing import Sequence, Any
import numpy as np

from src.fbmc.parameters.ptdf import get_subnetwork_ptdf, get_subnetwork_bodf, calculate_zonal_ptdf
from src.fbmc.parameters.flows import get_base_flows, calculate_ram
# from ..network_conversion import nodal_to_zonal
# from network_conversion import nodal_to_zonal


def add_security_constraints(
    sub_network: pypsa.SubNetwork,
    gsk: pd.DataFrame = None, 
    cnecs: pd.MultiIndex | None = None,
    cnes: pd.Index | None = None,
    branch_outages: Sequence | pd.Index | pd.MultiIndex | None = None,
    model_kwargs: dict | None = None,
    **kwargs: Any,
) -> tuple[str, str]:
    """Add security constraints to zonal network.

    This ensures that no branch is overloaded even given the branch outages.

    Parameters
    ----------
    snapshots : list-like, optional
        Set of snapshots to consider in the optimization. The default is None.
    branch_outages : list-like/pandas.Index/pandas.MultiIndex, optional
        Subset of passive branches to consider as possible outages. If a list
        or a pandas.Index is passed, it is assumed to identify lines. If a
        multiindex is passed, its first level has to contain the component names,
        the second the assets. The default None results in all passive branches
        to be considered.
    multi_investment_periods : bool, default False
        Whether to optimise as a single investment period or to optimise in multiple
        investment periods. Then, snapshots should be a ``pd.MultiIndex``.
    model_kwargs: dict
        Keyword arguments used by `linopy.Model`, such as `solver_dir` or `chunk`.
    **kwargs:
        Keyword argument used by `linopy.Model.solve`, such as `solver_name`,
        `problem_fn` or solver options directly passed to the solver.

    """
    if model_kwargs is None:
        model_kwargs = {}

    if (cnecs is not None) and ((branch_outages is not None) or (cnes is not None)):
        raise ValueError("If cnecs are passed, branch_outages and cnes must not be passe")
    

    
    all_passive_branches = sub_network.branches().index.droplevel(0)
    if cnecs is None:
        if cnes is None:
            cnes = all_passive_branches
        if branch_outages is None:
            branch_outages = all_passive_branches[:3]
        cnecs_tuples_list = [(branch, outage) for branch, outage in product(cnes, branch_outages) if branch != outage]
        cnecs = pd.MultiIndex.from_tuples(cnecs_tuples_list, names=['branch', 'outage'])
        cnecs_df = cnecs.to_series().reset_index().drop(columns=0)
        cnecs_df.index.name = 'cnec'
    if branch_outages is None:
        branch_outages = all_passive_branches


    branches_i = sub_network.branches_i().droplevel(0)
    outages = branches_i.intersection(branch_outages)

    # if outages.empty:
    #     continue

    BODF = get_subnetwork_bodf(sub_network)

    if gsk is None:
        bus_inds = sub_network.buses().index
        zones = sub_network.buses()['zone_name'].unique()
        gsk = pd.DataFrame(np.random.rand(bus_inds.size, zones.size), 
                            index=bus_inds,
                            columns=zones,
                            )

    nPTDF = get_subnetwork_ptdf(sub_network)
    # nPTDF = nPTDF.reindex(cnecs_df['branch'])
    # nPTDF.index = cnecs_df.index

        # Create all (line, outage) pairs excluding self-contingencies

    # pairs = list(product(cnes, branch_outages))
    # multi_index = pd.MultiIndex.from_tuples(pairs, names=['branch', 'outage']) 

    # BODF.loc[branch, outage].T * PTDF.loc[branch, sub_network.buses().index]
    # nPTDF_security = (
    #     PTDF.loc[cnecs.get_level_values('branch'), sub_network.buses_o] + 
    #     BODF.loc[cnecs.get_level_values('branch'), cnecs.get_level_values('outage')] @ PTDF.loc[cnecs.get_level_values('outage'), sub_network.buses_o]
    # )  # dims (CNEC x bus)
    # nPTDF_security.index = cnecs
    
    if isinstance(gsk, dict):
        # zPTDF = {
        #     snapshot: nPTDF_security @ gsk_snapshot.loc[:, sub_network.buses_o].T
        #     for snapshot, gsk_snapshot in gsk.items()
        # }
        zPTDF = {
            snapshot: calculate_zonal_ptdf(nPTDF, gsk_snapshot)
            for snapshot, gsk_snapshot in gsk.items()
        }

        zones = list(zPTDF.values())[0].columns
        

    base_flows = get_base_flows(sub_network)  # shape: (snapshots, branches)
    outaged_base_flows = calc_outaged_base_flows(base_flows, BODF, cnecs)
    base_flows.reindex(columns=cnecs_df['branch'])
    flow_direction = 1
    upper_ram = calculate_ram(sub_network, zPTDF, base_flows, flow_direction=flow_direction)
    upper_ram = upper_ram + flow_direction * (base_flows.reindex(columns=cnecs_df['branch']).T - outaged_base_flows.T)
    upper_ram.index = cnecs_df.index

    flow_direction = -1
    lower_ram = calculate_ram(sub_network, zPTDF, base_flows, flow_direction=flow_direction)
    lower_ram = lower_ram + flow_direction * (base_flows.reindex(columns=cnecs_df['branch']).T - outaged_base_flows.T)
    lower_ram.index = cnecs_df.index

    
    for snapshot, zPTDF_t in zPTDF.items():
        zPTDF[snapshot] = zPTDF_t.reindex(index=cnecs_df['branch'])
        zPTDF[snapshot].index = cnecs_df.index


    return upper_ram, lower_ram, zPTDF

def calc_outaged_base_flows(base_flows: pd.DataFrame, BODF: pd.DataFrame, cnecs) -> pd.DataFrame:
    """
    Calculate the outaged base flows for all (line, outage) pairs.

    Parameters
    ----------
    sub_network : pypsa.SubNetwork
        The sub-network containing the branches and buses.
    BODF : pd.DataFrame
        The Branch Outage Distribution Factor matrix with shape (branches x outages).
    base_flows : pd.DataFrame
        DataFrame containing the base flows with index as snapshots and columns as branches.

    Returns
    -------
    pd.DataFrame
        DataFrame containing the outaged base flows with index snapshot and columns MultiIndex (snapshot, CNEC).
    """

    snapshots = base_flows.index
    branches = cnecs.get_level_values('branch')
    outages = cnecs.get_level_values('outage')

    # Get integer positions for each (branch, outage) pair
    row_idx = BODF.index.get_indexer(branches)
    col_idx = BODF.columns.get_indexer(outages)

    # Extract only the matching diagonal elements
    bodf_cnec_values = BODF.values[row_idx, col_idx]

    outaged_flow = base_flows.loc[:, cnecs.get_level_values('branch')] + bodf_cnec_values * base_flows.loc[:, cnecs.get_level_values('outage')].values
    outaged_flow_df = pd.DataFrame(outaged_flow, index=snapshots)

    # outaged_flow_df.columns = cnecs 
    outaged_flow_df.columns = pd.Index(np.arange(cnecs.size), name='CNEC')


    return outaged_flow
