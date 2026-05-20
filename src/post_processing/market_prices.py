import linopy as lp
import pandas as pd 


def calculate_zonal_prices(zones, snapshots, z_ptdf_dict: dict[str], model: lp.Model, sn_slack_zone_map: pd.Series) -> pd.DataFrame:
    """Calculate zonal prices from the dual variables of the model constraints.

    Parameters
    ----------
    z_ptdf_dict : dict
        Dictionary containing the PTDF matrices for each zone.
    model : lp.Model
        The optimization model containing the constraints.
    sn_slack_zone_map : pd.Series
        A Series mapping sub_networks to their respective slack zones.
    Returns
    -------
    pd.DataFrame       
        A DataFrame with snapshots as index and zones as columns, containing the zonal prices.

    """

    slack_zone_duals = model.constraints['Zone-definition'].dual.sel(Zone=sn_slack_zone_map.values)

    zonal_prices_full = pd.DataFrame(index=snapshots, columns=zones)
    
    for sub_network, z_ptdf in z_ptdf_dict.items():
        slack_zone_dual_ser = slack_zone_duals.sel(Zone=sn_slack_zone_map[sub_network])  # timeseries 
        subnet_zones = z_ptdf.coords['Zone'].values
        # Get the dual variables for the constraints
        # zonal_balance_dual = model.constraints[f'Zonal_balance-subnet-{sub_network}'].dual
        cnec_upper_ram_dual = model.constraints[f'CNEC-upper-RAM-subnet-{sub_network}'].dual
        cnec_lower_ram_dual = model.constraints[f'CNEC-lower-RAM-subnet-{sub_network}'].dual
        zonal_price = - slack_zone_dual_ser + (z_ptdf * cnec_upper_ram_dual).sum(dim='cnec') - (z_ptdf * cnec_lower_ram_dual).sum(dim='cnec')

        zonal_prices_full.loc[:, subnet_zones] = zonal_price.to_pandas()

    return zonal_prices_full
    