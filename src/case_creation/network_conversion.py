"""
Functions for converting between nodal and zonal network representations.
"""

import pandas as pd
from PyPSA import pypsa
import numpy as np
from typing import Optional


def copy_net(oldnet, time_dependent_attrs={}):
    net = pypsa.Network()
     # --- Copy static components ---
    net.add('Bus', oldnet.buses.index, **oldnet.buses)
    net.add('Line', oldnet.lines.index, **oldnet.lines)
    net.add('Transformer', oldnet.transformers.index, **oldnet.transformers)
    net.add('StorageUnit', oldnet.storage_units.index, **oldnet.storage_units)
    net.add('Link', oldnet.links.index, **oldnet.links)
    net.add('Generator', oldnet.generators.index, **oldnet.generators)
    net.add('Load', oldnet.loads.index, **oldnet.loads)
    net.add('Carrier', oldnet.carriers.index, **oldnet.carriers)
    net.set_snapshots(oldnet.snapshots)

    for attr_name in time_dependent_attrs:
        for attr in time_dependent_attrs[attr_name]:
            if not oldnet.__getattribute__(attr_name)[attr].empty:
                net.__getattribute__(attr_name)[attr] = oldnet.__getattribute__(attr_name)[attr].copy()

    return net


def nodal_to_zonal(n, bus_zone_map: pd.Series, interzonal_cap_factor: float=0.7, add_ntc_flag: bool=False):
    """
    Converts a nodal PyPSA-Eur network to a zonal network by:
    - Adding one bus per zone
    - Remapping all one-port components to zones
    - Removing all branch components (lines, links transformers)
    - Adding a single high-capacity link between each pair of connected zones
    based on the sum of capacities of inter-zonal lines and links in the original network
    """
    
    # Check if zone mapping exists
    if bus_zone_map.isna().any():
        raise ValueError(f"Some buses do not have a zone assigned: {bus_zone_map[bus_zone_map.isna()]}")


     # Remove the model if it exists to avoid issues during copying
     # Try-except needed because hasattr(n, 'model') raises an error if model not created. 
    try:
        if hasattr(n, 'model'):
            del(n.model) 
    except ValueError: 
        pass

    # Copy the original nodal network
    zonal_net = n.copy()

    # Store original mapping from nodal bus -> zone

    zones = bus_zone_map.unique()

    # STEP 1: Remap one-port components (generators, loads, storage_units, etc.) to zones
    for c in zonal_net.iterate_components(zonal_net.one_port_components):
        c.df.bus = c.df.bus.map(bus_zone_map)  
    

    # STEP 3: Create a new bus for each zone (at the mean x/y of all buses in that zone)
    for zone_name, buses_zone in n.buses.groupby(bus_zone_map):
        x_zone, y_zone= np.mean(buses_zone.x), np.mean(buses_zone.y)
        zonal_net.add("Bus", zone_name, x=x_zone, y=y_zone) 
    zonal_net.buses.index.name = "Bus"

    # Remove all original nodal buses (i.e. sub-zonal nodes) 
    zonal_net.remove("Bus", zonal_net.buses.index[~np.isin(zonal_net.buses.index, zones)])  

    # STEP 4: Aggregate inter-zonal capacities (lines and DC links)
    if not add_ntc_flag:
        zonal_net.remove('Line', zonal_net.lines.index)
        zonal_net.remove('Transformer', zonal_net.transformers.index)
        zonal_net.links.loc[:, 'bus0'] = zonal_net.links.bus0.map(bus_zone_map)
        zonal_net.links.loc[:, 'bus1'] = zonal_net.links.bus1.map(bus_zone_map)
        internal_links =  zonal_net.links.bus0 == zonal_net.links.bus1
        zonal_net.remove('Link', zonal_net.links.index[internal_links])
    else:
        add_ntcs(zonal_net, n, bus_zone_map, zones, interzonal_cap_factor)
    return zonal_net


def add_ntcs(zonal_net, n, bus_zone_map: pd.Series, zones, interzonal_cap_factor: float=0.7):
    interzonal_cap = pd.DataFrame(0.0, index=zones, columns=zones)
    for i in zones:
        for j in zones:
            if i == j:
                continue
            # Lines (AC): sum s_nom between zones
            mask_lines = (
                ((n.lines.bus0.map(bus_zone_map) == i) & (n.lines.bus1.map(bus_zone_map) == j)) |
                ((n.lines.bus0.map(bus_zone_map) == j) & (n.lines.bus1.map(bus_zone_map) == i))
            )
            # Links (DC): sum p_nom between zones
            mask_links = (
                ((n.links.bus0.map(bus_zone_map) == i) & (n.links.bus1.map(bus_zone_map) == j)) |
                ((n.links.bus0.map(bus_zone_map) == j) & (n.links.bus1.map(bus_zone_map) == i))
            )
            cap = interzonal_cap_factor * n.lines.loc[mask_lines, "s_nom"].sum() + \
                n.links.loc[mask_links, "p_nom"].sum()
            interzonal_cap.loc[i, j] = cap

    # # STEP 2: Remove all branch components (lines, links, transformers)
    for c in zonal_net.iterate_components(zonal_net.branch_components):
        zonal_net.remove(c.name, c.df.index)

    # STEP 5: Add a single bidirectional link between each connected zone pair
    for i in zones:
        for j in zones:
            if i < j and interzonal_cap.loc[i,j] > 0: # avoid duplicates
                zonal_net.add("Link",
                    name=f"{i}---{j}",
                    bus0=i,
                    bus1=j,
                    p_nom=interzonal_cap.loc[i,j],
                    p_min_pu=-1.0,
                    carrier="NTC"
                )

