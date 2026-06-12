import numpy as np
import pypsa

from fbmc.core.input_network_conversions.network_conversion import nodal_to_zonal, nodal_to_zonal_nocopy, copy_net




def create_scigrid_case():
    scigrid = pypsa.examples.scigrid_de()

    time_dependent_attrs = {
        'generators_t': ['p_max_pu'],
        'loads_t': ['p_set'],
        'storage_units_t': ['state_of_charge'],
    }
    nodal_net = copy_net(scigrid, time_dependent_attrs=time_dependent_attrs)

    nodal_net.set_snapshots(nodal_net.snapshots[:1])
    # net.remove('StorageUnit', net.storage_units.index)
    # nodal_net.add('Generator', 'load_shedding_' + nodal_net.buses.index, bus=nodal_net.buses.index, p_nom=10000, marginal_cost=1000, carrier="load_shedding")
    nodal_net.lines.s_nom *= 1.3
    quadrant1 = (nodal_net.buses.y > 51) & (nodal_net.buses.x > 9)
    quadrant2 = (nodal_net.buses.y > 51) & (nodal_net.buses.x < 9)
    quadrant3 = (nodal_net.buses.y < 51) & (nodal_net.buses.x < 9)
    quadrant4 = (nodal_net.buses.y < 51) & (nodal_net.buses.x > 9)

    # find buses in each quadrant
    buses_q1 = nodal_net.buses[quadrant1]
    buses_q2 = nodal_net.buses[quadrant2]
    buses_q3 = nodal_net.buses[quadrant3]
    buses_q4 = nodal_net.buses[quadrant4]

    nodal_net.buses.loc[buses_q1.index, 'zone_name'] = 'Z1'
    nodal_net.buses.loc[buses_q2.index, 'zone_name'] = 'Z2'
    nodal_net.buses.loc[buses_q3.index, 'zone_name'] = 'Z3'
    nodal_net.buses.loc[buses_q4.index, 'zone_name'] = 'Z4'
    # net.remove('StorageUnit', net.storage_units.index)

    nodal_net.loads_t.p_set *= 0.5
    nodal_net.transformers.index = 'T' + nodal_net.transformers.index
    zonal_net = nodal_to_zonal(nodal_net, bus_zone_map=nodal_net.buses.zone_name)

    # zonal_net.remove('Link', zonal_net.links.index)
    output = {
        'zonal_net': zonal_net,
        'nodal_net': nodal_net, 
    }

    return output