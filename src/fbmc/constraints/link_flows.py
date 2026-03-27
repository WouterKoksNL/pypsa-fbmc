import linopy as lp
import pandas as pd
import xarray as xr
import numpy as np



def construct_cne_constraint_advanced_hybrid(
        zPTDF: xr.DataArray, 
        net_positions: lp.LinearExpression, 
        ram: xr.DataArray, 
        upper_bool: bool,
        advanced_hybrid_flag: bool,
        link_flows: lp.LinearExpression,
        link_ptdf_bus0: xr.DataArray,
        link_ptdf_bus1: xr.DataArray,
        ):
    """
    Create the constraint restricting the flow on CNECs by the Remaining Available Margin (RAM).
    
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
    lhs = (zPTDF * net_positions).sum(dim="Zone") 
    if link_flows is not None:
        lhs += ((link_ptdf_bus1 - link_ptdf_bus0) * link_flows).sum(dim="Link")
    # Create the constraint.
    if upper_bool:
        cne_constraint = lhs <= ram
    else:
        cne_constraint = lhs >= ram

    return cne_constraint