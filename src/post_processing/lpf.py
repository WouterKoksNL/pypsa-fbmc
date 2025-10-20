import pypsa

from src.fbmc.parameters.types import SubnetFBMCParameters


def do_lpf_contingency_check(
        nodal_net: pypsa.Network,
        zonal_net: pypsa.Network,
        fbmc_parameters: dict[str, SubnetFBMCParameters] 
    ):
    nodal_net.generators_t.p_set = zonal_net.generators_t.p.reindex(index=nodal_net.snapshots, columns=nodal_net.generators.index).fillna(0.0)
    nodal_net.storage_units_t.p_set = zonal_net.storage_units_t.p_dispatch.reindex(index=nodal_net.snapshots, columns=nodal_net.storage_units.index).fillna(0.0)
    nodal_net.links_t.p_set = zonal_net.links_t.p0.reindex(index=nodal_net.snapshots, columns=nodal_net.links.index).fillna(0.0)
    for sn_name, sn_params in fbmc_parameters.items():
        branches = sn_params.cnecs.get_level_values('branch').unique()
        branch_outages = sn_params.cnecs.get_level_values('outage').unique()

        lpf_result = nodal_net.lpf_contingency(snapshots=nodal_net.snapshots[0], branch_outages=branch_outages)
        overload_check = (lpf_result.abs().max(axis=1).droplevel(0).loc[branches] <= nodal_net.lines.s_nom.loc[branches] + 1e-5).all()
        if not overload_check:
            raise ValueError("N-1 overloads detected using zonal dispatch.")
    return 