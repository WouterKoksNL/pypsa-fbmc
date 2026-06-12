
import pypsa
import pandas as pd

from fbmc.input_network_conversions.network_conversion import nodal_to_zonal 

def create_advanced_hybrid_check(
        variation='C-to-out'
):
    nodal_net = pypsa.Network()
    nodal_net.set_snapshots(['1'])
    load = 10
    buses = ['A', 'B', 'C', 'D', 'out']

    bus_zone_map = {
        'A': 'zone1',
        'B': 'zone2',
        'C': 'zone2',
        'D': 'zone2',
        'out': 'zone3',
    }
    nodal_net.add('Bus', buses, zone_name=[bus_zone_map[bus] for bus in buses])

    nodal_net.add('Link', 'A-B', bus0='A', bus1='B', p_nom=10)
    nodal_net.add('Line', 'B-C', bus0='B', bus1='C', x=1, s_nom=4)
    nodal_net.add('Line', 'C-D', bus0='C', bus1='D', x=1, s_nom=4)
    nodal_net.add('Line', 'B-D', bus0='B', bus1='D', x=1, s_nom=4)
    if variation == 'C-to-out':
        nodal_net.add('Line', 'C-out', bus0='C', bus1='out', x=1, s_nom=10)
    elif variation == 'B-to-out':
        nodal_net.add('Line', 'B-out', bus0='B', bus1='out', x=1, s_nom=10)
    else:
        raise ValueError("Invalid variation specified. Use 'C-to-out' or 'B-to-out'.")
    nodal_net.add('Generator', 'gen_A', bus='A', p_nom=10, marginal_cost=1, carrier="X")
    nodal_net.add('Generator', 'gen_C', bus='C', p_nom=10, marginal_cost=10, carrier="X")
    nodal_net.add('Generator', 'gen_out', bus='out', p_nom=10, marginal_cost=30, carrier="X")

    nodal_net.add('Load', 'load_out', bus='out', p_set=load)

    zonal_net = nodal_to_zonal(nodal_net.copy(), bus_zone_map=nodal_net.buses.zone_name)

    gsk = pd.DataFrame(0., index=zonal_net.buses.index.copy(), columns=nodal_net.buses.index)
    gsk.loc['zone1', 'A'] = 1.
    gsk.loc['zone2', 'C'] = 1.
    gsk.loc['zone3', 'out'] = 1.

    gsk.columns.name = "Bus"
    gsk.index.name = "Zone"
    gsk_dict = {snapshot: gsk.copy()
        for snapshot in zonal_net.snapshots}
    output = {
        'zonal_net': zonal_net,
        'nodal_net': nodal_net,
        'gsk_dict': gsk_dict
    }
    return output