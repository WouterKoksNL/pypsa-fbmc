import pandas as pd
import pypsa
from typing import Sequence
from linopy import Model, LinearExpression


from .regulator_handler import RegulatorHandler
from .security_constraints import add_security_constraints
from src.fbmc.parameters.types import DispatchResults

def select_flex_gens(net, flexible_carriers: Sequence[str]) -> pd.Index:
    return net.generators.index[
            net.generators.carrier.isin(flexible_carriers)
        ]


def run_redispatch(nodal_net:pypsa.Network, dispatch_results:DispatchResults, adjustable_carriers=None, with_security_constraints=True, branch_outages=None) -> pypsa.Network:
    if adjustable_carriers is None:
        adjustable_carriers = nodal_net.generators.carrier.unique()
    flex_gens_up = select_flex_gens(nodal_net, adjustable_carriers)
    flex_gens_down = flex_gens_up

    regulator_handler = RegulatorHandler(
        nodal_net,
        dispatch_results,
        flex_gens_up,
        flex_gens_down,
    )
    regulator_handler.add_up_down_reg()
    nodal_net.optimize.add_load_shedding(sign=1, marginal_cost=1e5)
    if with_security_constraints:
        add_security_constraints(nodal_net, branch_outages)
        _set_nodal_objective(nodal_net)
        nodal_net.optimize.solve_model(solver_name="gurobi")
        cost = get_costs(nodal_net)
    else:
        nodal_net.optimize(solver_name="gurobi")
        cost = nodal_net.model.objective.value
    if nodal_net.model.termination_condition != 'optimal':
        raise ValueError("Redispatch optimization did not solve to optimality.")
    return nodal_net, cost


def _get_nodal_objective(
        net: pypsa.Network,
        model: Model,
        rt_deviation_factor: float = 0.9,
        rt_reference_price: float = 100.0,
        stage_identifier_str: str = "_rd",
        ) -> LinearExpression:
    '''Create objective function for the nodal stages by altering the Linopy optimization model. This objective is a linear combination of cost minimization and deviation minimization.
    The parameter settings.rt_deviation_factor controls the importance of the deviation minimization part. '''
    up_down_regulators = [gen_name for gen_name, carrier in zip(net.generators.index, net.generators.carrier) if (stage_identifier_str in gen_name)] # list of up- and downregulators

    # wind_generators = [gen_name for gen_name, carrier in zip(net.generators.index, net.generators.carrier) if ('wind' in carrier)] # list of up- and downregulators
    # up_down_storage_regulators = [storage_name for storage_name, carrier in zip(net.storage_units.index, net.storage_units.carrier) if (stage_identifier_str in storage_name)]
    if "StorageUnit-p" not in model.variables:
        return (
                (1 - rt_deviation_factor) * (
                    net.get_switchable_as_dense('Generator', 'marginal_cost').values * model.variables['Generator-p']
                    ).sum() + 
                rt_deviation_factor * rt_reference_price * 
                (model.variables["Generator-p"].sel(Generator=up_down_regulators).sum() 
            ))
    else:
        raise NotImplementedError("For the case with storage, only pure deviation minimization is currently implemented.")
    # else:
    #     up_down_storage_regulators = [storage_name for storage_name, carrier in zip(net.storage_units.index, net.storage_units.carrier) if (stage_identifier_str in storage_name)]
    #     if rt_deviation_factor != 1:
    #         raise NotImplementedError("For the case with storage, only pure deviation minimization is currently implemented.")
    #     return (
    #         (model.variables["Generator-p"].sel(Generator=up_down_regulators).sum() 
    #         + (model.variables['StorageUnit-p'] - storage_p_old).loc[storage_redispatch_units].abs()
    #            ).sum('snapshot').sum() 
    #         ))

def _set_nodal_objective(net) -> None:
    '''Create a model instance and alter its objective from the standard PyPSA formulation.'''
    if net.model is None:
        model = net.optimize.create_model()
    else:
        model = net.model
    model.objective = _get_nodal_objective(net, model)
    return 

def get_costs(
    net: pypsa.Network,
):
    gen_costs = (net.get_switchable_as_dense('Generator', 'marginal_cost') * net.generators_t.p).sum().sum()
    return gen_costs