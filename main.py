from PyPSA import pypsa
import numpy as np
import pandas as pd
from logging import Logger 

from src.fbmc.parameters.bridge_branches import find_bridges_network
from src.fbmc.config import FBMCConfig
from src.fbmc.main import setup_fbmc_model, solve
from src.fbmc.parameters.base_case import prepare_base_case, BaseCaseStrategy
from src.post_processing.market_prices import calculate_zonal_prices

from src.case_creation.main import create_case, Cases

from src.redispatch.main import run_redispatch

from src.post_processing.lpf import do_lpf_contingency_check
from src.fbmc.parameters.types import DispatchResults
from src.fbmc.parameters.gsk import calculate_gsk, GSKStrategy
from src.fbmc.input_checks import do_input_checks


def remove_zero_capacity_branches(net: pypsa.Network):
    net.remove('Line', net.lines.index[net.lines.s_nom < 1e-5])
    net.remove('Transformer', net.transformers.index[net.transformers.s_nom < 1e-5])
    net.remove('Link', net.links.index[net.links.p_nom < 1e-5])


def main(
        case_name=Cases.BASIC_THREE_NODE, 
        gsk_strategy: None | GSKStrategy = None,
        base_case_strategy: None | BaseCaseStrategy = None,
        snapshot_length=3,
        case_kwargs={},
        load_case_flag=False,
        save_case_flag=True,
         ):
    logger = Logger(__name__)
    
    case_data = create_case(case_name, load_case_flag=load_case_flag, save_case_flag=False, **case_kwargs)

    logger.info(f"Running case: {case_name}")
    nodal_net: pypsa.Network = case_data['nodal_net']
    zonal_net: pypsa.Network = case_data['zonal_net']
    gsk = case_data.get('gsk_dict', None)

    do_input_checks(nodal_net, zonal_net, gsk)
    config = FBMCConfig()
    if base_case_strategy is not None:
        config.base_case_strategy = base_case_strategy
    # nodal_net.remove('StorageUnit', nodal_net.storage_units.index)
    # zonal_net.remove('StorageUnit', zonal_net.storage_units.index)
    if nodal_net.sub_networks.empty:
        nodal_net.determine_network_topology()
    bridges = find_bridges_network(nodal_net)
    outaged_lines = nodal_net.lines.index.difference(bridges)
    
    base_case = prepare_base_case(
        nodal_net, 
        strategy=base_case_strategy, 
        base_case_kwargs={'marginal_cost_load_shedding': config.marginal_cost_load_shedding}
        )
    gsk = None

    print(gsk_strategy)

    if gsk is None:
        gsk_strategy = gsk_strategy if gsk_strategy is not None else config.gsk_method
        gsk = calculate_gsk(base_case, gsk_strategy, config)

    config.reliability_margin_factor = 0.0
    remove_zero_capacity_branches(nodal_net)
    zonal_net.remove('Link', zonal_net.links.index[zonal_net.links.p_nom < 1e-5])


    model, fbmc_parameters = setup_fbmc_model(
        zonal_net, 
        basecase_nodal_network=base_case, 
        gsk=gsk,
        config=config
    )
    zonal_net, net_positions = solve(zonal_net, advanced_hybrid_flag=config.advanced_hybrid_coupling)
    dispatch_results = DispatchResults(zonal_net)
    if config.run_redispatch:
      
        nodal_net, cost = run_redispatch(nodal_net, zonal_net.generators_t.p, with_security_constraints=True, branch_outages=outaged_lines)
        dispatch_results = DispatchResults(nodal_net)  # override dispatch results

    if base_case_strategy in [BaseCaseStrategy.NODAL_OPTIMUM, BaseCaseStrategy.SECURITY_CONSTRAINED_NODAL_OPTIMUM]:
        nodal_optimum = base_case.objective    
        print("Costs of FBMC to Nodal optimum:", zonal_net.model.objective.value / nodal_optimum)
        print("Cost of FBMC + redispatch vs nodal optimum:", cost / nodal_optimum)
    breakpoint()
    do_lpf_contingency_check(nodal_net, dispatch_results, fbmc_parameters)
    
    

    

    return zonal_net.model.objective.value, None

if __name__ == "__main__":
    
    obj3, obj_rd3 = main(
        Cases.PYPSA_EUR_UA, 
        gsk_strategy=GSKStrategy.P_NOM,
        base_case_strategy=BaseCaseStrategy.ZERO_FLOWS,
        case_kwargs={
            'snapshot_i_range': slice(0, 3),
            'drop_countries': ["GB"]
            },
        )  


