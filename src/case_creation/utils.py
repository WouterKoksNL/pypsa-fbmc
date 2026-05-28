
import pypsa


def remove_zero_capacity_branches(net: pypsa.Network):
    net.remove('Line', net.lines.index[net.lines.s_nom < 1e-5])
    net.remove('Transformer', net.transformers.index[net.transformers.s_nom < 1e-5])
    net.remove('Link', net.links.index[net.links.p_nom < 1e-5])


def remove_zero_capacity_links(zonal_net: pypsa.Network):
    zonal_net.remove('Link', zonal_net.links.index[zonal_net.links.p_nom < 1e-5])


def select_snapshot(net: pypsa.Network, snapshot_i_range: slice):
    net.set_snapshots(net.snapshots[snapshot_i_range])


def add_load_shedding(net: pypsa.Network, load_shedding_cost: float) -> None:
    net.add(
        "Generator",
        net.buses.index + "_load_shedding",
        bus=net.buses.index,
        p_nom=1e6,
        marginal_cost=load_shedding_cost,
        carrier="load-shedding",
    )
