import pypsa
import numpy as np
import pandas as pd

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

    post_process(nodal_net, zonal_net, fbmc_parameters)
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