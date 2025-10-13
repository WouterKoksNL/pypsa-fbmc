import pypsa
import numpy as np
import pandas as pd

from src.fbmc.config import FBMCConfig, GSKMethod
from src.fbmc.pos_neg_method import setup_pos_neg_fbmc_model
from src.fbmc.main import run_fbmc 
from src.fbmc.network_conversion import nodal_to_zonal
from src.fbmc.market_prices import calculate_zonal_prices



def pre_process(net: pypsa.Network):
    net.remove('Line', net.lines.index[net.lines.s_nom < 1e-5])
    net.remove('Transformer', net.transformers.index[net.transformers.s_nom < 1e-5])
    net.remove('Link', net.links.index[net.links.p_nom < 1e-5])

def main(pos_neg_method, gsk_method, snapshot_length=3):
    if False:
        n_rd = pypsa.Network()
        
        rng = np.random.default_rng(42)
        
        n_rd.set_snapshots(np.arange(snapshot_length))
        uni = rng.uniform(0, 25, size=n_rd.snapshots.size)
        uni2 = rng.uniform(0, 10, size=n_rd.snapshots.size)
        uni3 = rng.uniform(12, 20, size=n_rd.snapshots.size)
        uni4 = rng.uniform(0, 10, size=n_rd.snapshots.size)
        uni_load = rng.uniform(0, 25, size=n_rd.snapshots.size)
        n_rd.add('Bus', ['Bus_1', 'Bus_2', 'Bus_3', 'Bus_4'])
        n_rd.buses.loc[:, 'zone_name'] = ['Zone_A', 'Zone_A', 'Zone_B', 'Zone_C']
        n_rd.add('Line', 'Line_1', bus0='Bus_1', bus1='Bus_2', x=0.1, s_nom=10)
        n_rd.add('Line', 'Line_2', bus0='Bus_2', bus1='Bus_3', x=0.1, s_nom=5/11)
        n_rd.add('Line', 'Line_3', bus0='Bus_3', bus1='Bus_4', x=0.1, s_nom=8) # may change
        n_rd.add('Line', 'Line_4', bus0='Bus_4', bus1='Bus_1', x=0.1, s_nom=8)
        n_rd.add('Line', 'Line_5', bus0='Bus_4', bus1='Bus_2', x=0.1, s_nom=10)
        # n_rd.add('Transformer', 'Transformer_1', bus0='Bus_1', bus1='Bus_2', x=0.1, s_nom=10)
        n_rd.add('Load', 'Load_Bus_4', bus='Bus_4', p_set=uni_load)
        n_rd.add('Generator', 'Gen_Bus_1', bus='Bus_1', p_nom=11, marginal_cost=uni, carrier="hydropower")
        n_rd.add('Generator', 'Gen_Bus_2', bus='Bus_2', p_nom=11, marginal_cost=uni2, carrier="hydropower")
        n_rd.add('Generator', 'Gen_Bus_3', bus='Bus_3', p_nom=11, marginal_cost=uni, carrier="hydropower")
        n_rd.add('Generator', 'Gen_Bus_4', bus='Bus_4', p_nom=11, marginal_cost=uni4, carrier="hydropower")
        z_da = nodal_to_zonal(n_rd, zone_column='zone_name')
        z_da.loads_t.p_set.loc[:, 'Load_Bus_4'] = uni3
    elif False:
        net = pypsa.Network('input_networks/scigrid_de.nc')
        net.set_snapshots(net.snapshots[:2])
        # net.remove('StorageUnit', net.storage_units.index)
        # net.add('Generator', 'load_shedding_' + net.buses.index, bus=net.buses.index, p_nom=1000, marginal_cost=1000, carrier="load_shedding")
        net.lines.s_nom *= 1.3
        quadrant1 = (net.buses.y > 51) & (net.buses.x > 9)
        quadrant2 = (net.buses.y > 51) & (net.buses.x < 9)
        quadrant3 = (net.buses.y < 51) & (net.buses.x < 9)
        quadrant4 = (net.buses.y < 51) & (net.buses.x > 9)

        # find buses in each quadrant
        buses_q1 = net.buses[quadrant1]
        buses_q2 = net.buses[quadrant2]
        buses_q3 = net.buses[quadrant3]
        buses_q4 = net.buses[quadrant4]

        net.buses.loc[buses_q1.index, 'zone_name'] = 'Z1'
        net.buses.loc[buses_q2.index, 'zone_name'] = 'Z2'
        net.buses.loc[buses_q3.index, 'zone_name'] = 'Z3'
        net.buses.loc[buses_q4.index, 'zone_name'] = 'Z4'
        net.remove('StorageUnit', net.storage_units.index)
        n_rd = net

        net.transformers.index = 'T' + net.transformers.index
        z_da = nodal_to_zonal(net)


        # define an rng
        if False:
            rng = np.random.default_rng(42)
            # scale the loads
            load_std = 0.01
            z_da.loads_t.p_set = z_da.loads_t.p_set * rng.normal(1, load_std, size=z_da.loads_t.p_set.shape)
            total_load_std = np.sqrt((load_std ** 2 * z_da.loads_t.p_set.mean() ** 2).mean())
            st_devs = {'Wind Onshore': 0.02, 'Wind Offshore': 0.02, 'Solar': 0.01}
            total_carrier_std = {}
            for carrier, std in st_devs.items():
                generators_carrier_index = z_da.generators[z_da.generators.carrier == carrier].index
                z_da.generators_t.p_max_pu.loc[:, generators_carrier_index] = np.clip(
                    z_da.generators_t.p_max_pu.loc[:, generators_carrier_index] * rng.normal(1, std, size=z_da.generators_t.p_max_pu.loc[:, generators_carrier_index].shape),
                    0, 1
                )
                total_carrier_std[carrier] = np.sqrt((std ** 2) * ((z_da.generators.p_nom.loc[generators_carrier_index] * z_da.generators_t.p_max_pu.loc[:, generators_carrier_index].mean()) ** 2).mean())
            # st_devs = z_da.loads_t.p_set.T.groupby(z_da.loads.bus).sum().T * load_std
            total_std = np.sqrt(total_load_std ** 2 + sum(v ** 2 for v in total_carrier_std.values()))
            print('total load std:', total_load_std)
            print('total carrier std:', total_carrier_std)
            print('total std:', total_std)
    elif False:
        n_rd = pypsa.Network()
        z_da = pypsa.Network()
        # Get the networks from files:
        folder = "input_networks"
        n_rd.import_from_netcdf(f"{folder}/nodal.nc")
        z_da.import_from_netcdf(f"{folder}/zonal.nc")
        n_rd.lines.s_nom *= 1
        z_da.remove('Bus', 'NO3')
        z_da.generators.loc[z_da.generators.bus == 'NO3', 'bus'] = 'NO2'
        z_da.remove('Load', 'load_3')
        z_da.remove('Link', z_da.links.index)
        z_da.add('Link', 'NO1_NO2', bus0='NO1', bus1='NO2', p_min_pu=-1, p_nom=300)
        # z_da.loads_t.p_set = z_da.loads_t.p_set * 0.7
    elif False:
    # snapshots are wrongly aligned!
        case_name = "pypsa-eur_central_northern"
        n_rd = pypsa.Network(f"input_networks/{case_name}/nodal.nc", ignore_standard_types=False)

        n_rd.set_snapshots(n_rd.snapshots[:24*3])
        bus_zone_map = pd.read_csv("C:/Users/wouterko/GitHub/pypsa-eur-market-zonal-optimization/bus_zone_map.csv", index_col=0)
        # pypsa.components.component_attrs['Bus'].loc['zone_name', ['type', 'unit', 'default']] = ['str', '', '']
        n_rd.buses['zone_name'] = bus_zone_map.reindex(n_rd.buses.index)
    
        # z_da = pypsa.Network(f"input_networks/{case_name}/zonal.nc", ignore_standard_types=False)
        z_da = pypsa.Network(f"input_networks/{case_name}/daily_zonal_network_day0.nc")
        z_da.set_snapshots(z_da.snapshots[:24*3])
        z_da.storage_units.loc[:, 'cyclic_state_of_charge'] = True
        # z_da = nodal_to_zonal(n_rd, zone_column='zone_name')

        # n_rd.remove('Link', n_rd.links.index)
    elif True:
        
        nodal_net = pypsa.Network()
        nodal_net.set_snapshots(['1', '2'])
        nodal_net.add('Bus', ['A1', 'B1', 'B2'])
        nodal_net.buses.loc[:, 'zone_name'] = ['A', 'B', 'B']
        nodal_net.add('Line', 'A1-B1', bus0='B1', bus1='A1', x=1, s_nom=10)
        nodal_net.add('Line', 'A2-B1', bus0='B2', bus1='A1', x=1, s_nom=10)
        nodal_net.add('Line', 'A1-A2', bus0='B1', bus1='B2', x=1, s_nom=10)
        
        nodal_net.add('Generator', 'gen_A1', bus='A1', p_nom=12, marginal_cost=400, carrier="Wind")
        nodal_net.add('Generator', 'gen_B1', bus='B1', p_nom=12, marginal_cost=100, carrier="CCGT")
        nodal_net.add('Generator', 'gen_B2', bus='B2', p_nom=12, marginal_cost=200, carrier="Oil")
        nodal_net.add('Load', 'load_A1', bus='A1', p_set=[15, 15])

        zonal_net = nodal_to_zonal(nodal_net)
        zonal_net.remove('Link', zonal_net.links.index)
        # nodal_net.optimize(solver_name='gurobi')

        z_da = zonal_net
        n_rd = nodal_net

        gsk = pd.DataFrame(0., index=zonal_net.buses.index, columns=nodal_net.buses.index)
        gsk.loc['A', 'A1'] = 1.0
        gsk.loc['B', 'B1'] = 0.8
        gsk.loc['B', 'B2'] = 0.2
        gsk.columns.name = "Bus"
        gsk.index.name = "Zone"
        gsk_dict = {snapshot: gsk.copy()
            for snapshot in zonal_net.snapshots}
    else:
        n_rd = pypsa.Network()
        n_rd.set_snapshots(['now'])
        n_rd.add('Bus', ['Bus_1', 'Bus_2', 'Bus_3'])
        n_rd.buses.loc[:, 'zone_name'] = ['Zone_1', 'Zone_2', 'Zone_2']
        n_rd.add('Line', 'Line_1', bus0='Bus_1', bus1='Bus_2', x=0.1, s_nom=10, v_nom=400)
        n_rd.add('Line', 'Line_2', bus0='Bus_2', bus1='Bus_3', x=0.1, s_nom=10, v_nom=400)
        n_rd.add('Line', 'Line_3', bus0='Bus_3', bus1='Bus_1', x=0.1, s_nom=10, v_nom=400)
        n_rd.add('Generator', 'Gen_1', bus='Bus_1', p_nom=12, marginal_cost=400, carrier="hydropower")
        n_rd.add('Generator', 'Gen_2', bus='Bus_2', p_nom=12, marginal_cost=100, carrier="hydropower")
        n_rd.add('Generator', 'Gen_3', bus='Bus_3', p_nom=12, marginal_cost=200, carrier="hydropower")
        n_rd.add('Load', 'Load_1', bus='Bus_1', p_set=10)
        n_rd.add('Load', 'Load_2', bus='Bus_2', p_set=1)
        n_rd.add('Load', 'Load_3', bus='Bus_3', p_set=1)
        z_da = nodal_to_zonal(n_rd, zone_column='zone_name')
        # z_da.loads.p_set *= 1.5
    # n_rd.lines.loc[:, 's_nom'] *= 0.3
    # z_da.optimize(solver_name='gurobi')
    n_rd.optimize(solver_name='gurobi')
    # n_rd.lines_t.p0 = pd.DataFrame(0., index=n_rd.snapshots, columns=n_rd.lines.index)
    # n_rd.lines_t.p1 = pd.DataFrame(0., index=n_rd.snapshots, columns=n_rd.lines.index)
    # n_rd.buses_t.p = pd.DataFrame(0., index=n_rd.snapshots, columns=n_rd.buses.index)
    config = FBMCConfig()
    config.pos_neg_method = pos_neg_method
    config.gsk_method = gsk_method
    config.reliability_margin_factor = 0.0
    pre_process(n_rd)
    z_da.remove('Link', z_da.links.index[z_da.links.p_nom < 1e-5])
    z_da.loads_t.p_set = z_da.loads_t.p_set * (18/15)
    z_da, _, z_ptdf, ram = run_fbmc(n_rd, z_da, config=config, gsk=gsk_dict)

        

    # print(z_da.model)
    # z_da.model.objective.value = ((z_da.get_switchable_as_dense('Generator', 'marginal_cost').values * z_da.model.variables['Generator-p']).sum('snapshot').sum()
    #     #                     + 
    #     #  z_da.model.variables['Delta_NP_pos'] + z_da.model.variables['Delta_NP_neg']
    #      )  
    # z_da_copy.model.objective = ((z_da_copy.get_switchable_as_dense('Generator', 'marginal_cost').values * z_da_copy.model.variables['Generator-p']).sum('snapshot').sum()
    #     #                     + 
    #     #  z_da.model.variables['Delta_NP_pos'] + z_da.model.variables['Delta_NP_neg']
    #      )  
    # solver_parameters =  {"ResultFile":"model.ilp"}
    
    # z_da.model.constraints['Delta_Net_Position'].rhs = np.abs(z_da.model.constraints['Delta_Net_Position'].rhs)
    # z_da.model.constraints['Zone-p_definition'].rhs = np.abs(z_da.model.constraints['Zone-p_definition'].rhs)
    # z_da.optimize(solver_name='gurobi', solver_options=solver_parameters)
    zonal_prices = calculate_zonal_prices(z_da.buses.index, z_da.snapshots, z_ptdf, z_da.model)
    z_da.buses_t.marginal_price = zonal_prices
    z_da.export_to_netcdf('output_networks/zonal_no_links.nc')
    breakpoint()
    return z_da.model.objective.value, None


