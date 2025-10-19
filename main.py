import pypsa
import numpy as np
import pandas as pd

from src.fbmc.config import FBMCConfig, GSKMethod
from src.fbmc.pos_neg_method import setup_pos_neg_fbmc_model
from src.fbmc.main import run_fbmc 
from src.fbmc.market_prices import calculate_zonal_prices

from src.case_creation.main import create_case, Cases

from src.redispatch.main import run_redispatch



def pre_process(net: pypsa.Network):
    net.remove('Line', net.lines.index[net.lines.s_nom < 1e-5])
    net.remove('Transformer', net.transformers.index[net.transformers.s_nom < 1e-5])
    net.remove('Link', net.links.index[net.links.p_nom < 1e-5])

def main(case_name=Cases.BASIC_THREE_NODE, 
         snapshot_length=3):
    logger = Logger(__name__)
    case_data = create_case_router(case_name, load_case_flag=False, save_case_flag=True)
    
    logger.info(f"Running case: {case_name}")
    nodal_net = case_data['nodal_net']
    zonal_net = case_data['zonal_net']
    gsk_dict = case_data.get('gsk_dict', None)
    config = FBMCConfig()
    config.pos_neg_method = pos_neg_method
    config.gsk_method = gsk_method
    config.reliability_margin_factor = 0.0
    pre_process(n_rd)
    z_da.remove('Link', z_da.links.index[z_da.links.p_nom < 1e-5])
    z_da.loads_t.p_set = z_da.loads_t.p_set * (18/15)
    z_da, _, z_ptdf, ram = run_fbmc(n_rd, z_da, config=config, gsk=gsk_dict)

    zonal_net, _, fbmc_parameters = run_fbmc(nodal_net, zonal_net, config=config, gsk=gsk_dict)

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
    obj3, obj_rd3 = main(Cases.SCIGRID_DE)  # 4.95, 5.82,  split-merit-order 5.86, merit-order 6.00, adjustable cap 6.09, 5.83
    print('Results:')
    # print(obj2)
    print(obj3)
    # print(f"Objective with pos_neg_method=True and gsk_method=MERIT_ORDER: {obj1}, Redispatch objective: {obj_rd1}, Sum: {obj1 + obj_rd1}")
    # print(f"Objective with pos_neg_method=False and gsk_method=MERIT_ORDER: {obj2}, Redispatch objective: {obj_rd2}, Sum: {obj2 + obj_rd2}")
    # print(f"Objective with pos_neg_method=False and gsk_method=ADJUSTABLE_CAP: {obj3}, Redispatch objective: {obj_rd3}")
    # split merit order
    # 1.62 merit order
    # 1.62 adjustable cap