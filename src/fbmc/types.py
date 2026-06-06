import pandas as pd
import numpy as np
import xarray as xr
from typing import Any
from dataclasses import dataclass
import pypsa


def _shape_summary(obj: pd.DataFrame | xr.DataArray | dict[Any, pd.DataFrame] | None) -> str:
    if obj is None:
        return "None"
    if isinstance(obj, pd.DataFrame):
        return f"DataFrame{obj.shape}"
    if isinstance(obj, xr.DataArray):
        return f"DataArray{obj.shape}"
    if isinstance(obj, dict):
        n_snapshots = len(obj)
        if n_snapshots == 0:
            return "dict(0 snapshots)"
        first_df = next(iter(obj.values()))
        return f"dict({n_snapshots} snapshots, frame_shape={first_df.shape})"
    return type(obj).__name__


def _network_summary(net: pypsa.Network) -> str:
    name = net.name or "Unnamed Network"
    component_attrs = [
        ("buses", "Bus"),
        ("generators", "Generator"),
        ("loads", "Load"),
        ("lines", "Line"),
        ("links", "Link"),
        ("storage_units", "StorageUnit"),
        ("stores", "Store"),
        ("transformers", "Transformer"),
        ("sub_networks", "SubNetwork"),
    ]
    parts: list[str] = []
    for attr_name, label in component_attrs:
        if hasattr(net, attr_name):
            count = len(getattr(net, attr_name))
            if count > 0:
                parts.append(f"{label}:{count}")

    snapshots = len(net.snapshots) if hasattr(net, "snapshots") else "?"
    components = ", ".join(parts) if parts else "none"
    return f"{name} | snapshots={snapshots} | components=[{components}]"

class SubnetFBMCParameters:
    def __init__(
        self,
        z_ptdf_dict: dict[Any, pd.DataFrame],
        upper_ram_dict: dict[Any, pd.DataFrame],
        lower_ram_dict: dict[Any, pd.DataFrame],
        cnecs: pd.Series | pd.MultiIndex,
        zones: pd.Index,
    ):
        self.z_ptdf: dict[Any, pd.DataFrame] | xr.DataArray = z_ptdf_dict
        self.upper_ram: dict[Any, pd.DataFrame] | xr.DataArray = upper_ram_dict
        self.lower_ram: dict[Any, pd.DataFrame] | xr.DataArray = lower_ram_dict
        self.cnecs: pd.Series | pd.MultiIndex = cnecs
        self.zones: pd.Index = zones

    def __repr__(self) -> str:
        return (
            "SubnetFBMCParameters("
            f"z_ptdf={_shape_summary(self.z_ptdf)}, "
            f"upper_ram={_shape_summary(self.upper_ram)}, "
            f"lower_ram={_shape_summary(self.lower_ram)}, "
            f"cnecs={len(self.cnecs)}, "
            f"zones={len(self.zones)}, "
            ")"
        )

    __str__ = __repr__

    def convert_to_xr(self):
        """Convert all dict attributes to xarray DataArrays."""
        self.z_ptdf = self._zptdf_to_xarray(self.z_ptdf)
        if not isinstance(self.upper_ram, xr.DataArray):
            self.upper_ram = self._ram_dict_to_xarray(self.upper_ram, name="upper_RAM")
            self.lower_ram = self._ram_dict_to_xarray(self.lower_ram, name="lower_RAM")

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
        if isinstance(zptdf_data, xr.DataArray):
            return zptdf_data
        elif isinstance(zptdf_data, dict):
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


class DispatchResult:
    def __init__(self, net: pypsa.Network):
        self.generators_p: pd.DataFrame = net.generators_t.p
        self.storage_units_p: pd.DataFrame = net.storage_units_t.p

        self.links_p0: pd.DataFrame = net.links_t.p0
        self.storage_levels: pd.DataFrame | None = None
        self.water_values: xr.DataArray | None = None
        if not net.storage_units.empty:
            self.storage_levels = net.storage_units_t.state_of_charge
            if "StorageUnit-energy_balance" in net.model.dual: # needs seperate check as dual is not returned in case the problem is a MILP
                self.water_values: xr.DataArray = net.model.dual["StorageUnit-energy_balance"]

    def __repr__(self) -> str:
        return (
            "DispatchResult object with attrs: "
            f"\n  generators_p: {self.generators_p.shape} snapshots x generators, "
            f"\n  storage_units_p: {self.storage_units_p.shape} snapshots x storage units, "
            f"\n  links_p0: {self.links_p0.shape} snapshots x links, "
            f"\n  storage_levels: {self.storage_levels.shape if self.storage_levels is not None else None} snapshots x storage levels, "
            f"\n  water_values: {self.water_values.shape if self.water_values is not None else None} snapshots x water values"
        )

    __str__ = __repr__



@dataclass
class FBMCResult:
    zonal_net: pypsa.Network
    net_positions: pd.DataFrame
    dispatch_results: DispatchResult
    fbmc_parameters: dict[str, "SubnetFBMCParameters"]
    base_case: pypsa.Network

    def __str__(self) -> str:
        subnet_keys = list(self.fbmc_parameters.keys())
        key_preview = ", ".join(map(str, subnet_keys[:5]))
        if len(subnet_keys) > 5:
            key_preview += ", ..."

        return (
            "FBMCResult\n"
            f"  zonal_net: {_network_summary(self.zonal_net)}\n"
            f"  base_case: {_network_summary(self.base_case)}\n"
            f"  net_positions: DataFrame{self.net_positions.shape}\n"
            f"  dispatch_results: {self.dispatch_results}\n"
            f"  fbmc_parameters: {len(self.fbmc_parameters)} subnet(s) [{key_preview}]"
        )

    __repr__ = __str__

@dataclass
class RedispatchResult:
    nodal_net: pypsa.Network
    cost: float
    dispatch_results: DispatchResult