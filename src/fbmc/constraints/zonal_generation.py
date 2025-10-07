import pandas as pd
import pypsa
import xarray as xr
import linopy as lp

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from linopy import merge
from xarray import DataArray
from pypsa.components.common import as_components
from pypsa.descriptors import get_switchable_as_dense as as_dense


if TYPE_CHECKING:
    from collections.abc import Sequence


def add_net_position_variable(network: pypsa.Network, zones: list, snapshots: list) -> lp.Variable: 
    """
    Add Zone-p (net position) variables for a given PyPSA network.
    
    Args:
        network (pypsa.Network): The PyPSA network object containing the model.
        zones (list): List of zone names.
        snapshots (list): List of timestamps for the analysis period.
    
    Returns:
        linopy.Variable: A variable with dimensions ("snapshot", "Zone") representing 
            the zonal generation for each snapshot and zone.
    """
    
    zonal_generation = network.model.add_variables(
        name="Zone-p",
        coords={"snapshot": snapshots, "Zone": zones},  
        dims=["snapshot", "Zone"],  
        )
    
    return zonal_generation


def define_net_positions_constraint(
    n: pypsa.Network,
    sns: pd.Index,
    buses: Sequence | None = None,
    suffix: str = "",
) -> None:
    """Define net positions based on PyPSA 0.35.0 nodal balance constraint at
    https://github.com/PyPSA/PyPSA/blob/f26ee3052107aaa20511a6de543c85c39897ca78/pypsa/optimization/constraints.py
    The NPs contain the effect of Generators, Loads, StorageUnits, Links.
    Links are included to model transport by HVDC lines following Standard Hybrid Coupling
    """
    m = n.model
    if buses is None:
        buses = n.buses.index

    args = [
        ["Generator", "p", "bus", 1],
        ["Store", "p", "bus", 1],
        ["StorageUnit", "p_dispatch", "bus", 1],
        ["StorageUnit", "p_store", "bus", -1],
        # ["Line", "s", "bus0", -1],
        # ["Line", "s", "bus1", 1],
        # ["Transformer", "s", "bus0", -1],
        # ["Transformer", "s", "bus1", 1],
        ["Link", "p", "bus0", -1],
        ["Link", "p", "bus1", as_dense(n, "Link", "efficiency", sns)],
    ]

    if not n.links.empty:
        for i in n.components.links.additional_ports:
            eff = as_dense(n, "Link", f"efficiency{i}", sns)
            args.append(["Link", "p", f"bus{i}", eff])


    exprs = []

    for arg in args:
        c, attr, column, sign = arg

        if n.static(c).empty:
            continue

        if "sign" in n.static(c):
            # additional sign necessary for branches in reverse direction
            sign = sign * n.static(c).sign

        expr = DataArray(sign) * m[f"{c}-{attr}"]
        cbuses = n.static(c)[column][lambda ds: ds.isin(buses)].rename("Bus")

        #  drop non-existent multiport buses which are ''
        if column in ["bus" + i for i in n.c.links.additional_ports]:
            cbuses = cbuses[cbuses != ""]

        expr = expr.sel({c: cbuses.index})

        if expr.size:
            exprs.append(expr.groupby(cbuses).sum())

    nodal_production = merge(exprs, join="outer").reindex(Bus=buses)
    active = n.loads.query("active").index
    fixed_load = (
        (-as_dense(n, "Load", "p_set", sns, active) * n.loads.sign[active])
        .T.groupby(n.loads.bus[active])
        .sum()
        .T.reindex(columns=buses, fill_value=0)
    )
    # the name for multi-index is getting lost by groupby before pandas 1.4.0
    # TODO remove once we bump the required pandas version to >= 1.4.0
    fixed_load.index.name = "snapshot"

    empty_nodal_balance = (zonal_production.vars == -1).all("_term")
    fixed_load = DataArray(fixed_load)
    if empty_nodal_balance.any():
        if (empty_nodal_balance & (fixed_load != 0)).any().item():
            msg = "Empty LHS with non-zero RHS in nodal balance constraint."
            raise ValueError(msg)

        mask = ~empty_nodal_balance
    else:
        mask = None

    if suffix:
        zonal_production = zonal_production.rename(Bus=f"Bus{suffix}")
        fixed_load = fixed_load.rename(Bus=f"Bus{suffix}")
        if mask is not None:
            mask = mask.rename(Bus=f"Bus{suffix}")
    zonal_production = zonal_production.rename({"Bus": "Zone"})
    fixed_load = fixed_load.rename({"Bus": "Zone"})
    n.model.add_constraints(n.model.variables['Zone-p'] - (lhs - fixed_load), "=", 0, name=f"Zone{suffix}-definition", mask=mask)
    n.model.add_constraints(n.model.variables['Zone-p'] - (zonal_production - fixed_load), "=", 0, name=f"Zone{suffix}-definition", mask=mask)

