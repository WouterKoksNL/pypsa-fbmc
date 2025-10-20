import pypsa
import pickle
from enum import Enum 


from .scigrid_de import create_scigrid_case
from .basic_three_node import create_basic_three_node_case
from .double_three_node_link import create_double_three_node_link_case
from .double_three_node_transformer import create_double_three_node_transformer_case
from .pypsa_eur_central_northern import create_pypsa_eur_central_northern_case
from .double_three_node_line import create_double_three_node_line_case
from .double_three_node_link_and_line import create_double_three_node_link_and_line_case

class Cases(Enum):
    SCIGRID_DE = 'scigrid-de'
    BASIC_THREE_NODE = 'basic-three-node'
    DOUBLE_THREE_NODE_LINK = 'double-three-node-link'
    DOUBLE_THREE_NODE_LINE = 'double-three-node-line'
    DOUBLE_THREE_NODE_TRANSFORMER = 'double-three-node-transformer'
    PYPSA_EUR_CENTRAL_NORTHERN = 'pypsa-eur-central-northern'
    DOUBLE_THREE_NODE_LINK_AND_LINE = 'double-three-node-link-and-line'


CASE_FUNCTION_MAP = {
    Cases.SCIGRID_DE: create_scigrid_case,
    Cases.BASIC_THREE_NODE: create_basic_three_node_case,
    Cases.DOUBLE_THREE_NODE_LINK: create_double_three_node_link_case,
    Cases.DOUBLE_THREE_NODE_LINE: create_double_three_node_line_case,
    Cases.DOUBLE_THREE_NODE_TRANSFORMER: create_double_three_node_transformer_case,
    Cases.PYPSA_EUR_CENTRAL_NORTHERN: create_pypsa_eur_central_northern_case,
    Cases.DOUBLE_THREE_NODE_LINK_AND_LINE: create_double_three_node_link_and_line_case,
}


def create_case(case, load_case_flag=True, save_case_flag=True):
    case_name = case.value

    if load_case_flag:
        output = load_case(case_name)
    else:
        output = _create_case(case)
    if save_case_flag:
        save_case(case_name, output)
    return output

def _create_case(case):
    if case in CASE_FUNCTION_MAP:
        case_creation_function = CASE_FUNCTION_MAP[case]
        output = case_creation_function()
    else:
        raise ValueError(f"Unknown case: {case}")
    return output


def load_case(case_name):
    zonal_net = pypsa.Network(f'input_networks/{case_name}_zonal.nc')
    nodal_net = pypsa.Network(f'input_networks/{case_name}_nodal.nc')
    with open(f'input_networks/{case_name}_gsk.json', 'r') as f:
        gsk_dict = pickle.load(f)
    output = {
        'case_name': case_name,
        'zonal_net': zonal_net, 
        'nodal_net': nodal_net,
        'gsk_dict': gsk_dict
    }
    return output


def save_case(case_name, output):
    output['zonal_net'].export_to_netcdf(f'input_networks/{case_name}_zonal.nc')
    output['nodal_net'].export_to_netcdf(f'input_networks/{case_name}_nodal.nc')
    
    if 'gsk_dict' in output.keys():
        with open(f'input_networks/{case_name}_gsk.pkl', 'wb') as f:
            pickle.dump(output['gsk_dict'], f)
