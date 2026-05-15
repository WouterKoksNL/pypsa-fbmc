from PyPSA import pypsa
import pandas as pd

from .network_conversion import nodal_to_zonal 

def create_four_node():
    nodal_net = pypsa.Network()
    nodal_net.set_snapshots(['1'])
    load = 10
    buses = ['A', 'B', 'C', 'D']
    # bus_zone_map = {
    #     'A': 'zone1',
    #     'B': 'zone1',
    #     'C': 'zone2',
    #     'D': 'zone1',
    # }
    bus_zone_map = {
        'A': 'zone1',
        'B': 'zone1',
        'C': 'zone2',
        'D': 'zone2',
    }
    nodal_net.add('Bus', buses, zone_name=[bus_zone_map[bus] for bus in buses])

    nodal_net.add('Line', 'A-B', bus0='A', bus1='B', x=1, s_nom=4)
    nodal_net.add('Line', 'B-C', bus0='B', bus1='C', x=1, s_nom=10)
    nodal_net.add('Line', 'C-D', bus0='C', bus1='D', x=1, s_nom=10)
    nodal_net.add('Line', 'A-D', bus0='A', bus1='D', x=1, s_nom=10)
    nodal_net.add('Line', 'A-C', bus0='A', bus1='C', x=1, s_nom=10)

    nodal_net.add('Generator', 'gen_B', bus='B', p_nom=10, marginal_cost=30, carrier="X")
    nodal_net.add('Generator', 'gen_D', bus='D', p_nom=10, marginal_cost=20, carrier="X")
    nodal_net.add('Generator', 'gen_C', bus='C', p_nom=10, marginal_cost=10, carrier="X")

    nodal_net.add('Load', 'load_A', bus='A', p_set=load)

    zonal_net = nodal_to_zonal(nodal_net.copy(), bus_zone_map=nodal_net.buses.zone_name)

    gsk = pd.DataFrame(0., index=zonal_net.buses.index.copy(), columns=nodal_net.buses.index)
    gsk.loc['zone2', 'C'] = 1.
    gsk.loc['zone1', 'D'] = 1.

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