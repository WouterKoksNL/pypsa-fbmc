import pypsa
import pandas as pd

from fbmc.types import SubnetFBMCParameters, DispatchResult


def do_lpf_contingency_check(
        nodal_net: pypsa.Network,
        dispatch_results: DispatchResult,
        fbmc_parameters: dict[str, SubnetFBMCParameters] 
    ):
    gens_p = dispatch_results.generators_p
    storage_p = dispatch_results.storage_units_p
    links_p = dispatch_results.links_p0
    
    nodal_net.generators_t.p_set = gens_p.reindex(index=nodal_net.snapshots, columns=nodal_net.generators.index).fillna(0.0)
    nodal_net.storage_units_t.p_set = storage_p.reindex(index=nodal_net.snapshots, columns=nodal_net.storage_units.index).fillna(0.0)
    nodal_net.links_t.p_set = links_p.reindex(index=nodal_net.snapshots, columns=nodal_net.links.index).fillna(0.0)
    for sn_name, sn_params in fbmc_parameters.items():
        branches = sn_params.cnecs.get_level_values('branch').unique()
        branch_outages = sn_params.cnecs.get_level_values('outage').unique()

        lpf_result = nodal_net.lpf_contingency(snapshots=nodal_net.snapshots[0], branch_outages=branch_outages)
        overload = (lpf_result.abs().max(axis=1).droplevel(0).loc[branches] > nodal_net.lines.s_nom.loc[branches] + 1e-5).all().all()
        if overload:
            breakpoint()
            raise ValueError("N-1 overloads detected using zonal dispatch.")
    return 