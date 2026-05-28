import pypsa
import pickle
from enum import Enum 
import logging
from typing import Any

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
from src.config import FBMCConfig

from .utils import add_load_shedding


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



def create_case(case: str | Cases, load_case_flag=True, save_case_flag=True, **kwargs):
    if type(case) is str:
        case = Cases(case)
    case_name = case.value + (f"-{kwargs.get('variation', '')}" if 'variation' in kwargs else '')

    if load_case_flag:
        output = load_case(case_name)
    else:
        output = _create_case(case, **kwargs)

    if save_case_flag:
        save_case(case_name, output)
    return output

def _create_case(case: Cases, **kwargs):
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



def alter_case_workflow(output: dict[str, Any], case_alteration_kwargs: dict[str, Any]):
    from src.case_creation.case_alteration import select_snapshots, apply_uc, remove_links
    snapshots = case_alteration_kwargs.get('snapshot_i_range', None)
    if snapshots is not None:
        select_snapshots(
            output,
            case_alteration_kwargs.get('snapshot_i_range', None)
        )
    if case_alteration_kwargs.get('use_unit_commitment', False):
        apply_uc(
            output=output,
            use_unit_commitment=True,
            unit_commitment_path=case_alteration_kwargs.get('unit_commitment_path')
        )
    # Remove links if requested
    if case_alteration_kwargs.get('remove_links', False):
        remove_zonal = case_alteration_kwargs.get('remove_zonal_links', False)
        remove_nodal = case_alteration_kwargs.get('remove_nodal_links', False)
        remove_links(output, remove_zonal_links=remove_zonal, remove_nodal_links=remove_nodal)
    
    if case_alteration_kwargs.get('load_water_values', False):
        water_values_path = case_alteration_kwargs.get('water_values_path', None)
        soc_path = case_alteration_kwargs.get('soc_path', None)
        if water_values_path is not None:
            import pandas as pd
            water_values = pd.read_csv(water_values_path, index_col=0, parse_dates=True)
            soc = pd.read_csv(soc_path, index_col=0, parse_dates=True)

            zonal_net = output['zonal_net']
            nodal_net = output['nodal_net']

            # zonal_net.storage_units.loc[:, 'marginal_cost'] = water_values.loc[zonal_net.snapshots[-1]]
            # nodal_net.storage_units.loc[:, 'marginal_cost'] = water_values.loc[nodal_net.snapshots[-1]]
            
            # zonal_net.storage_units.loc[:, 'state_of_charge_initial'] = soc.loc[zonal_net.snapshots[0]]
            # nodal_net.storage_units.loc[:, 'state_of_charge_initial'] = soc.loc[nodal_net.snapshots[0]]
            if False: # not currently working correctly 
                zonal_net.storage_units.loc[:, 'cyclic_state_of_charge'] = False
                nodal_net.storage_units.loc[:, 'cyclic_state_of_charge'] = False
                fsn, lsn = zonal_net.snapshots[0], zonal_net.snapshots[-1]
                first_and_last = [fsn, lsn]
                zonal_net.storage_units_t.state_of_charge_set.loc[first_and_last, soc.columns] = soc.loc[first_and_last].values
                nodal_net.storage_units_t.state_of_charge_set.loc[first_and_last, soc.columns] = soc.loc[first_and_last].values
                zonal_net.storage_units.loc[soc.columns, 'state_of_charge_initial'] = soc.loc[fsn].values
                nodal_net.storage_units.loc[soc.columns, 'state_of_charge_initial'] = soc.loc[fsn].values
    
    if case_alteration_kwargs.get('add_zonal_load_shedding', False):
        load_shedding_cost = case_alteration_kwargs.get("load_shedding_cost", None)
        # add_load_shedding(output['nodal_net'], load_shedding_cost=load_shedding_cost)
        add_load_shedding(output['zonal_net'], load_shedding_cost=load_shedding_cost)

    return output