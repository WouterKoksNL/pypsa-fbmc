import xarray as xr
import linopy as lp
import pandas as pd

from ..constraints.fbmc_constraints import (
    create_load_zone_mapping,
    construct_zonal_balance_constraint,
    create_load_zone_mask,
    get_zonal_loads
)
from src.fbmc.parameters.ptdf import convert_zPTDF_to_xarray
from src.fbmc.parameters.flows import convert_RAM_to_xarray




def add_pos_neg_fbmc_constraints(network, zptdf_pos, zptdf_neg, ram_df, net_position_base_case):
    """
    Add FBMC constraints to the network using positive and negative zPTDFs. 
    
    Parameters
    ----------
    network : pypsa.Network
        The PyPSA network to add constraints to.
    zptdf_pos_df : pd.DataFrame or dict of pd.DataFrame
        zPTDF for positive NP changes.
        Either a single DataFrame containing zptdf values (static GSKs),
        or a dictionary of DataFrames with snapshots as keys (snapshot-based GSKs).
    zptdf_neg_df : pd.DataFrame or dict of pd.DataFrame
        zPTDF for negative NP changes.
        Either a single DataFrame containing zptdf values (static GSKs),
        or a dictionary of DataFrames with snapshots as keys (snapshot-based GSKs).
    ram_df : pd.DataFrame
        DataFrame containing RAM values.
    
    Returns
    -------
    pypsa.Network
        The network with added FBMC constraints.
    """
    # xarray conversion
    zptdf_pos_xr = convert_zPTDF_to_xarray(zptdf_pos)
    zptdf_neg_xr = convert_zPTDF_to_xarray(zptdf_neg)
    ram_xr = convert_RAM_to_xarray(ram_df)

    # Retrieve the zonal generation variable
    zonal_generation = network.model.variables["Zone-p"]

    # zonal loads
    load_zone_mapping = create_load_zone_mapping(network.loads)
    zones = network.buses.index.to_list()
    snapshots = network.snapshots.to_list()
    load_zone_mask = create_load_zone_mask(load_zone_mapping, zones)
    zonal_loads = get_zonal_loads(load_zone_mask, network.get_switchable_as_dense('Load', 'p_set'))

    delta_np_pos, delta_np_neg = create_delta_net_position_variables(network)
    # Restrict the load on CNEs by the Remaining Available Margin (RAM)
    net_position = zonal_generation - zonal_loads
    net_position_base_case.columns.name = "Zone"
    delta_np_constraint = construct_delta_np_constraints(net_position, net_position_base_case, delta_np_pos, delta_np_neg, snapshots, zones)
    network.model.add_constraints(delta_np_constraint, name="Delta_Net_Position")
    cne_constraint = construct_pos_neg_cne_constraint(zptdf_pos_xr, zptdf_neg_xr, delta_np_pos, delta_np_neg, ram_xr)
    network.model.add_constraints(cne_constraint, name="CNE-RAM")

    # Ensure the Net Position of all zones adds up to 0
    zonal_balance_constraint = construct_zonal_balance_constraint(zonal_generation, zonal_loads)
    network.model.add_constraints(zonal_balance_constraint, name="Zonal_balance")

    
    return network

