import pypsa
import numpy as np
import pandas as pd
from logging import Logger 

from src.fbmc.config import FBMCConfig
from src.fbmc.main import run_fbmc 
from src.fbmc.parameters.types import SubnetFBMCParameters
from src.post_processing.market_prices import calculate_zonal_prices

from src.case_creation.main import create_case, Cases

from src.redispatch.main import run_redispatch

from src.post_processing.post_process import post_process



def pre_process(net: pypsa.Network):
    net.remove('Line', net.lines.index[net.lines.s_nom < 1e-5])
    net.remove('Transformer', net.transformers.index[net.transformers.s_nom < 1e-5])
    net.remove('Link', net.links.index[net.links.p_nom < 1e-5])


def main(case_name=Cases.BASIC_THREE_NODE, 
         snapshot_length=3):
    logger = Logger(__name__)
    
    case_data = create_case(case_name, load_case_flag=False, save_case_flag=True)

    logger.info(f"Running case: {case_name}")
    nodal_net: pypsa.Network = case_data['nodal_net']
    zonal_net: pypsa.Network = case_data['zonal_net']

    gsk_dict = case_data.get('gsk_dict', None)
    config = FBMCConfig()
    # nodal_net.remove('StorageUnit', nodal_net.storage_units.index)
    # zonal_net.remove('StorageUnit', zonal_net.storage_units.index)
    nodal_net.optimize(solver_name='gurobi')
    

    
    print(config.gsk_method)
    config.reliability_margin_factor = 0.0
    pre_process(nodal_net)
    zonal_net.remove('Link', zonal_net.links.index[zonal_net.links.p_nom < 1e-5])

    zonal_net, _, fbmc_parameters = run_fbmc(nodal_net, zonal_net, config=config, gsk=gsk_dict)

    post_process(nodal_net, zonal_net, fbmc_parameters)
    breakpoint()
    # nodal_net.optimize.optimize_security_constrained(solver_name='gurobi')
    return zonal_net.model.objective.value, None

if __name__ == "__main__":
    
    # obj1, obj_rd1 = main(pos_neg_method=True, gsk_method=GSKMethod.MERIT_ORDER)  # 4.95, 5.82,  split-merit-order 5.86, merit-order 6.00, adjustable cap 6.09, 5.83
    # obj2, obj_rd2 = main(pos_neg_method=False, gsk_method=GSKMethod.MERIT_ORDER)  # 5.82, 6.00, 6.09, 5.83
    obj3, obj_rd3 = main(Cases.PYPSA_EUR_CENTRAL_NORTHERN)  # 4.95, 5.82,  split-merit-order 5.86, merit-order 6.00, adjustable cap 6.09, 5.83


