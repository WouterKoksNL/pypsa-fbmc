import pypsa
import pandas as pd

def create_pypsa_eur_central_northern_case(day=0, max_snapshots=24):
    case_name = "pypsa-eur_central_northern"
    case_dir = f"unprocessed_input_networks/{case_name}"
    nodal_net = pypsa.Network(f"{case_dir}/nodal.nc", ignore_standard_types=False)

    nodal_net.set_snapshots(nodal_net.snapshots[:max_snapshots])
    bus_zone_map = pd.read_csv(f"{case_dir}/bus_zone_map.csv", index_col=0)
    nodal_net.buses['zone_name'] = bus_zone_map.reindex(nodal_net.buses.index)
    zonal_net = pypsa.Network(f"{case_dir}/daily_zonal_network_day{day}.nc")
    zonal_net.set_snapshots(zonal_net.snapshots[:max_snapshots])
    # zonal_net.storage_units.loc[:, 'cyclic_state_of_charge'] = True

    # zonal_net = nodal_to_zonal(nodal_net, zone_column='zone_name')
    zonal_net.loads_t.p_set *= 0.1
    nodal_net.loads_t.p_set *= 0.1
    # nodal_net.remove('Link', nodal_net.links.index)
    
    output = {
        'zonal_net': zonal_net,
        'nodal_net': nodal_net, 
    }
    return output