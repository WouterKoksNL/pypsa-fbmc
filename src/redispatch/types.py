
import pandas as pd
import xarray as xr
import pypsa
from dataclasses import dataclass


@dataclass 
class ReferenceDispatch:
    generators_p: pd.DataFrame
    storage_units_p: pd.DataFrame | None
    storage_levels: pd.DataFrame | None
    water_values: xr.DataArray | None
    links_p0: pd.DataFrame | None



    
@dataclass
class RedispatchResult:
    nodal_net: pypsa.Network
    cost: float
    dispatch_results: ReferenceDispatch
