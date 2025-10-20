import pypsa

from .lpf import do_lpf_contingency_check
from src.fbmc.parameters.types import SubnetFBMCParameters
from src.post_processing.results_extraction import extract_model_results


def post_process(nodal_net: pypsa.Network, zonal_net: pypsa.Network, fbmc_parameters: SubnetFBMCParameters):
    extract_model_results(zonal_net)
    do_lpf_contingency_check(nodal_net, zonal_net, fbmc_parameters)
    
    nodal_net.optimize(solver_name='gurobi')
    print("Costs of FBMC to Nodal optimum:", zonal_net.model.objective.value / nodal_net.model.objective.value)
    return 