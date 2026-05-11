import pandas as pd
import numpy as np
import xarray as xr
from typing import Any
from dataclasses import dataclass
import pypsa

class SubnetFBMCParameters:
    def __init__(
        self,
        z_ptdf_dict: dict[Any, pd.DataFrame],
        upper_ram_dict: dict[Any, pd.DataFrame],
        lower_ram_dict: dict[Any, pd.DataFrame],
        cnecs: pd.Series | pd.MultiIndex,
        zones: pd.Index,
        link_ptdf_bus0: pd.DataFrame | None = None,
        link_ptdf_bus1: pd.DataFrame | None = None,
    ):
        self.z_ptdf: dict[Any, pd.DataFrame] | xr.DataArray = z_ptdf_dict
        self.upper_ram: dict[Any, pd.DataFrame] | xr.DataArray = upper_ram_dict
        self.lower_ram: dict[Any, pd.DataFrame] | xr.DataArray = lower_ram_dict
        self.cnecs: pd.Series | pd.MultiIndex = cnecs
        self.zones: pd.Index = zones
        self.link_ptdf_bus0: pd.DataFrame | None = link_ptdf_bus0
        self.link_ptdf_bus1: pd.DataFrame | None = link_ptdf_bus1

    def convert_to_xr(self):
        """Convert all dict attributes to xarray DataArrays."""
        self.z_ptdf = self._zptdf_to_xarray(self.z_ptdf)
        self.upper_ram = self._ram_dict_to_xarray(self.upper_ram, name="upper_RAM")
        self.lower_ram = self._ram_dict_to_xarray(self.lower_ram, name="lower_RAM")
        if self.link_ptdf_bus0 is not None:
            self.link_ptdf_bus0 = self._convert_link_ptdf_to_xarray(self.link_ptdf_bus0)
        if self.link_ptdf_bus1 is not None:
            self.link_ptdf_bus1 = self._convert_link_ptdf_to_xarray(self.link_ptdf_bus1)

    # ---- zPTDF conversion ----
    def z_ptdf_xr(self) -> xr.DataArray:
        """Convert zonal PTDF data (dict or DataFrame) to a DataArray."""
        return self._convert_zptdf_to_xarray(self.z_ptdf)

    # ---- internal helper methods ----
    @staticmethod
    def _ram_dict_to_xarray(ram_dict: dict[Any, pd.DataFrame], name: str) -> xr.DataArray:
        """
        Combine per-snapshot RAM DataFrames into one DataArray.
        """
        snapshots = list(ram_dict.keys())
        cnecs = ram_dict[snapshots[0]].index
        data = np.stack([ram_dict[s].values for s in snapshots])
        return xr.DataArray(
            data,
            dims=["snapshot", "cnec"],
            coords={"snapshot": snapshots, "cnec": cnecs},
            name=name,
        )


    def _convert_link_ptdf_to_xarray(self, link_ptdf: pd.DataFrame) -> xr.DataArray:
        """
        Convert link PTDF DataFrame to a DataArray.
        """
        return xr.DataArray(
            link_ptdf.values,
            dims=["cnec", "Link"],
            coords={"cnec": link_ptdf.index, "Link": link_ptdf.columns},
            name="link_PTDF",
        )

    @staticmethod
    def _zptdf_to_xarray(zptdf_data: dict | pd.DataFrame) -> xr.DataArray:
        """
        Convert zPTDF data (dict or DataFrame) to a DataArray.
        """
        if isinstance(zptdf_data, dict):
            snapshots = list(zptdf_data.keys())
            cnes = zptdf_data[snapshots[0]].index
            zones = zptdf_data[snapshots[0]].columns
            data_array = np.stack([zptdf_data[s].values for s in snapshots])
            return xr.DataArray(
                data_array,
                dims=["snapshot", "cnec", "Zone"],
                coords={"snapshot": snapshots, "cnec": cnes, "Zone": zones},
                name="zPTDF",
            )
        else:
            return xr.DataArray(
                zptdf_data.values,
                dims=["cnec", "Zone"],
                coords={"cnec": zptdf_data.index, "Zone": zptdf_data.columns},
                name="zPTDF",
            )

@dataclass
class DispatchResults:
    generators_p: pd.DataFrame
    storage_units_p: pd.DataFrame
    links_p0: pd.DataFrame

    def __init__(self, nodal_net: pypsa.Network):
        self.generators_p = nodal_net.generators_t.p
        self.storage_units_p = nodal_net.storage_units_t.p
        self.links_p0 = nodal_net.links_t.p0


