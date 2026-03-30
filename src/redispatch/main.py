import pandas as pd
import pypsa
from typing import Sequence
from itertools import product
import xarray as xr
from typing import Any

from .regulator_handler import RegulatorHandler

def select_flex_gens(net, flexible_carriers: Sequence[str]) -> pd.Index:
    return net.generators.index[
            net.generators.carrier.isin(flexible_carriers)
        ]


def run_redispatch(nodal_net:pypsa.Network, dispatch_results:pd.DataFrame, adjustable_carriers=None, with_security_constraints=True, branch_outages=None) -> pypsa.Network:
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
        
        nodal_net.optimize.add_security_constraints(snapshots=nodal_net.snapshots, branch_outages=branch_outages)
        nodal_net.optimize.solve_model(solver_name="gurobi")
    else:
        nodal_net.optimize(solver_name="gurobi")
    return nodal_net


def add_security_constraints(
        net,
        snapshots: Sequence | None = None,
        branch_outages: Sequence | pd.Index | pd.MultiIndex | None = None,
        multi_investment_periods: bool = False,
        model_kwargs: dict | None = None,
        **kwargs: Any,
    ) -> tuple[str, str]:
        """Compute Security-Constrained Linear Optimal Power Flow (SCLOPF).

        This ensures that no branch is overloaded even given the branch outages.

        Parameters
        ----------
        snapshots : list-like, optional
            Set of snapshots to consider in the optimization. The default is None.
        branch_outages : list-like/pandas.Index/pandas.MultiIndex, optional
            Subset of passive branches to consider as possible outages. If a list
            or a pandas.Index is passed, it is assumed to identify lines. If a
            multiindex is passed, its first level has to contain the component names,
            the second the assets. The default None results in all passive branches
            to be considered.
        multi_investment_periods : bool, default False
            Whether to optimise as a single investment period or to optimise in multiple
            investment periods. Then, snapshots should be a ``pd.MultiIndex``.
        model_kwargs: dict
            Keyword arguments used by `linopy.Model`, such as `solver_dir` or `chunk`.
        **kwargs:
            Keyword argument used by `linopy.Model.solve`, such as `solver_name`,
            `problem_fn` or solver options directly passed to the solver.

        """
        if model_kwargs is None:
            model_kwargs = {}

        all_passive_branches = net.passive_branches().index

        if branch_outages is None:
            branch_outages = all_passive_branches
        elif isinstance(branch_outages, (list | pd.Index)):
            branch_outages = pd.MultiIndex.from_product([("Line",), branch_outages])

            if diff := set(branch_outages) - set(all_passive_branches):
                msg = f"The following passive branches are not in the network: {diff}"
                raise ValueError(msg)

        if not len(all_passive_branches):
            return net

        m = net.optimize.create_model(
            snapshots=snapshots,
            multi_investment_periods=multi_investment_periods,
            **model_kwargs,
        )

        for sub_network in net.c.sub_networks.static.obj:
            branches_i = sub_network.branches_i()
            outages = branches_i.intersection(branch_outages)

            if outages.empty:
                continue

            sub_network.calculate_BODF()
            BODF = pd.DataFrame(sub_network.BODF, index=branches_i, columns=branches_i)[
                outages
            ]

            for c_outage, c_affected in product(
                outages.unique(0), branches_i.unique(0)
            ):
                c_outage_ = c_outage + "-outage"
                c_outages = outages.get_loc_level(c_outage)[1]
                flow_outage = m.variables[c_outage + "-s"].loc[:, c_outages]
                flow_outage = flow_outage.rename({"name": c_outage_})

                bodf = BODF.loc[c_affected, c_outage]
                bodf = xr.DataArray(bodf, dims=[c_affected, c_outage_])
                added_flow = flow_outage * bodf

                for bound, kind in product(("lower", "upper"), ("fix", "ext")):
                    constraint = c_affected + "-" + kind + "-s-" + bound
                    if constraint not in m.constraints:
                        continue

                    con = m.constraints[constraint]

                    idx = con.lhs.indexes["name"].intersection(
                        added_flow.indexes[c_affected]
                    )

                    added_flow_aligned = added_flow.sel({c_affected: idx}).rename(
                        {c_affected: "name"}
                    )
                    lhs = con.lhs.sel(name=idx) + added_flow_aligned

                    name = (
                        constraint
                        + f"-security-for-{c_outage_}-in-sub-network-{sub_network.name}"
                    )
                    m.add_constraints(
                        lhs, con.sign.sel(name=idx), con.rhs.sel(name=idx), name=name
                    )

        return net


# def _get_nodal_objective(self, 
#                             model: Model
#                             ) -> LinearExpression:
#     '''Create objective function for the nodal stages by altering the Linopy optimization model. This objective is a linear combination of cost minimization and deviation minimization.
#     The parameter settings.rt_deviation_factor controls the importance of the deviation minimization part. '''
#     up_down_regulators = [gen_name for gen_name, carrier in zip(self.net.generators.index, self.net.generators.carrier) if (self.stage_identifier_str in gen_name)] # list of up- and downregulators
#     # wind_generators = [gen_name for gen_name, carrier in zip(self.net.generators.index, self.net.generators.carrier) if ('wind' in carrier)] # list of up- and downregulators
#     return (
#             (1 - self.settings.rt_deviation_factor) * (as_dense(self.net, 'Generator', 'marginal_cost').values * model.variables['Generator-p']).sum('snapshot').sum() + 
#             self.settings.rt_deviation_factor * self.settings.rt_reference_price * model.variables["Generator-p"].sum("snapshot").loc[up_down_regulators].sum() 
#             )

# def _set_nodal_objective(self) -> None:
#     '''Create a model instance and alter its objective from the standard PyPSA formulation.'''
#     model = self.net.optimize.create_model()
#     model.objective = self._get_nodal_objective(model)
#     return 