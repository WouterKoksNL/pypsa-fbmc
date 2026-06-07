import pypsa
import pandas as pd
from typing import Any
import xarray as xr

from .security_constrained import get_subnetwork_bodf
from .ram import calculate_ram
from .ptdf import calculate_zonal_ptdf, get_subnetwork_ptdf_non_security_constrained, calc_subnet_ptdf_security_constrained
from ...settings import FBMCConfig
from fbmc.core.derived_parameters.base_case import get_base_flows_subnet_non_security_constrained, calc_base_net_positions_subnet, get_base_flows_subnet_security_constrained
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

    if config.add_security_constraints:
        bodf = get_subnetwork_bodf(sub_network, cnecs, config.security_constraint_bodf_size_threshold)
        nodal_ptdf = calc_subnet_ptdf_security_constrained(sub_network, bodf, bodf_columnwise_matrix_size_limit=config.security_constraint_bodf_columnwise_matrix_size_limit)
        base_flows_subnet = get_base_flows_subnet_security_constrained(sub_network, bodf)
        cnecs = nodal_ptdf.coords['cnec']  # Update CNECs to match the potentially reduced set in apply_security_param_changes
    else:
        nodal_ptdf = get_subnetwork_ptdf_non_security_constrained(sub_network, cnecs)
        base_flows_subnet = get_base_flows_subnet_non_security_constrained(sub_network, cnecs)


    base_net_positions_subnet = calc_base_net_positions_subnet(sub_network)

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