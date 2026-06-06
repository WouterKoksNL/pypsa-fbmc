import pypsa
import pandas as pd
from typing import Any
import xarray as xr


from .input.cnec import cnec_router
from .derived.ram import calculate_ram
from .derived.ptdf import calculate_zonal_ptdf, get_subnetwork_ptdf
from ...settings import FBMCConfig
from fbmc.core.parameters.derived.base_case import get_base_flows_subnet, calc_base_net_positions_subnet
from .derived.security_constrained import apply_security_param_changes
from ...types import SubnetFBMCParameters
from ...settings import BaseCaseStrategy

def calculate_fbmc_parameters_subnet(
    sub_network: pypsa.SubNetwork,
    gsk: dict[Any, pd.DataFrame], 
    config: FBMCConfig,
    cnecs: xr.Coordinates,
) -> SubnetFBMCParameters:
    """Add security constraints to zonal network.

    This ensures that no branch is overloaded even given the branch outages.

    Parameters
    ----------
    sub_network : pypsa.SubNetwork
        The sub-network to calculate security constrainted parameters for. 
    gsk : dict
        Generation shift key mapping for each snapshot. Must contain at least the buses and zones in the subnetwork. 
    config : FBMCConfig
        Configuration object for FBMC parameters.
    Returns
    -------
    FBMCParameters
        Dataclass containing upper and lower RAM, zPTDF and CNECs.
    """
    if sub_network.buses_i().size < 3:
        raise NotImplementedError("Sub-networks with less than 3 buses are not supported.")

    base_flows_subnet = get_base_flows_subnet(sub_network)
    base_net_positions_subnet = calc_base_net_positions_subnet(sub_network)

    nodal_ptdf = get_subnetwork_ptdf(sub_network)


    if config.add_security_constraints:
        nodal_ptdf, base_flows_subnet = apply_security_param_changes(
            sub_network,
            cnecs,
            nodal_ptdf,
            base_flows_subnet,
            bodf_size_threshold=config.security_constraint_bodf_size_threshold,
            bodf_columnwise_matrix_size_limit=config.security_constraint_bodf_columnwise_matrix_size_limit,
        )
        cnecs = nodal_ptdf.coords['cnec']  # Update CNECs to match the potentially reduced set in apply_security_param_changes
    else:
        
        # filter on cnecs
        nodal_ptdf = nodal_ptdf.sel(branch=cnecs['branch'])
        base_flows_subnet = base_flows_subnet.sel(branch=cnecs['branch'])
        nodal_ptdf = nodal_ptdf.assign_coords(cnec=('branch', cnecs['branch'].values)).swap_dims({"branch": "cnec"})  
        base_flows_subnet = base_flows_subnet.assign_coords(cnec=('branch', cnecs['branch'].values)).swap_dims({"branch": "cnec"})

    gsk_subnet = xr.DataArray(
        data=list(gsk.values()),
        coords={
            'snapshot': list(gsk.keys()),
            'Zone': gsk[list(gsk.keys())[0]].index,
            'Bus': gsk[list(gsk.keys())[0]].columns
        },
        dims=['snapshot', 'Zone', 'Bus']
    )
    gsk_subnet = gsk_subnet.sel(Bus=nodal_ptdf.coords['Bus'],
                                 Zone=sub_network.buses().zone_name.unique()) # Align GSK to PTDF columns based on bus names

    z_ptdf = calculate_zonal_ptdf(nodal_ptdf, gsk_subnet, cnecs)
    # z_ptdf_dics


    upper_ram, lower_ram = calculate_ram(
        sub_network, 
        z_ptdf, 
        base_flows_subnet, 
        reliability_margin_factor=config.reliability_margin_factor, 
        net_positions_base_case=base_net_positions_subnet
        )
    
    zones = sub_network.buses().zone_name.unique()
    fbmc_parameters = SubnetFBMCParameters(   
        upper_ram_dict=upper_ram,
        lower_ram_dict=lower_ram,
        z_ptdf_dict=z_ptdf,
        cnecs=cnecs,
        zones=zones,
    )

    return fbmc_parameters