def create_delta_net_position_variables(network):
    """
    Create Linopy variables for the delta net position.
    
    Parameters
    ----------
    zonal_generation : lp.Variable
        Linopy variable for zonal generation with dimensions [Zone, snapshot].
    zonal_loads : xr.DataArray
        DataArray with zonal loads with dimensions [Zone, snapshot].
    net_position_base_case : xr.DataArray
        Base case net position with dimensions [Zone, snapshot].
        
    Returns
    -------
    tuple of lp.Variable
        Variables for positive and negative delta net positions.
    """
    # Calculate the net position (generation minus load)

    zones = network.buses.index.to_list()
    snapshots = network.snapshots.to_list()
    # Create variables for positive and negative delta net positions
    delta_np_pos = network.model.add_variables(
        name="Delta_NP_pos",
        coords={"snapshot": snapshots, "Zone": zones},  # Changed order
        dims=["snapshot", "Zone"],  # Changed order and capitalization
        lower=0
        )
    delta_np_neg = network.model.add_variables(
        name="Delta_NP_neg",
        coords={"snapshot": snapshots, "Zone": zones},  # Changed order
        dims=["snapshot", "Zone"],  # Changed order and capitalization
        lower=0
        )


    # binary_indicator = network.model.add_variables(
    #     name='Binary_indicator',
    #     coords={"snapshot": snapshots, "Zone": zones},
    #     dims=["snapshot", "Zone"],  # Changed order and capitalization
    #     binary=True,
    # )
    # exclusion_constraints = construct_exclusion_constraints(delta_np_pos, delta_np_neg, binary_indicator, snapshots, zones)
    # network.model.add_constraints(
    #     exclusion_constraints[0],
    #     name="Exclusion_Delta_P_1",
    # # )
    # network.model.add_constraints(
    #     exclusion_constraints[1],
    #     name="Exclusion_Delta_P_2",
    # )

    return delta_np_pos, delta_np_neg

def construct_exclusion_constraints(
    delta_np_pos: lp.Variable,
    delta_np_neg: lp.Variable,
    binary_indicator: lp.Variable,
    snapshots, 
    zones,
    big_m: float = 1e6,
):
    """
    Enforce mutual exclusivity between delta_np_pos and delta_np_neg using a binary variable.
    Ensures only one of them can be positive at a time.

    Parameters
    ----------
    delta_np_pos : lp.Variable
        Positive net position deviation variable (≥ 0).
    delta_np_neg : lp.Variable
        Negative net position deviation variable (≥ 0).
    binary_indicator : lp.Variable
        Binary variable (0 or 1).
    big_m : float, optional
        Big-M constant to enforce constraint, default is 1e6.

    Returns
    -------
    list of linopy.Expression
        Two constraints as linopy expressions.
    """
    # Use linopy expression to construct 1 - binary_indicator


    # one = xr.DataArray(
    #     data=1,
    #     coords={"snapshot": snapshots, "Zone": zones},  # Changed order
    #     dims=["snapshot", "Zone"],  # Changed order and capitalization
    # )
    constraints = []
    for snap in snapshots:
        for zone in zones:
            binary = binary_indicator.sel(snapshot=snap, Zone=zone)
            dnp_pos = delta_np_pos.sel(snapshot=snap, Zone=zone)
            dnp_neg = delta_np_neg.sel(snapshot=snap, Zone=zone)
            # Constraint for positive delta net position
            constraint_pos = dnp_pos <= binary * big_m
            # Constraint for negative delta net position
            constraint_neg = dnp_neg <= (1 - binary) * big_m
            constraints.extend[constraint_pos, constraint_neg]

    return constraints

def construct_delta_np_constraints(net_position, net_position_base_case, delta_np_pos, delta_np_neg, snapshots, zones):
    all_lhs_list = []
    for snapshot in snapshots:
        lhs_list = []
        for zone in zones:
            delta_np_pos_slice = delta_np_pos.sel(snapshot=snapshot, Zone=zone)
            delta_np_neg_slice = delta_np_neg.sel(snapshot=snapshot, Zone=zone)
            np_slice = net_position.sel(snapshot=snapshot, Zone=zone) 
            lhs = np_slice - delta_np_pos_slice + delta_np_neg_slice 
            lhs = np_slice - delta_np_pos_slice + delta_np_neg_slice 
            lhs_list.append(lhs)
        zone_term = lp.merge(lhs_list, dim="Zone")
        all_lhs_list.append(zone_term)
    all_lhs = lp.merge(all_lhs_list, dim="snapshot")
    all_constraints = all_lhs == xr.DataArray(
        data=net_position_base_case,
        coords={"snapshot": snapshots, "Zone": zones},  # Changed order
        dims=["snapshot", "Zone"],  # Changed order and capitalization
    )
                        # Combine flow terms for all snapshots for this CNE
        # zone_term = lp.merge(constraint, dim="Zone")
        # cne_lhs_list.append(zone_term)
    
    return all_constraints

