import pypsa
import pandas as pd
from fbmc.input_network_conversions.network_conversion import copy_net, nodal_to_zonal
from fbmc.paths import get_unprocessed_input_networks_dir


def create_pypsa_eur_central_northern_case(day=0, max_snapshots=24):
    case_name = "pypsa-eur_central_northern"
    case_dir = get_unprocessed_input_networks_dir() / case_name
    nodal_net_unprocessed = pypsa.Network(case_dir / "nodal.nc", ignore_standard_types=False)
    nodal_net = copy_net(nodal_net_unprocessed, time_dependent_attrs={
        'generators_t': ['p_max_pu', 'p'],
        'loads_t': ['p_set'],
        'storage_units_t': ['p'],
        'links_t': ['p0'],
        'buses_t': ['p'],
        'lines_t': ['p0'],
        'transformers_t': ['p0'],
        })
    nodal_net.set_snapshots(nodal_net.snapshots[:max_snapshots])
    bus_zone_map = pd.read_csv(case_dir / "bus_zone_map.csv", index_col=0)
    nodal_net.buses['zone_name'] = bus_zone_map.reindex(nodal_net.buses.index)
    zonal_net = nodal_to_zonal(nodal_net, bus_zone_map=nodal_net.buses.zone_name, add_ntc_flag=False)
    # zonal_net_unprocessed = pypsa.Network(f"{case_dir}/daily_zonal_network_day{day}.nc")
    # breakpoint()
    # zonal_net = copy_net(zonal_net_unprocessed, time_dependent_attrs={
    #     'generators_t': ['p_max_pu'],
    #     'loads_t': ['p_set'],
    #     'storage_units_t': ['inflow'],
    #     })
    zonal_net.set_snapshots(zonal_net.snapshots[:max_snapshots])

    zonal_net.loads_t.p_set *= 0.5
    nodal_net.loads_t.p_set *= 0.5
    
    output = {
        'zonal_net': zonal_net,
        'nodal_net': nodal_net, 
    }
    return output