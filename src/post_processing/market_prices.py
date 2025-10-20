import linopy as lp
import pandas as pd 


def calculate_zonal_prices(zones, snapshots, z_ptdf_dict: dict[str], model: lp.Model):
    """Calculate zonal prices from the dual variables of the model constraints.

    Parameters
    ----------
    z_ptdf_dict : dict
        Dictionary containing the PTDF matrices for each zone.
    model : lp.Model
        The optimization model containing the constraints.

    Returns
    -------
    dict
        A dictionary with zonal prices for each zone.
    """
    zonal_prices_full = pd.DataFrame(index=snapshots, columns=zones)
    
    for sub_network, z_ptdf in z_ptdf_dict.items():
        subnet_zones = z_ptdf.coords['Zone'].values
        # Get the dual variables for the constraints
        zonal_balance_dual = model.constraints[f'Zonal_balance-subnet-{sub_network}'].dual
        cnec_upper_ram_dual = model.constraints[f'CNEC-upper-RAM-subnet-{sub_network}'].dual
        cnec_lower_ram_dual = model.constraints[f'CNEC-lower-RAM-subnet-{sub_network}'].dual
        # Calculate the zonal prices

        zonal_price = zonal_balance_dual + (z_ptdf * cnec_upper_ram_dual).sum(dim='cnec') +  (z_ptdf * cnec_lower_ram_dual).sum(dim='cnec')
        # TODO: include lower RAM
        zonal_prices_full.loc[:, subnet_zones] = zonal_price.to_pandas()

    return zonal_prices_full
    