def construct_pos_neg_cne_constraint(
        zptdf_pos: xr.DataArray, 
        zptdf_neg: xr.DataArray,
        delta_np_pos: lp.Variable,
        delta_np_neg: lp.Variable,
        RAM: xr.DataArray,
    ):
    """
    Create the constraint restricting the flow on CNEs by the Remaining Available Margin (RAM).
    
    This function handles both snapshot-dependent and static zPTDFs.
    
    Parameters
    ----------
    zPTDF : xr.DataArray
        Either a 2D DataArray with dimensions [CNE, Zone] for static zPTDF,
        or a 3D DataArray with dimensions [snapshot, CNE, Zone] for snapshot-dependent zPTDF.
    total_zonal_generation : lp.Variable
        Linopy variable for zonal generation with dimensions [Zone, snapshot].
    zonal_loads : xr.DataArray
        DataArray with zonal loads with dimensions [Zone, snapshot].
    RAM : xr.DataArray
        DataArray with RAM values with dimensions [CNE, snapshot].
        
    Returns
    -------
    lp.Constraint
        Constraint ensuring flows on CNEs are within the RAM.
    """
    # Check if zPTDF is snapshot-dependent
    snapshot_dependent = "snapshot" in zptdf_pos.dims
    
    # Get zones that are in both zPTDF and total_zonal_generation
    # zones = [zone for zone in zptdf_pos.coords['Zone'].values if zone in ptdf_pos.indexes['Zone']]
    
    # Get the generation and load for these zones
    # internal_zonal_gen = total_zonal_generation.sel(Zone=zones)
    # internal_zonal_loads = zonal_loads.sel(Zone=zones)
    
    # Calculate net position (generation minus load)
    # net_position = internal_zonal_gen - internal_zonal_loads
    
    # delta_np = net_position - net_position_base_case


    # Handle snapshot-dependent and static zPTDFs differently
    if snapshot_dependent:
        # For snapshot-dependent zPTDF
        cne_lhs_list = []
        
        # Make sure snapshots are aligned
        snapshots = [snap for snap in zptdf_pos.coords['snapshot'].values if snap in RAM.coords['snapshot'].values]
        

        # Calculate the LHS for each CNE

        for cne in zptdf_pos.CNE.values:
            # For each snapshot and CNE, calculate the flow
            flow_terms = []
            for snap in snapshots:
                # Get zPTDF and delta net position for this snapshot and CNE

                ptdf_pos_slice = zptdf_pos.sel(snapshot=snap, CNE=cne)
                delta_np_pos_slice = delta_np_pos.sel(snapshot=snap)   
                ptdf_neg_slice = zptdf_neg.sel(snapshot=snap, CNE=cne)
                delta_np_neg_slice = delta_np_neg.sel(snapshot=snap) 
                flow_terms.append((ptdf_pos_slice * delta_np_pos_slice - ptdf_neg_slice * delta_np_neg_slice).sum(dim="Zone"))
        
            # Combine flow terms for all snapshots for this CNE
            cne_term = lp.merge(flow_terms, dim="snapshot")
            cne_lhs_list.append(cne_term)
    
        # Combine all CNE terms
        cne_lhs = lp.merge(cne_lhs_list, dim="CNE")
        
        # Get corresponding RAM values
        ram_subset = RAM.sel(CNE=zptdf_pos.CNE.values, snapshot=snapshots)
        
        # Create the constraint
        cne_constraint = cne_lhs <= ram_subset
    # else:
    #     # For static zPTDF (original implementation)
    #     cne_lhs_list = []
    #     for cne in zptdf_pos.CNE.values:
    #         term = (zptdf_pos.sel(CNE=cne) * net_position).sum(dim="Zone")
    #         cne_lhs_list.append(term)
        
    #     cne_lhs = lp.merge(cne_lhs_list, dim="CNE")
    #     cne_constraint = cne_lhs <= RAM
    
    return cne_constraint
