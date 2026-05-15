
import pypsa

from .network_conversion import nodal_to_zonal

def create_linear_case(**kwargs):
    nodal_net = pypsa.Network()
    nodal_net.set_snapshots(range(2))
    nodal_net.add("Bus", ['1A', '1B', '1C', '2D', '2E', '2F'])
    nodal_net.add("Line", '1A-1B', bus0='1A', bus1='1B', x=1, s_nom=1)
    nodal_net.add("Line", '1B-1C', bus0='1B', bus1='1C', x=1, s_nom=1)
    nodal_net.add("Line", '1C-1A', bus0='1C', bus1='1A', x=1, s_nom=1)
    nodal_net.add("Line", '2D-1C', bus0='2D', bus1='1C', x=1, s_nom=10)
    nodal_net.add("Line", '2E-2F', bus0='2E', bus1='2F', x=1, s_nom=1)
    nodal_net.add("Line", '2F-2D', bus0='2F', bus1='2D', x=1, s_nom=1)

    nodal_net.add("Load", 'load_1C', bus='1C', p_set=[10, 10])
    nodal_net.add("Generator", 'gen_1A', bus='1A', p_nom=10, marginal_cost=1)
    nodal_net.add("Generator", 'gen_1C', bus='1C', p_nom=10, marginal_cost=5)
    nodal_net.add("Generator", 'gen_2D', bus='2D', p_nom=10, marginal_cost=10)

    nodal_net.buses.loc[:, 'zone_name'] = ['1', '1', '1', '2', '2', '2']
    zonal_net = nodal_to_zonal(nodal_net.copy(), nodal_net.buses.zone_name)

    output = {
        'zonal_net': zonal_net,
        'nodal_net': nodal_net, 
    }

    return output
