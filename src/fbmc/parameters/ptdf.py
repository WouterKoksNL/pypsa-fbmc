import numpy as np
import pandas as pd
import pypsa
import xarray as xr


def get_subnetwork_ptdf(sub_network: pypsa.SubNetwork) -> pd.DataFrame:
    """
    Extract PTDF matrix from the network model.
    Returns PTDF matrix and associated sub_network.
    """
    sub_network.calculate_PTDF()
    ptdf = pd.DataFrame(
        sub_network.PTDF,
        index=sub_network.branches().index.droplevel(0), # Drop MultiIndex. The branches include lines and transformers
        columns=sub_network.buses_o # Ordered list of buses used in all PF and PTDF calculations (slack first, then PV, then PQ)
    )
    return ptdf


def get_subnetwork_bodf(sub_network: pypsa.SubNetwork, cnecs: pd.MultiIndex) -> pd.DataFrame:
    sub_network.calculate_BODF()
    bodf = pd.DataFrame(
        sub_network.BODF,
        index=sub_network.branches_i().droplevel(0), # Drop MultiIndex. The branches include lines and transformers
        columns=sub_network.branches_i().droplevel(0) # Ordered list of buses used in all PF and PTDF calculations (slack first, then PV, then PQ)
    )
    
    branches = cnecs.get_level_values(0)
    outaged_branches = cnecs.get_level_values(1)

    # Get integer positions for each (branch, outage) pair
    row_idx = bodf.index.get_indexer(branches)
    col_idx = bodf.columns.get_indexer(outaged_branches)

    # Extract only the matching diagonal elements
    bodf_cnec = bodf.values[row_idx, col_idx]
    bodf = pd.Series(bodf_cnec, index=cnecs, name='BODF')
    if bodf.isna().any().any():
        raise ValueError("BODF contains NaN values. Check if network bridges are filtered out of outage list.")
    return bodf


def calculate_zonal_ptdf(
        ptdf: pd.DataFrame, 
        gsk: pd.DataFrame, 
        cnecs: pd.Index | pd.MultiIndex,
        ) -> pd.DataFrame:
    """
    Transform nodal PTDF to zonal PTDF using Generation Shift Keys (GSK).
    PTDF shape: (branches, buses)
    GSK shape: (zones, buses)
    CNECs shape: (branches) for N-0 CNECs, or (branches, outaged_branches) for N-1 CNECs
    zPTDF shape: (branches, zones), filtered on CNECs
    """
    if not set(ptdf.columns).issubset(set(gsk.columns)):
        raise ValueError("PTDF columns must match GSK bus names") #PTDF is based on subnetwork, GSK is based on full network

    gsk_filtered = gsk.loc[:, ptdf.columns]
    gsk_filtered = gsk_filtered.loc[gsk_filtered.sum(axis=1) > 1e-6]  # Remove zones with zero GSK in this subnetwork

    z_ptdf = (gsk_filtered @ ptdf.T).T  # shape: (branches, zones)
    z_ptdf.index = cnecs
    return z_ptdf


