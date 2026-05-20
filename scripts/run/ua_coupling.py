
from pathlib import Path
import sys
import pandas as pd
import pypsa

from src.config import FBMCConfig
from src.case_creation.main import Cases
from src.enums import GSKStrategy, BaseCaseStrategy
from main import main
from src.paths import get_case_results_dir, get_results_dir, get_input_networks_dir

config_path = Path("config/base_config.yaml")
config = FBMCConfig.from_base_yaml(config_path)
save_path = Path(get_case_results_dir(Cases.PYPSA_EUR_UA.value))  / "base"
obj3 = main(
    save_path=save_path,
    case_name=Cases.PYPSA_EUR_UA, 
    config=config,
    config_overrides={
        "gsk_strategy": GSKStrategy.P_NOM,
        "base_case_strategy": BaseCaseStrategy.ZERO_FLOWS,
        "advanced_hybrid_coupling_flag": False,
        "reliability_margin_factor": 0.3,
        "add_security_constraints": False,
        "security_constrained_redispatch": False,
    },
    load_case_flag=False,
    case_kwargs={
        # 'drop_countries': ["UA"]
    },
    case_alteration_kwargs={
        'snapshot_i_range': slice(0, 24),
        'use_unit_commitment': False,
        'unit_commitment_path': "data/unit_commitment_halve_su_sd.csv",
    }
)  

net_sep = pypsa.Network(get_input_networks_dir() / "pypsa-eur-ua-disconnected" / "nodal.nc")
net_sep.buses.loc[:, 'zone_name'] = net_sep.buses.country

save_path = get_results_dir() / "pypsa-eur-ua" / "disconnected"
if not save_path.exists():
    save_path.mkdir(parents=True)
config_path = Path("config/base_config.yaml")

config = FBMCConfig.from_base_yaml(config_path)

obj3 = main(
    nodal_net=net_sep,
    save_path=save_path,
    case_name="pypsa-eur-ua-disconnected", 
    config=config,
    config_overrides={
        "gsk_strategy": GSKStrategy.P_NOM,
        "base_case_strategy": BaseCaseStrategy.ZERO_FLOWS,
        "advanced_hybrid_coupling_flag": False,
        "reliability_margin_factor": 0.3,
        "add_security_constraints": False,
        "security_constrained_redispatch": False,
    },
    load_case_flag=False,
    case_kwargs={
        # 'drop_countries': ["UA"]
    },
    case_alteration_kwargs={
        'snapshot_i_range': slice(0, 24),
        'use_unit_commitment': False,
        'unit_commitment_path': "data/unit_commitment_halve_su_sd.csv",
    }
)  
