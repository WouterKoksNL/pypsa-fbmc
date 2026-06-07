import logging
import pypsa
import pandas as pd

from ...settings import FBMCConfig
from ...types import InputParameters, GSKStrategy, BaseCaseStrategy
from .base_case import prepare_base_case
from .gsk import calculate_gsk
from .cnec import cnec_router

def calc_input_parameters(
    nodal_net: pypsa.Network,
    gsk: dict | None,
    gsk_strategy: GSKStrategy,
    config: FBMCConfig
) -> InputParameters:
    """

    Args:
        nodal_net (pypsa.Network): _description_
        config (FBMCConfig): _description_

    Returns:
        InputParameters: _description_
    """
    base_case = prepare_base_case(
        nodal_net, 
        strategy=config.base_case_strategy,
        base_case_kwargs=config.fbmc_solver_kwargs
        )

    if gsk is None:
        gsk = calculate_gsk(base_case, gsk_strategy, config.gsk_kwargs)

    cnecs_dict = cnec_router(nodal_net, config.cnec_setting, config.add_security_constraints)
        
    return InputParameters(gsk=gsk, cnecs=cnecs_dict, base_case=base_case)