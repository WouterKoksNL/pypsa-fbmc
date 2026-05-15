from PyPSA import pypsa
from src.paths import get_case_input_dir


def create_custom_case(case_name="custom"):
    case_dir = get_case_input_dir(case_name)
    nodal_net = pypsa.Network(case_dir / "nodal.nc")
    zonal_net = pypsa.Network(case_dir / "zonal.nc")

    output = {
        'zonal_net': zonal_net,
        'nodal_net': nodal_net, 
    }
    return output