import pypsa
import pandas as pd
import numpy as np

from src.fbmc.parameters.ptdf import get_subnetwork_bodf, calculate_zonal_ptdf


BODF_COLUMNWISE_MATRIX_SIZE_LIMIT = 5_000_000


def apply_security_param_changes(
        sub_network: pypsa.SubNetwork, 
        cnecs: pd.MultiIndex, 
        nodal_ptdf: pd.DataFrame, 
        base_flows: pd.DataFrame,
        bodf_size_threshold: float,
        bodf_columnwise_matrix_size_limit: int = BODF_COLUMNWISE_MATRIX_SIZE_LIMIT,
        ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply security constraint parameter changes to nodal PTDF and base flows.""" 
    bodf = get_subnetwork_bodf(sub_network, cnecs, bodf_size_threshold)
    nodal_ptdf_outaged = apply_bodf(nodal_ptdf, bodf, matrix_size_limit=bodf_columnwise_matrix_size_limit)
    base_flows_outaged = apply_bodf(base_flows.T, bodf, matrix_size_limit=bodf_columnwise_matrix_size_limit).T
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

def _should_use_columnwise_bodf(
        df: pd.DataFrame,
        bodf: pd.Series,
        matrix_size_limit: int | None,
        ) -> bool:
    """Select a RAM-saving path when the intermediate matrix would be large."""
    if matrix_size_limit is None:
        return False
    estimated_elements = bodf.shape[0] * df.shape[1]
    return estimated_elements > matrix_size_limit


def apply_bodf_columnwise(df: pd.DataFrame, bodf: pd.Series) -> pd.DataFrame:
    """Apply BODF one column at a time to lower peak RAM usage."""
    cnec_branches = bodf.index.get_level_values(0)
    outage_branches = bodf.index.get_level_values(1)

    result_df = df.reindex(cnec_branches).copy()
    bodf_values = bodf.to_numpy()

    for column in result_df.columns:
        outage_contribution = df[column].reindex(outage_branches).to_numpy() * bodf_values
        result_df[column] = result_df[column].to_numpy() + outage_contribution

    result_df.index = bodf.index
    return result_df


def apply_bodf(
        df: pd.DataFrame,
        bodf: pd.Series,
        matrix_size_limit: int | None = BODF_COLUMNWISE_MATRIX_SIZE_LIMIT,
        ) -> pd.DataFrame:
    """Assumes df has index branches.
    Applies outage scenarios defined by the BODF. 
    Returns a new df with index as (line, outage) pairs and columns the same as the input df, containing the adjusted flows for each outage scenario.
    """

    if _should_use_columnwise_bodf(df, bodf, matrix_size_limit):
        return apply_bodf_columnwise(df, bodf)

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


def calculate_zonal_ptdf_advanced_hybrid(
    ptdf: pd.DataFrame, 
    gsk: pd.DataFrame, 
    cnecs: pd.Index | pd.MultiIndex,
    link_data: dict[str, pd.DataFrame],
    ):
    return _calculate_zonal_ptdf_advanced_hybrid(
        ptdf, 
        gsk,
        cnecs,
        link_data['df'],
        link_data['p0'],
        link_data['p1'],
        link_data['link_bus0_zone_mapping'],
        link_data['link_bus1_zone_mapping'],
    )


def _calculate_zonal_ptdf_advanced_hybrid(
        ptdf: pd.DataFrame, 
        gsk: pd.DataFrame, 
        cnecs: pd.Index | pd.MultiIndex,
        links_df: pd.DataFrame,
        links_p0: pd.DataFrame,
        links_p1: pd.DataFrame,
        link_bus0_zone_mapping: pd.Series,
        link_bus1_zone_mapping: pd.Series,
        ) -> pd.DataFrame:
    """
    Transform nodal PTDF to zonal PTDF using Generation Shift Keys (GSK).
    PTDF shape: (branches, buses)
    GSK shape: (zones, buses)
    CNECs shape: (branches) for N-0 CNECs, or (branches, outaged_branches) for N-1 CNECs
    zPTDF shape: (branches, zones), filtered on CNECs
    """
    z_ptdf = calculate_zonal_ptdf(ptdf, gsk, cnecs)
    
    links_with_bus0_in_subnet = links_df[links_df.bus0.isin(ptdf.columns)]
    links_with_bus1_in_subnet = links_df[links_df.bus1.isin(ptdf.columns)]

    
    
    ptdf_bus0 = ptdf.loc[:, links_with_bus0_in_subnet.bus0]
    ptdf_bus1 = ptdf.loc[:, links_with_bus1_in_subnet.bus1]
    ptdf_bus0.columns = links_with_bus0_in_subnet.index
    ptdf_bus1.columns = links_with_bus1_in_subnet.index
    
    link_term_bus0 = (
        (ptdf_bus0 * links_p0.loc[:, links_with_bus0_in_subnet.index].values)
        .T.groupby(link_bus0_zone_mapping).sum().T
        .reindex(z_ptdf.columns, fill_value=0.0, axis=1)
        )
    link_term_bus1 = (
        (ptdf_bus1 * links_p1.loc[:, links_with_bus1_in_subnet.index].values)
        .T.groupby(link_bus1_zone_mapping).sum().T
        .reindex(z_ptdf.columns, fill_value=0.0, axis=1)
    )
    return z_ptdf - link_term_bus0 + link_term_bus1


