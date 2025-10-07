import pandas as pd
import pypsa
import xarray as xr
import linopy as lp

def create_generator_zone_mapping(generators: pd.DataFrame) -> xr.DataArray:
    """
    Create an xarray mapping of generators to their respective zones.
    
    Args:
        generators (pd.DataFrame): DataFrame containing generator data with 'bus' column
            indicating the zone (assuming zonal network)
    
    Returns:
        xarray.DataArray: A 1D array with dimension "Generator" mapping generators to zones.
    """
    generator_zone_mapping = xr.DataArray(
        [generators.at[gen, 'bus'] for gen in generators.index],
        dims=["Generator"],
        coords={"Generator": generators.index}
    )
    return generator_zone_mapping


def create_signed_generator_mask(generator_zone_mapping: xr.DataArray, 
                               zones: list, 
                               gen_sign: xr.DataArray) -> xr.DataArray:
    """
    Create a signed mask for generators based on their zones and signs.
    
    Args:
        generator_zone_mapping (xarray.DataArray): Mapping of generators to zones.
        zones (list): List of zone names.
        gen_sign (xarray.DataArray): Array containing the sign of each generator.
    
    Returns:
        xarray.DataArray: A 2D array with dimensions ("Generator", "Zone") containing
            signed binary values indicating generator-zone assignments.
    """
    zone_da = xr.DataArray(zones, dims=["Zone"], coords={"Zone": zones})
    signed_mask = (generator_zone_mapping == zone_da) * gen_sign
    return signed_mask

def add_zonal_generation_variable(network: pypsa.Network, zones: list, snapshots: list) -> lp.Variable: 
    """
    Add zonal generation variables for a given PyPSA network.
    
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
        coords={"snapshot": snapshots, "Zone": zones},  # Changed order
        dims=["snapshot", "Zone"],  # Changed order and capitalization
        )
    
    return zonal_generation

def construct_zonal_generation_constraint(total_zonal_generation: lp.Variable, generators: lp.Variable, signed_mask: xr.DataArray) -> lp.Constraint:
    """
    Create constraints to define zonal generation as the sum of signed generator outputs.
    """

    zonal_generation_constraint = total_zonal_generation == (generators * signed_mask).sum(dim="Generator")
    return zonal_generation_constraint



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

    empty_nodal_balance = (nodal_production.vars == -1).all("_term")
    fixed_load = DataArray(fixed_load)
    if empty_nodal_balance.any():
        if (empty_nodal_balance & (fixed_load != 0)).any().item():
            msg = "Empty LHS with non-zero RHS in nodal balance constraint."
            raise ValueError(msg)

        mask = ~empty_nodal_balance
    else:
        mask = None

    if suffix:
        lhs = lhs.rename(Bus=f"Bus{suffix}")
        fixed_load = fixed_load.rename(Bus=f"Bus{suffix}")
        if mask is not None:
            mask = mask.rename(Bus=f"Bus{suffix}")
    lhs = lhs.rename({"Bus": "Zone"})
    fixed_load = fixed_load.rename({"Bus": "Zone"})
    n.model.add_constraints(n.model.variables['Zone-p'] - (lhs - fixed_load), "=", 0, name=f"Zone{suffix}-definition", mask=mask)

