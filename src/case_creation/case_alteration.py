import logging
from typing import Any


from .utils import select_snapshot
from .unit_commitment import apply_unit_commitment_data



def select_snapshots(
        output, 
        snapshot_i_range
    ):
    select_snapshot(output['zonal_net'], snapshot_i_range)
    select_snapshot(output['nodal_net'], snapshot_i_range)
    if 'gsk_dict' in output and output['gsk_dict'] is not None:
            output['gsk_dict'] = {snapshot: output['gsk_dict'][snapshot] for snapshot in output['zonal_net'].snapshots}

def apply_uc(output, use_unit_commitment=False, unit_commitment_path=None):
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



def remove_links(output, remove_zonal_links=True, remove_nodal_links=True):
    if remove_zonal_links and 'zonal_net' in output and hasattr(output['zonal_net'], 'links'):
        output['zonal_net'].remove('Link', output['zonal_net'].links.index)
    if remove_nodal_links and 'nodal_net' in output and hasattr(output['nodal_net'], 'links'):
        output['nodal_net'].remove('Link', output['nodal_net'].links.index)
    return output


