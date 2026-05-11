import pandas as pd
import pypsa


def extract_model_results(net: pypsa.Network):
        gen_p = pd.DataFrame(
            net.model.solution['Generator-p'].values,
            index=net.snapshots, 
            columns=net.generators.index
        )
        net.generators_t.p = gen_p

        net.loads_t.p = net.loads_t.p_set

        if not net.storage_units.empty:
            storage_p = pd.DataFrame(
            net.model.solution['StorageUnit-p_dispatch'].values,
            index=net.snapshots, 
            columns=net.storage_units.index
            )
            net.storage_units_t.p_dispatch = storage_p
        
        if not net.links.empty:
            links_p = pd.DataFrame(
                net.model.solution['Link-p'].values,
                index=net.snapshots, 
                columns=net.links.index
            )

            net.links_t.p0 = links_p
            net.links_t.p1 = -links_p
        return 

def get_net_positions(zonal_net: pypsa.Network, advanced_hybrid_flag: bool) -> pd.DataFrame:
    """Get net positions, accounting for link flows if advanced hybrid coupling is enabled. This is needed because with the current algorithm, 
    the net position of a zone downstream of a link flow has the flow included in it, while the upstream zone does not. 

    Args:
        zonal_net (pypsa.Network): _description_
        advanced_hybrid_flag (bool): _description_

    Returns:
        pd.DataFrame: _description_
    """

    net_positions = zonal_net.model.solution['Zone-p'].to_pandas()

    if "Link-p" not in zonal_net.model.solution or not advanced_hybrid_flag:
        return net_positions

    link_flows = zonal_net.model.solution['Link-p'].to_pandas()
    flow_from = - link_flows.T.groupby(zonal_net.links.bus0).sum().T.reindex(columns=zonal_net.buses.index, fill_value=0.0)
    flow_to = link_flows.T.groupby(zonal_net.links.bus1).sum().T.reindex(columns=zonal_net.buses.index, fill_value=0.0)
    net_positions -= flow_from + flow_to
    return net_positions