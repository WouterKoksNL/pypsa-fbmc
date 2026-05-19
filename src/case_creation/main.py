import pypsa
import pickle
from enum import Enum 
import logging


from .scigrid_de import create_scigrid_case
from .basic_three_node import create_basic_three_node_case
from .double_three_node_link import create_double_three_node_link_case
from .double_three_node_transformer import create_double_three_node_transformer_case
from .pypsa_eur_central_northern import create_pypsa_eur_central_northern_case
from .double_three_node_line import create_double_three_node_line_case
from .double_three_node_link_and_line import create_double_three_node_link_and_line_case
from .four_node import create_four_node
from .pypsa_eur_ua import create_pypsa_eur_ua_case
from .linear import create_linear_case
from .three_node_redispatch import create_three_node_redispatch_case
from .custom import create_custom_case
from src.case_creation.advanced_hybrid_check import create_advanced_hybrid_check
from src.paths import get_case_input_dir
from .utils import select_snapshot
from .unit_commitment import apply_unit_commitment_data

logging.basicConfig(level=logging.INFO)

class Cases(Enum):
    SCIGRID_DE = 'scigrid-de'
    BASIC_THREE_NODE = 'basic-three-node'
    DOUBLE_THREE_NODE_LINK = 'double-three-node-link'
    DOUBLE_THREE_NODE_LINE = 'double-three-node-line'
    DOUBLE_THREE_NODE_TRANSFORMER = 'double-three-node-transformer'
    PYPSA_EUR_CENTRAL_NORTHERN = 'pypsa-eur-central-northern'
    DOUBLE_THREE_NODE_LINK_AND_LINE = 'double-three-node-link-and-line'
    FOUR_NODE = 'four-node'
    ADVANCED_HYBRID_CHECK = 'advanced-hybrid-check'
    PYPSA_EUR_UA = 'pypsa-eur-ua'
    LINEAR = 'linear'
    THREE_NODE_REDISPATCH = 'three-node-redispatch'
    CUSTOM = 'custom'


CASE_FUNCTION_MAP = {
    Cases.SCIGRID_DE: create_scigrid_case,
    Cases.BASIC_THREE_NODE: create_basic_three_node_case,
    Cases.DOUBLE_THREE_NODE_LINK: create_double_three_node_link_case,
    Cases.DOUBLE_THREE_NODE_LINE: create_double_three_node_line_case,
    Cases.DOUBLE_THREE_NODE_TRANSFORMER: create_double_three_node_transformer_case,
    Cases.PYPSA_EUR_CENTRAL_NORTHERN: create_pypsa_eur_central_northern_case,
    Cases.DOUBLE_THREE_NODE_LINK_AND_LINE: create_double_three_node_link_and_line_case,
    Cases.FOUR_NODE: create_four_node,
    Cases.ADVANCED_HYBRID_CHECK: create_advanced_hybrid_check,
    Cases.PYPSA_EUR_UA: create_pypsa_eur_ua_case,
    Cases.LINEAR: create_linear_case,
    Cases.THREE_NODE_REDISPATCH: create_three_node_redispatch_case,
    Cases.CUSTOM: create_custom_case, 
}



def create_case(case, load_case_flag=True, save_case_flag=True, **kwargs):

    case_name = case.value + (f"-{kwargs.get('variation', '')}" if 'variation' in kwargs else '')
    snapshot_i_range = kwargs.get('snapshot_i_range', None)
    use_unit_commitment = kwargs.get('use_unit_commitment', False)
    unit_commitment_path = kwargs.get('unit_commitment_path', None)
    kwargs.pop('snapshot_i_range', None)
    kwargs.pop('use_unit_commitment', None)
    kwargs.pop('unit_commitment_path', None)
    load_water_values = kwargs.pop('load_water_values', False)
    water_values_path = kwargs.pop('water_values_path', None)
    if load_case_flag:
        output = load_case(case_name)
    else:
        output = _create_case(case, **kwargs)

    if snapshot_i_range is not None:
        select_snapshot(output['zonal_net'], snapshot_i_range)
        select_snapshot(output['nodal_net'], snapshot_i_range)
        if 'gsk_dict' in output and output['gsk_dict'] is not None:
                output['gsk_dict'] = {snapshot: output['gsk_dict'][snapshot] for snapshot in output['zonal_net'].snapshots}

    if use_unit_commitment:
        logging.info(f"Applying unit commitment data from {unit_commitment_path} to networks.")
        apply_unit_commitment_data(
            output['nodal_net'],
            unit_commitment_path=unit_commitment_path,
        )
        apply_unit_commitment_data(
            output['zonal_net'],
            unit_commitment_path=unit_commitment_path,
        )
    


    # Optionally load water values if specified in case_kwargs

    if load_water_values and water_values_path:
        import pandas as pd
        try:
            water_values = pd.read_csv(water_values_path, index_col=0)
            
            logging.info(f"Loaded water values from {water_values_path}")
        except Exception as e:
            logging.warning(f"Failed to load water values from {water_values_path}: {e}")
        breakpoint()
    if save_case_flag:
        save_case(case_name, output)
    return output

def _create_case(case, **kwargs):
    if case in CASE_FUNCTION_MAP:
        case_creation_function = CASE_FUNCTION_MAP[case]
        output = case_creation_function(**kwargs)
    else:
        raise ValueError(f"Unknown case: {case}")
    return output


def load_case(case_name):
    case_dir = get_case_input_dir(case_name)
    zonal_net = pypsa.Network(case_dir / 'zonal.nc')
    nodal_net = pypsa.Network(case_dir / 'nodal.nc')

    # first check if gsk file exists, if not, set gsk to None
    gsk_path = case_dir / 'gsk.pkl'
    gsk_dict = None
    if gsk_path.exists():
        with open(gsk_path, 'rb') as f:
            gsk_dict = pickle.load(f)

    output = {
        'case_name': case_name,
        'zonal_net': zonal_net, 
        'nodal_net': nodal_net,
        'gsk_dict': gsk_dict
    }
    return output


def save_case(case_name, output, 
    export_path=None):
    if export_path is None:
        export_path = get_case_input_dir(case_name)
        export_path.mkdir(parents=True, exist_ok=True)

    output['zonal_net'].export_to_netcdf(export_path / 'zonal.nc')
    output['nodal_net'].export_to_netcdf(export_path / 'nodal.nc')

    if 'gsk_dict' in output.keys():
        with open(export_path / 'gsk.pkl', 'wb') as f:
            pickle.dump(output['gsk_dict'], f)
