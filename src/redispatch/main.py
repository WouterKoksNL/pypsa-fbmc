import pandas as pd
import pypsa
from typing import Sequence
from .regulator_handler import RegulatorHandler

def select_flex_gens(net, flexible_carriers: Sequence[str]) -> pd.Index:
    return net.generators.index[
            net.generators.carrier.isin(flexible_carriers)
        ]


def run_redispatch(nodal_net:pypsa.Network, dispatch_results:pd.DataFrame, adjustable_carriers=None) -> pypsa.Network:
    if adjustable_carriers is None:
        adjustable_carriers = nodal_net.generators.carrier.unique()
    flex_gens_up = select_flex_gens(nodal_net, adjustable_carriers)
    flex_gens_down = flex_gens_up
    breakpoint()
    regulator_handler = RegulatorHandler(
        nodal_net,
        dispatch_results,
        flex_gens_up,
        flex_gens_down,
    )
    regulator_handler.add_up_down_reg()

    breakpoint()
    nodal_net.optimize(solver_name="gurobi")
    return nodal_net
