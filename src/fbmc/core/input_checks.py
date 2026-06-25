import logging
from collections.abc import Sequence

import pypsa

from fbmc.enums import CNECStrategy

logging.basicConfig(level=logging.INFO)

def check_reactance(nodal_net):
    if ((nodal_net.lines.x <= 0) & (nodal_net.lines.type == "")).any():
        raise ValueError("Lines with non-positive reactance found.")
    if ((nodal_net.transformers.x <= 0) & (nodal_net.transformers.type == "")).any():
        raise ValueError("Transformers with non-positive reactance found.")

def check_no_lines_or_transformers_in_zonal_net(zonal_net: pypsa.Network):
    """Checks that there are no lines or transformers in the zonal network, as these should be represented either as links or nothing
    (since fbmc constraints will be added)

    """

    if (zonal_net.lines.index).any():
        raise ValueError("Lines found in zonal network.")
    if (zonal_net.transformers.index).any():
        raise ValueError("Transformers found in zonal network.")
    if (zonal_net.links.index).any():
        logging.warning(f" {len(zonal_net.links.index)} Links found in zonal network. Make sure they represent HVDC connections, not NTCs. Link indices: " + str(zonal_net.links.index))


def check_custom_cnecs(cnecs_input):
    if cnecs_input is None:
        raise ValueError(
            "cnec_setting is CUSTOM but no cnecs were provided. "
            "Pass a cnecs argument to run_fbmc()."
        )
    if isinstance(cnecs_input, str) or not isinstance(cnecs_input, Sequence):
        raise ValueError(
            "cnecs must be a Sequence of Sequences (e.g. a list of tuples). "
            "See fbmc.core.input_parameters.cnec.cnec_subnet_router() for the expected format."
        )
    if not all(isinstance(item, Sequence) and not isinstance(item, str) for item in cnecs_input):
        raise ValueError(
            "Each element of cnecs must itself be a Sequence (e.g. a tuple). "
            "See fbmc.core.input_parameters.cnec.cnec_subnet_router() for the expected format."
        )


def do_input_checks(nodal_net, zonal_net, gsk_dict, cnec_strategy=None, cnecs_input=None):
    check_reactance(nodal_net)
    check_no_lines_or_transformers_in_zonal_net(zonal_net)
    if cnec_strategy == CNECStrategy.CUSTOM:
        check_custom_cnecs(cnecs_input)
