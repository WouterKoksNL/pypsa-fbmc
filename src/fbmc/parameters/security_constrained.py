import pypsa
import pandas as pd
import numpy as np

from src.fbmc.parameters.ptdf import get_subnetwork_bodf


def apply_security_param_changes(
        sub_network: pypsa.SubNetwork, 
        cnecs: pd.MultiIndex, 
        nodal_ptdf: pd.DataFrame, 
        base_flows: pd.DataFrame
        ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply security constraint parameter changes to nodal PTDF and base flows.""" 
    bodf = get_subnetwork_bodf(sub_network, cnecs)
    nodal_ptdf_outaged = apply_bodf(nodal_ptdf, bodf)
    base_flows_outaged = apply_bodf(base_flows.T, bodf).T
    return nodal_ptdf_outaged, base_flows_outaged


def calc_bodf_cnec_values(BODF: pd.DataFrame, cnecs: pd.MultiIndex) -> pd.Series:
    """
    Extract BODF values for each (line, outage) pair in cnecs.

    Parameters
    ----------
    BODF : pd.DataFrame
        The Branch Outage Distribution Factor matrix with shape (branches x outages).
    cnecs : pd.MultiIndex
        MultiIndex where the first level contains the outages and the second level contains the branches.

    Returns
    -------
    pd.Series
        Series containing the BODF values for each (line, outage) pair in cnecs.
    """
    

    branches = cnecs.get_level_values('branch')
    outages = cnecs.get_level_values('outage')

    # Get integer positions for each (branch, outage) pair
    row_idx = BODF.index.get_indexer(branches)
    col_idx = BODF.columns.get_indexer(outages)

    # Extract only the matching diagonal elements
    bodf_cnec_values = BODF.values[row_idx, col_idx]
    return bodf_cnec_values
    # return pd.Series(bodf_cnec_values, index=cnecs, name='BODF_value')

def apply_bodf(df: pd.DataFrame, bodf: pd.DataFrame) -> pd.DataFrame:
    """Assumes df has index branches."""
    outage_term = (df.loc[bodf.index.get_level_values(1)].T * bodf.values).T
    outage_term.index = bodf.index.get_level_values(0)
    result_df = df.reindex(bodf.index.get_level_values(0)) + outage_term
    result_df.index = bodf.index
    return result_df


def calc_outaged_base_flows(base_flows: pd.DataFrame, BODF: pd.DataFrame, cnecs: pd.MultiIndex) -> pd.DataFrame:
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
    bodf_cnec_values = calc_bodf_cnec_values(BODF, cnecs)
    additional_flow_from_outage = bodf_cnec_values * base_flows.loc[:, cnecs.get_level_values('outage')].values
    additional_flow_from_outage = pd.DataFrame(additional_flow_from_outage, index=snapshots)
    additional_flow_from_outage.columns = pd.Index(np.arange(cnecs.size), name='cnec')
    return additional_flow_from_outage


def reindex_to_cnec_nr(df: pd.DataFrame | pd.Series, cnecs_df: pd.DataFrame, from_index: str ='branch') -> pd.DataFrame | pd.Series:
    """
    Reindex the given DataFrame or Series to match the CNEC numbering.

    Parameters
    ----------
    df : pd.DataFrame | pd.Series
        The DataFrame or Series to reindex.
    cnecs_df : pd.DataFrame
        The CNEC DataFrame containing the new index.
    from_index : str
        The column name to use as the new index.

    Returns
    -------
    pd.DataFrame | pd.Series
        The reindexed DataFrame or Series.
    """
    return (
        df.reindex(index=cnecs_df[from_index])
        .set_axis(cnecs_df.index)
    )
