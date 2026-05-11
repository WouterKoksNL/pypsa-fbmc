
import pypsa


def remove_zero_capacity_branches(net: pypsa.Network):
    net.remove('Line', net.lines.index[net.lines.s_nom < 1e-5])
    net.remove('Transformer', net.transformers.index[net.transformers.s_nom < 1e-5])
    net.remove('Link', net.links.index[net.links.p_nom < 1e-5])



def remove_zero_capacity_links(zonal_net: pypsa.Network):
    zonal_net.remove('Link', zonal_net.links.index[zonal_net.links.p_nom < 1e-5])