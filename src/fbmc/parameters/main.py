import pypsa
import pandas as pd
from typing import Any

from .cnec import cnec_router
from .ram import calculate_ram
from .ptdf import calculate_zonal_ptdf, get_subnetwork_ptdf
from ..config import FBMCConfig
from .base_case import calc_base_net_positions, get_base_flows
from .security_constrained import apply_security_param_changes, calculate_zonal_ptdf_advanced_hybrid

def get_base_parameters(sub_network: pypsa.SubNetwork, config: FBMCConfig):
    nodal_ptdf = get_subnetwork_ptdf(sub_network)
    net_positions_base_case = calc_base_net_positions(sub_network, config.use_zero_base_flows_flag)
    base_flows = get_base_flows(sub_network, config.use_zero_base_flows_flag)  # shape: (snapshots, branches)
    return nodal_ptdf, net_positions_base_case, base_flows


@dataclass
class FBMCParameters:
    upper_ram_dict: dict[Any, pd.DataFrame]
    lower_ram_dict: dict[Any, pd.DataFrame]
    z_ptdf_dict: dict[Any, pd.DataFrame]
    cnecs: pd.Series | pd.MultiIndex


def calculate_fbmc_parameters(
    sub_network: pypsa.SubNetwork,
    gsk: dict[Any, pd.DataFrame], 
    config: FBMCConfig = FBMCConfig(),
) -> FBMCParameters:
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
    nodal_ptdf, net_positions_base_case, base_flows = get_base_parameters(sub_network, config)

    cnecs = cnec_router(sub_network, config)

    if config.add_security_constraints:
        nodal_ptdf, base_flows = apply_security_param_changes(sub_network, cnecs, nodal_ptdf, base_flows)

    z_ptdf_dict = {
        snapshot: calculate_zonal_ptdf(nodal_ptdf, gsk_snapshot, cnecs)
        for snapshot, gsk_snapshot in gsk.items()
    }

    upper_ram, lower_ram = calculate_ram(
        sub_network, 
        z_ptdf_dict, 
        base_flows, 
        reliability_margin_factor=config.reliability_margin_factor, 
        net_positions_base_case=net_positions_base_case
        )

    fbmc_parameters = FBMCParameters(   
        upper_ram_dict=upper_ram,
        lower_ram_dict=lower_ram,
        z_ptdf_dict=z_ptdf_dict,
        cnecs=cnecs
    )
    return fbmc_parameters