


import pypsa
import pandas as pd
from pathlib import Path
from src.paths import get_case_input_dir
from .network_conversion import copy_net, nodal_to_zonal

def _remove_buses_and_connected_components(net: pypsa.Network, buses_to_remove):
    # remove lines and transformers connected to the buses to remove
    lines_to_remove = net.lines.index[net.lines.bus0.isin(buses_to_remove) | net.lines.bus1.isin(buses_to_remove)]
    transformers_to_remove = net.transformers.index[net.transformers.bus0.isin(buses_to_remove) | net.transformers.bus1.isin(buses_to_remove)]
    generators_to_remove = net.generators.index[net.generators.bus.isin(buses_to_remove)]
    loads_to_remove = net.loads.index[net.loads.bus.isin(buses_to_remove)]
    storage_units_to_remove = net.storage_units.index[net.storage_units.bus.isin(buses_to_remove)]
    net.remove('StorageUnit', storage_units_to_remove)
    net.remove('Generator', generators_to_remove)
    net.remove('Load', loads_to_remove)
    net.remove('Line', lines_to_remove)
    net.remove('Transformer', transformers_to_remove)
    # remove the buses
    net.remove('Bus', buses_to_remove)


def _apply_unit_commitment_data(nodal_net: pypsa.Network) -> None:
    """Apply per-carrier unit-commitment parameters to nodal generators."""
    unit_commitment_path = Path(__file__).resolve().parent / "data" / "unit_commitment.csv"
    uc_df = pd.read_csv(unit_commitment_path, index_col="attribute")

    carrier_set = set(nodal_net.generators.carrier.astype(str))
    available_carriers = [carrier for carrier in uc_df.columns if carrier in carrier_set]
    if not available_carriers:
        return

    for carrier in available_carriers:
        generator_mask = nodal_net.generators.carrier.astype(str) == carrier
        if not generator_mask.any():
            continue

        # UC attributes only have an effect when committable is enabled.
        nodal_net.generators.loc[generator_mask, "committable"] = True

        for attribute, value in uc_df[carrier].items():
            nodal_net.generators.loc[generator_mask, attribute] = value


def create_pypsa_eur_ua_case(keep_countries=None, drop_countries=None):
    """Precedence: keep countries over drop countries.

    Args:
        keep_countries (_type_, optional): _description_. Defaults to None.
        drop_countries (_type_, optional): _description_. Defaults to None.

    Returns:
        _type_: _description_
    """
    case_name = "pypsa-eur-ua"
    case_dir = get_case_input_dir(case_name)
    nodal_net = pypsa.Network(case_dir / "nodal.nc")
    nodal_net = copy_net(
        nodal_net,
        time_dependent_attrs={
            'generators_t': ['p_max_pu'],
            'loads_t': ['p_set'],
            'storage_units_t': ['inflow']
        })  # since we used another pypsa version for creating the case, we need to copy the net to get it to the current version. 

    # if zonal exists, use it, otherwise create it from the nodal net
    _apply_unit_commitment_data(nodal_net)
    if (case_dir / "zonal.nc").exists():
        zonal_net = pypsa.Network(case_dir / "zonal.nc")
    else:
        zonal_net = nodal_to_zonal(nodal_net, bus_zone_map=nodal_net.buses.country)
    remove_countries_list = None
    if keep_countries is not None:
        remove_countries_list = list(set(nodal_net.buses.country.unique()).difference(set(keep_countries)))
    elif drop_countries is not None:
        remove_countries_list = drop_countries
    if remove_countries_list is not None:
        remove_buses = nodal_net.buses.index[nodal_net.buses.country.isin(remove_countries_list)]
        _remove_buses_and_connected_components(nodal_net, remove_buses)
        _remove_buses_and_connected_components(zonal_net, remove_countries_list)
    nodal_net.buses.loc[:, 'zone_name'] = nodal_net.buses.country
    zonal_net.remove('Line', zonal_net.lines.index)
    zonal_net.remove('Transformer', zonal_net.transformers.index)
    output = {
        'zonal_net': zonal_net,
        'nodal_net': nodal_net, 
    }
    return output