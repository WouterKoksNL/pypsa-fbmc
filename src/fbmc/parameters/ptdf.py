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


def get_subnetwork_bodf(sub_network: pypsa.SubNetwork) -> pd.DataFrame:
    sub_network.calculate_BODF()
    bodf = pd.DataFrame(
        sub_network.BODF,
        index=sub_network.branches().index.droplevel(0), # Drop MultiIndex. The branches include lines and transformers
        columns=sub_network.branches().index.droplevel(0) # Ordered list of buses used in all PF and PTDF calculations (slack first, then PV, then PQ)
    )
    return bodf 


def calculate_zonal_ptdf(ptdf: pd.DataFrame, gsk: pd.DataFrame) -> pd.DataFrame:
    """
    Transform nodal PTDF to zonal PTDF using Generation Shift Keys (GSK).
    """
    if not set(ptdf.columns).issubset(set(gsk.columns)):
        raise ValueError("PTDF columns must match GSK bus names") #PTDF is based on subnetwork, GSK is based on full network
        
    #TODO: Check if the signs of the CNE are correct - if not, multiply by -1
    
    # Get the GSK for the nodes in the PTDF
    gsk_filtered = gsk.loc[:, ptdf.columns]
    gsk_filtered = gsk_filtered.loc[gsk_filtered.sum(axis=1) > 1e-6]  # Remove zones with no GSK in this subnetwork
    # Calculate the zPTDF by multiplying the PTDF with the GSK
    z_ptdf_array = np.dot(ptdf.values, gsk_filtered.T)

    # To dataframe; index = branches, columns = zones
    z_ptdf = pd.DataFrame(z_ptdf_array, index=ptdf.index, columns=gsk_filtered.index)
    
    return z_ptdf



def convert_zPTDF_to_xarray(zPTDF_data) -> xr.DataArray:
    """
    Convert zPTDF data to an xarray DataArray.
    
    Parameters
    ----------
    zPTDF_data : pd.DataFrame or dict of pd.DataFrame
        Either a single DataFrame containing zPTDF values for all snapshots,
        or a dictionary of DataFrames with snapshots as keys.
        
    Returns
    -------
    xr.DataArray
        For snapshot-dependent zPTDF: A 3D DataArray with dimensions [snapshot, CNE, Zone]
        For static zPTDF: A 2D DataArray with dimensions [CNE, Zone]
    """
    if isinstance(zPTDF_data, dict):
        # For snapshot-dependent zPTDF (dictionary of DataFrames)
        snapshots = list(zPTDF_data.keys())
        cnes = zPTDF_data[snapshots[0]].index
        zones = zPTDF_data[snapshots[0]].columns
        
        # Create a 3D array to hold all zPTDF values
        data_array = np.zeros((len(snapshots), len(cnes), len(zones)))
        
        # Fill the array with values from each snapshot
        for i, snapshot in enumerate(snapshots):
            data_array[i, :, :] = zPTDF_data[snapshot].values
        
        # Convert to xarray DataArray with proper dimensions and coordinates
        return xr.DataArray(
            data_array,
            dims=["snapshot", "cnec", "Zone"],
            coords={
                "snapshot": snapshots,
                "cnec": cnes,
                "Zone": zones
            }
        )
    else:
        # For static zPTDF (single DataFrame)
        return xr.DataArray(
            zPTDF_data,
            dims=["cnec", "Zone"],
            coords={"cnec": zPTDF_data.index, "Zone": zPTDF_data.columns}
        )