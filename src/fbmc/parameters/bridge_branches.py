from PyPSA import pypsa
import pandas as pd
import networkx as nx



def find_bridges_sub_network(sub_network: pypsa.SubNetwork) -> pd.MultiIndex:
    """
    Identify bridges in the sub-network. A bridge is a line or transformer that, if removed, would increase the number of connected components in the network.
    These cannot be included as outages considered for CNECs since their outage would disconnect the network (BODF value of NaN).

    Parameters
    ----------
    sub_network : pypsa.SubNetwork

    Returns
    -------
    pd.MultiIndex
        MultiIndex of bridges in the network. (First level: branch type, second level: branch name)
    """

    G = sub_network.graph()
    bridges = list(nx.bridges(G))
    # find all components connecting the bus0 and bus1 pairs of the bridges
    bus0 = sub_network.branches().bus0
    bus1 = sub_network.branches().bus1
    
    bridge_branches = pd.MultiIndex(levels=[[], []], codes=[[], []])
    for u, v in bridges:
        mask = ((bus0 == u) & (bus1 == v)) | ((bus0 == v) & (bus1 == u))
        bridge_branches = bridge_branches.append(sub_network.branches().index[mask])  
    return bridge_branches

def find_bridges_network(net) -> pd.MultiIndex:
    """Loops over all sub-networks (connected AC) in a net and returns the bridge branches for each using the find_bridges_sub_network function.

    Args:
        net (pypsa.Network)

    Returns:
        pd.MultiIndex: MultiIndex of bridges in the network. (First level: branch type, second level: branch name)
    """
    bridge_branches = pd.MultiIndex(levels=[[], []], codes=[[], []])
    for subnet in net.sub_networks.obj:
        bridge_branches = bridge_branches.append(find_bridges_sub_network(subnet))
    return bridge_branches