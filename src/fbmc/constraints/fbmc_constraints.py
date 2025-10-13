import linopy as lp
import pandas as pd
import xarray as xr
import numpy as np

# ---- Data Transformations ----



# ---- Load Mapping ----

def create_load_zone_mapping(loads: pd.DataFrame) -> xr.DataArray:
    """
    Create an xarray mapping of loads to their respective zones.
    """
    load_zone_mapping = xr.DataArray(
        [loads.at[load, 'bus'] for load in loads.index],
        dims=["Load"],
        coords={"Load": loads.index}
    )
    return load_zone_mapping

def create_load_zone_mask(load_zone_mapping: xr.DataArray, zones: list) -> xr.DataArray:
    """
    Create a mask for the loads in the zones.
    """
    zone_da = xr.DataArray(zones, dims = ["Zone"], coords = {"Zone": zones})
    mask = zone_da == load_zone_mapping
    return mask

def get_zonal_loads(load_zone_mask, loads_t_pset):
    """
    Get the total loads per zone (xarray)
    """
    loads_xr = xr.DataArray(
        loads_t_pset.T,
        dims=["Load", "snapshot"],
        coords={"Load": loads_t_pset.columns, "snapshot": loads_t_pset.index}
    )
    return (loads_xr * load_zone_mask).sum(dim="Load")

# ---- Constraint Construction ----

def construct_cne_constraint(zPTDF: xr.DataArray, net_positions: lp.LinearExpression, RAM: xr.DataArray, upper_bool: True):
    """
    Create the constraint restricting the flow on cnecs by the Remaining Available Margin (RAM).
    
    This function handles both snapshot-dependent and static zPTDFs.
    
    Parameters
    ----------
    zPTDF : xr.DataArray
        Either a 2D DataArray with dimensions [cnec, Zone] for static zPTDF,
        or a 3D DataArray with dimensions [snapshot, cnec, Zone] for snapshot-dependent zPTDF.
    total_zonal_generation : lp.Variable
        Linopy variable for zonal generation with dimensions [Zone, snapshot].
    zonal_loads : xr.DataArray
        DataArray with zonal loads with dimensions [Zone, snapshot].
    RAM : xr.DataArray
        DataArray with RAM values with dimensions [cnec, snapshot].
        
    Returns
    -------
    lp.Constraint
        Constraint ensuring flows on cnecs are within the RAM.
    """
    # Check if zPTDF is snapshot-dependent
    snapshot_dependent = "snapshot" in zPTDF.dims
    
    # Get zones that are in both zPTDF and total_zonal_generation
    zones = [zone for zone in zPTDF.coords['Zone'].values if zone in net_positions.indexes['Zone']]
    net_positions = net_positions.sel(Zone=zones)
    # internal_zonal_loads = zonal_loads.sel(Zone=zones)
    
    # Handle snapshot-dependent and static zPTDFs differently
    if snapshot_dependent:
        # For snapshot-dependent zPTDF
        
        # Make sure snapshots are aligned
        snapshots = [snap for snap in zPTDF.coords['snapshot'].values if snap in RAM.coords['snapshot'].values]
        
        cne_lhs = (zPTDF * net_positions).sum(dim="Zone")
        # output dim: [snapshot, cnec]
        # Get corresponding RAM values
        ram_subset = RAM.sel(cnec=zPTDF.cnec, snapshot=snapshots).T
        
        # Create the constraint.
        if upper_bool:
            cne_constraint = cne_lhs <= ram_subset
        else:
            cne_constraint = cne_lhs >= ram_subset
    else:
        # For static zPTDF (original implementation)
        cne_lhs_list = []
        for cne in zPTDF.cnec.values:
            term = (zPTDF.sel(cnec=cne) * net_positions).sum(dim="Zone")
            cne_lhs_list.append(term)

        
        cne_lhs = lp.merge(cne_lhs_list, dim="cnec")
        cne_constraint = cne_lhs <= RAM
    
    return cne_constraint

def construct_zonal_balance_constraint(net_positions: lp.LinearExpression):
    """
    Get the zonal balance constraint.
    """

    return net_positions.sum(dim="Zone") == 0