if __name__ == "__main__":
    
    # obj1, obj_rd1 = main(pos_neg_method=True, gsk_method=GSKMethod.MERIT_ORDER)  # 4.95, 5.82,  split-merit-order 5.86, merit-order 6.00, adjustable cap 6.09, 5.83
    # obj2, obj_rd2 = main(pos_neg_method=False, gsk_method=GSKMethod.MERIT_ORDER)  # 5.82, 6.00, 6.09, 5.83
    obj3, obj_rd3 = main(pos_neg_method=False, gsk_method=GSKMethod.ADJUSTABLE_CAP)  # 4.95, 5.82,  split-merit-order 5.86, merit-order 6.00, adjustable cap 6.09, 5.83
    print('Results:')
    # print(obj2)
    print(obj3)
    # print(f"Objective with pos_neg_method=True and gsk_method=MERIT_ORDER: {obj1}, Redispatch objective: {obj_rd1}, Sum: {obj1 + obj_rd1}")
    # print(f"Objective with pos_neg_method=False and gsk_method=MERIT_ORDER: {obj2}, Redispatch objective: {obj_rd2}, Sum: {obj2 + obj_rd2}")
    # print(f"Objective with pos_neg_method=False and gsk_method=ADJUSTABLE_CAP: {obj3}, Redispatch objective: {obj_rd3}")
    # split merit order
    # 1.62 merit order
    # 1.62 adjustable cap