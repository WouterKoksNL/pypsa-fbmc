from PyPSA import pypsa
import pandas as pd

from .network_conversion import nodal_to_zonal  

def create_double_three_node_link_case():
    nodal_net = pypsa.Network()
    nodal_net.set_snapshots(['1'])
    loads = {1: 15, 2: 20}
    # loads = {1: 15, 2: 22}
    for sn in [1, 2]:
        buses_sn = [f'S{sn}A1', f'S{sn}B1', f'S{sn}B2']
        nodal_net.add('Bus', buses_sn, zone_name=[f'S{sn}A', f'S{sn}B', f'S{sn}B'])
        # nodal_net.buses.loc[buses_sn, 'zone_name'] = [f'S{sn}A', f'S{sn}B', f'S{sn}B']
        nodal_net.add('Line', f'S{sn}B1-S{sn}A1', bus0=f'S{sn}B1', bus1=f'S{sn}A1', x=1, s_nom=12)
        nodal_net.add('Line', f'S{sn}B1-S{sn}B2', bus0=f'S{sn}B1', bus1=f'S{sn}B2', x=1, s_nom=12)
        nodal_net.add('Line', f'S{sn}A1-S{sn}B2', bus0=f'S{sn}A1', bus1=f'S{sn}B2', x=1, s_nom=12)

        nodal_net.add('Generator', f'gen_S{sn}A1', bus=f'S{sn}A1', p_nom=12, marginal_cost=400, carrier="Wind")
        nodal_net.add('Generator', f'gen_S{sn}B1', bus=f'S{sn}B1', p_nom=12, marginal_cost=100, carrier="CCGT")
        nodal_net.add('Generator', f'gen_S{sn}B2', bus=f'S{sn}B2', p_nom=12, marginal_cost=200, carrier="Oil")
        nodal_net.add('Load', f'load_S{sn}A1', bus=f'S{sn}A1', p_set=loads[sn])
 
    nodal_net.add('Link', 'S1B2_S2B1', bus0='S1B2', bus1='S2B1', p_min_pu=-1, p_nom=5)
    # nodal_net.add('Link', 'S1B1_S2B1', bus0='S1B1', bus1='S2B1', p_min_pu=-1, p_nom=3)
    zonal_net = nodal_to_zonal(nodal_net.copy(), bus_zone_map=nodal_net.buses.zone_name)

    # nodal_net.optimize(solver_name='gurobi')
    gsk = pd.DataFrame(0., index=zonal_net.buses.index.copy(), columns=nodal_net.buses.index)
    for sn in [1, 2]:
        gsk.loc[f'S{sn}A', f'S{sn}A1'] = 1.0
        gsk.loc[f'S{sn}B', f'S{sn}B1'] = 0.8
        gsk.loc[f'S{sn}B', f'S{sn}B2'] = 0.2
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