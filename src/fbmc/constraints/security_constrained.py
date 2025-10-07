import pypsa
from itertools import product
import pandas as pd
import xarray as xr
from typing import Sequence, Any
import numpy as np

# from ..network_conversion import nodal_to_zonal
# from network_conversion import nodal_to_zonal


def add_security_constraints(
    nodal_net: pypsa.Network,
    zonal_net: pypsa.Network, 
    snapshots: Sequence | None = None,
    gsk: pd.DataFrame = None, 
    cnecs: pd.MultiIndex | None = None,
    cnes: pd.Index | None = None,
    branch_outages: Sequence | pd.Index | pd.MultiIndex | None = None,
    model_kwargs: dict | None = None,
    **kwargs: Any,
) -> tuple[str, str]:
    """Add security constraints to zonal network.

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

    if (cnecs is not None) and ((branch_outages is not None) or (cnes is not None)):
        raise ValueError("If cnecs are passed, branch_outages and cnes must not be passe")
    
    all_passive_branches = nodal_net.passive_branches().index.droplevel(0)
    if cnecs is None:
        if cnes is None:
            cnes = all_passive_branches
        if branch_outages is None:
            branch_outages = all_passive_branches[:3]
        cnecs_tuples_list = [(branch, outage) for branch, outage in product(cnes, branch_outages) if branch != outage]
        cnecs = pd.MultiIndex.from_tuples(cnecs_tuples_list, names=['branch', 'outage'])
        
    if branch_outages is None:
        branch_outages = all_passive_branches



    m = zonal_net.optimize.create_model(
        snapshots=snapshots,
        **model_kwargs,
    )

    for sub_network in nodal_net.sub_networks.obj:
        branches_i = sub_network.branches_i().droplevel(0)
        outages = branches_i.intersection(branch_outages)

        if outages.empty:
            continue

        sub_network.calculate_BODF()
        BODF = pd.DataFrame(sub_network.BODF, index=branches_i, columns=branches_i)[
            outages
        ]

        if gsk is None:
            bus_inds = sub_network.buses().index
            zones = sub_network.buses()['zone_name'].unique()
            gsk = pd.DataFrame(np.random.rand(bus_inds.size, zones.size), 
                               index=bus_inds,
                               columns=zones,
                               )

        sub_network.calculate_PTDF()
        PTDF = pd.DataFrame(sub_network.PTDF, index=branches_i, columns=sub_network.buses().index)

            # Create all (line, outage) pairs excluding self-contingencies

        # pairs = list(product(cnes, branch_outages))
        # multi_index = pd.MultiIndex.from_tuples(pairs, names=['branch', 'outage']) 

        # BODF.loc[branch, outage].T * PTDF.loc[branch, sub_network.buses().index]
        nPTDF_security = (
            PTDF.loc[cnecs.get_level_values('branch'), sub_network.buses().index] + 
            BODF.loc[cnecs.get_level_values('branch'), cnecs.get_level_values('outage')] @ PTDF.loc[cnecs.get_level_values('outage'), sub_network.buses().index]
        )  # dims (CNEC x bus)
        nPTDF_security.index = cnecs
        
        if isinstance(gsk, dict):
            zPTDF = {
                snapshot: nPTDF_security @ gsk_snapshot.loc[:, sub_network.buses().index].T
                for snapshot, gsk_snapshot in gsk.items()
            }
        else:
            zPTDF = nPTDF_security @ gsk.loc[:, sub_network.buses().index].T   # dims (CNEC x zone)
        # lhs = zPTDF * net_positions
        # RAM = ram_cnes.loc[multi_index.get_level_values('branch'), multi_index.get_level_values('outage')]

        # nPTDF_security = (PTDF.values[:, None, :] + BODF.values.T @ PTDF.values)
        # zPTDF = np.einsum("lcb,bz->lcz", nPTDF_security, gsk.loc[sub_network.buses().index, :].values)

        from ..parameters.flows import calculate_ram
        ram = calculate_ram(nodal_net, zPTDF)
        print('ok')
        
        # m.add_constraints(
        #     lhs=zPTDF * net_positions,
        #     rhs=ram,
        #     name='n-1_security'
        # )
        # for c_outage, c_affected in product(
        #     outages.unique(0), branches_i.unique(0)
        # ):
        #     c_outage_ = c_outage + "-outage"
        #     c_outages = outages.get_loc_level(c_outage)[1]
        #     flow_outage = m.variables[c_outage + "-s"].loc[:, c_outages]
        #     flow_outage = flow_outage.rename({c_outage: c_outage_})

        #     bodf = BODF.loc[c_affected, c_outage]
        #     bodf = xr.DataArray(bodf, dims=[c_affected, c_outage_])
        #     additional_flow = flow_outage * bodf
        #     for bound, kind in product(("lower", "upper"), ("fix", "ext")):
        #         coord = c_affected + "-" + kind
        #         constraint = coord + "-s-" + bound
        #         if constraint not in m.constraints:
        #             continue
        #         rename = {c_affected: coord}
        #         added_flow = additional_flow.rename(rename)
        #         con = m.constraints[constraint]  # use this as a template
        #         # idx now contains fixed/extendable for the sub-network
        #         idx = con.lhs.indexes[coord].intersection(added_flow.indexes[coord])
        #         sel = {coord: idx}


        #         new_flow = con.lhs.sel(sel) + added_flow.sel(sel)
        #         if gsk is not None:
        #             lhs = gsk * new_flow
        #         name = constraint + f"-security-for-{c_outage_}-in-{sub_network}"
        #         m.add_constraints(
        #             lhs, con.sign.sel(sel), con.rhs.sel(sel), name=name
        #         )

    return m