def nodal_to_zonal_nocopy(
    nodal_network: pypsa.Network,
    snapshots: Optional[list[pd.Index]] = None,
    zone_column: str = 'zone_name',
    bidirectional_links: bool = True
) -> pypsa.Network:
 # Validate inputs
    if zone_column not in nodal_network.buses.columns:
        raise ValueError(f"The column '{zone_column}' does not exist in the nodal network's buses")
    
    # Create a new zonal network
    zonal_network = pypsa.Network()
    
    # Set snapshots
    if snapshots is None:
        snapshots = nodal_network.snapshots
    else:
        zonal_network.set_snapshots(snapshots)
    
    # Add zonal buses (one for each unique zone in the nodal network)
    zones = nodal_network.buses[zone_column].unique()
    for zone in zones:
        zonal_network.add("Bus", zone, v_nom=nodal_network.buses.v_nom.mean())
    
    # Move generators to their respective zonal buses
    for gen in nodal_network.generators.itertuples():
        # Get the zone name for this generator's bus
        bus_name = gen.bus
        zone_name = nodal_network.buses.at[bus_name, zone_column]
        
        # Add the generator to the zonal network at its zone
        gen_dict = {col: getattr(gen, col) for col in nodal_network.generators.columns 
                   if col != 'bus' and hasattr(gen, col)}
        gen_dict['bus'] = zone_name  # Use the zone name as the bus
        
        zonal_network.add("Generator", gen.Index, **gen_dict)
    
    # Copy generator time series data if it exists
    for attr_name in nodal_network.generators_t:
        if attr_name != 'p':
            if not nodal_network.generators_t[attr_name].empty:
                zonal_network.generators_t[attr_name] = nodal_network.generators_t[attr_name].copy()
        
    # Move loads to their respective zonal buses
    if not nodal_network.loads.empty:
        for load in nodal_network.loads.itertuples():
            # Get the zone name for this load's bus
            bus_name = load.bus
            zone_name = nodal_network.buses.at[bus_name, zone_column]
            
            # Add the load to the zonal network at its zone
            load_dict = {col: getattr(load, col) for col in nodal_network.loads.columns 
                        if col != 'bus' and hasattr(load, col)}
            load_dict['bus'] = zone_name  # Use the zone name as the bus
            
            zonal_network.add("Load", load.Index, **load_dict)
        
        # Copy load time series data if it exists
        for attr_name in nodal_network.loads_t:
            if attr_name != 'p':
                if not nodal_network.loads_t[attr_name].empty:
                    zonal_network.loads_t[attr_name] = nodal_network.loads_t[attr_name].copy()
        
    # # Calculate the total line capacity between zones and create links
    # zone_connections = {}
    
    # # Loop through all lines and calculate total capacity between zones
    # if not nodal_network.lines.empty:
    #     for line in nodal_network.lines.itertuples():
    #         bus0_zone = nodal_network.buses.at[line.bus0, zone_column]
    #         bus1_zone = nodal_network.buses.at[line.bus1, zone_column]
            
    #         # Skip if the line connects buses in the same zone
    #         if bus0_zone == bus1_zone:
    #             continue
            
    #         # Ensure consistent ordering of zones for dictionary keys
    #         zone_pair = tuple(sorted([bus0_zone, bus1_zone]))
            
    #         # Add capacity to the total for this zone pair
    #         if zone_pair not in zone_connections:
    #             zone_connections[zone_pair] = 0
    #         zone_connections[zone_pair] += line.s_nom
    
    # # Create links between zones with the total capacity
    # for (zone1, zone2), capacity in zone_connections.items():
    #     if bidirectional_links:
    #         # Create bidirectional links (two one-directional links)
    #         zonal_network.add("Link", 
    #                         f"link_{zone1}_{zone2}", 
    #                         bus0=zone1, 
    #                         bus1=zone2, 
    #                         p_nom=capacity,
    #                         p_min_pu=-1 if bidirectional_links else 0)
            
    #         zonal_network.add("Link", 
    #                         f"link_{zone2}_{zone1}", 
    #                         bus0=zone2, 
    #                         bus1=zone1, 
    #                         p_nom=capacity,
    #                         p_min_pu=-1 if bidirectional_links else 0)
    #     else:
    #         # Create a single bidirectional link
    #         zonal_network.add("Link", 
    #                         f"link_{zone1}_{zone2}", 
    #                         bus0=zone1, 
    #                         bus1=zone2, 
    #                         p_nom=capacity,
    #                         p_min_pu=-1)
    
    # Copy carriers from the original network
    if hasattr(nodal_network, 'carriers') and not nodal_network.carriers.empty:
        for carrier in nodal_network.carriers.index:
            if carrier not in zonal_network.carriers.index:
                carrier_data = {col: nodal_network.carriers.at[carrier, col] 
                               for col in nodal_network.carriers.columns 
                               if carrier in nodal_network.carriers.index}
                zonal_network.add('Carrier', carrier, **carrier_data)
    
    return zonal_network