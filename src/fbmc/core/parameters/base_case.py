import pandas as pd
import pypsa
from .bridge_branches import find_bridges_network
from ...enums import BaseCaseStrategy


def prepare_nodal_optimum_base_case(_nodal_net: pypsa.Network, **solver_kwargs):
    """Prepare base case using nodal optimziation without security constraints.
    """
    base_case = _nodal_net.copy()
    base_case.optimize.add_load_shedding(sign=1, marginal_cost=marginal_cost_load_shedding)
    base_case.optimize(solver_name='gurobi')
    if base_case.model.termination_condition != 'optimal':
        raise ValueError("Initial nodal optimization did not solve to optimality.")
    return base_case


def prepare_zero_flow_base_case(_nodal_net: pypsa.Network, **solver_kwargs):
    base_case = _nodal_net.copy()
    base_case.lines_t.p0.loc[base_case.snapshots, base_case.lines.index] = 0
    base_case.transformers_t.p0.loc[base_case.snapshots, base_case.transformers.index] = 0
    base_case.buses_t.p.loc[base_case.snapshots, base_case.buses.index] = 0
    return base_case


def prepare_custom_base_case(_nodal_net: pypsa.Network, **solver_kwargs):
    return _nodal_net.copy()


def prepare_security_constrained_base_case(_nodal_net: pypsa.Network, **solver_kwargs):
    base_case = _nodal_net.copy()
    if base_case.sub_networks.empty:
        base_case.determine_network_topology()
    bridges = find_bridges_network(base_case)
    outaged_lines = base_case.lines.index.difference(bridges)
    base_case.optimize.add_load_shedding(sign=1, marginal_cost=marginal_cost_load_shedding)
    base_case.optimize.optimize_security_constrained(solver_name='gurobi', branch_outages=outaged_lines)
    if base_case.model.termination_condition != 'optimal':
        raise ValueError("Initial nodal optimization did not solve to optimality.")
    return base_case


prepare_function_mapping = {
    BaseCaseStrategy.ZERO_FLOWS: prepare_zero_flow_base_case,
    BaseCaseStrategy.NODAL_OPTIMUM: prepare_nodal_optimum_base_case,
    BaseCaseStrategy.SECURITY_CONSTRAINED_NODAL_OPTIMUM: prepare_security_constrained_base_case,
    BaseCaseStrategy.CUSTOM: prepare_custom_base_case
}

def prepare_base_case(net: pypsa.Network, strategy: BaseCaseStrategy, base_case_kwargs: dict = None):
    if strategy not in prepare_function_mapping:
        raise ValueError(f"Strategy {strategy} is not supported.")
    if base_case_kwargs is None:
        base_case_kwargs = {}
    return prepare_function_mapping[strategy](net, **base_case_kwargs)


def get_base_flows_subnet(sub_network: pypsa.SubNetwork
                   ) -> pd.DataFrame:
    """Get the base case power flows from transformers, links and lines.
    Assumes there are no transformers, links or lines with the same name."""

    return pd.concat([
        sub_network.pnl('transformers')['p0'].T, 
        sub_network.pnl('lines')['p0'].T
    ]).T


def calc_base_net_positions_subnet(sub_network: pypsa.SubNetwork) -> pd.DataFrame:
    """Calculate net positions for each zone based on bus power values.
    
    Args:
        buses: DataFrame containing bus data with zone_name column
        buses_t: DataFrame containing time series bus power values
        zones: Index of zone names to calculate positions for
        
    Returns:
        DataFrame with net positions per zone
    """

    net_positions = (
        sub_network.pnl('buses')['p'].T.groupby(sub_network.df('buses').zone_name).sum().T 
    )

    if net_positions.sum(axis=1).abs().max() > 1e-6:
        raise ValueError("Net positions do not sum to zero.")
    return net_positions


def get_base_flows(
        net: pypsa.Network,
):
    """Get the base case power flows from transformers, links and lines.
    Assumes there are no transformers, links or lines with the same name."""

    return pd.concat([
        net.transformers_t.p0.T, 
        net.lines_t.p0.T
    ]).T

def calc_base_net_positions(net: pypsa.Network) -> pd.DataFrame:
    """Calculate net positions for each zone based on bus power values.
    
    Args:
        buses: DataFrame containing bus data with zone_name column
        buses_t: DataFrame containing time series bus power values
        zones: Index of zone names to calculate positions for
    """
    net_positions = (
        net.buses_t.p.T.groupby(net.buses.zone_name).sum().T 
    )

    if net_positions.sum(axis=1).abs().max() > 1e-6:
        raise ValueError("Net positions do not sum to zero.")
    return net_positions