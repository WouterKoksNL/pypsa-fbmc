import pypsa
import numpy as np
import pandas as pd
from logging import Logger 

from src.fbmc.parameters.cnec import find_bridges_network
from src.fbmc.config import FBMCConfig
from src.fbmc.main import run_fbmc 
from src.fbmc.parameters.types import SubnetFBMCParameters
from src.post_processing.market_prices import calculate_zonal_prices

from src.case_creation.main import create_case, Cases

from src.redispatch.main import run_redispatch

from src.post_processing.lpf import do_lpf_contingency_check



def remove_zero_capacity_branches(net: pypsa.Network):
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
    nodal_net.determine_network_topology()
    bridges = find_bridges_network(nodal_net)
    outaged_lines = nodal_net.lines.index.difference(bridges)
    nodal_net.optimize.optimize_security_constrained(solver_name='gurobi', branch_outages=outaged_lines)

    nodal_optimum = nodal_net.model.objective.value
    print(config.gsk_method)
    config.reliability_margin_factor = 0.0
    remove_zero_capacity_branches(nodal_net)
    zonal_net.remove('Link', zonal_net.links.index[zonal_net.links.p_nom < 1e-5])

    zonal_net, _, fbmc_parameters = run_fbmc(nodal_net, zonal_net, config=config, gsk=gsk_dict)

    if config.run_redispatch:
        zonal_net.generators_t.p = zonal_net.model.solution['Generator-p'].to_pandas()
        outaged_lines = nodal_net.passive_branches()
        
        nodal_net = run_redispatch(nodal_net, zonal_net.generators_t.p, with_security_constraints=True, branch_outages=outaged_lines)
        dispatch_results = {
            'generators': nodal_net.generators_t.p,
            'storage_units': nodal_net.storage_units_t.p,
            'links': nodal_net.links_t.p0,
        }
    else:
        dispatch_results = {
            'generators': zonal_net.generators_t.p,
            'storage_units': zonal_net.storage_units_t.p,
            'links': zonal_net.links_t.p0,
        }

    
    do_lpf_contingency_check(nodal_net, dispatch_results, fbmc_parameters)
    
    
    print("Costs of FBMC to Nodal optimum:", zonal_net.model.objective.value / nodal_optimum)
    print("Cost of FBMC + redispatch vs nodal optimum:", nodal_net.model.objective.value / nodal_optimum)
    
    # nodal_net.optimize.optimize_security_constrained(solver_name='gurobi')
    return zonal_net.model.objective.value, None

if __name__ == "__main__":
    
    # obj1, obj_rd1 = main(pos_neg_method=True, gsk_method=GSKMethod.MERIT_ORDER)  # 4.95, 5.82,  split-merit-order 5.86, merit-order 6.00, adjustable cap 6.09, 5.83
    # obj2, obj_rd2 = main(pos_neg_method=False, gsk_method=GSKMethod.MERIT_ORDER)  # 5.82, 6.00, 6.09, 5.83
    obj3, obj_rd3 = main(Cases.PYPSA_EUR_CENTRAL_NORTHERN)  # 4.95, 5.82,  split-merit-order 5.86, merit-order 6.00, adjustable cap 6.09, 5.83


