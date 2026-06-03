from fbmc.case_creation.network_conversion import nodal_to_zonal
from fbmc.paths import get_case_input_dir
import sys
import pypsa

# get argv
case_name = sys.argv[1]
case_dir = get_case_input_dir(case_name)

nodal_net = pypsa.Network(case_dir / 'nodal.nc')
bus_zone_map = nodal_net.buses.country
zonal_net = nodal_to_zonal(nodal_net.copy(), bus_zone_map=bus_zone_map)
zonal_net.export_to_netcdf(case_dir / 'zonal.nc')