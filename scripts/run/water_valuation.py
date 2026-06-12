
from pathlib import Path
import sys
import pandas as pd

from fbmc.settings import FBMCConfig
from example_networks.main import Cases
from fbmc.enums import GSKStrategy, BaseCaseStrategy
from ...src.runner import main
from fbmc.paths import get_case_results_dir

N_TIMESTEPS = sys.argv[1] if len(sys.argv) > 1 else 24*7

config_path = Path("config/base_config.yaml")
config = FBMCConfig.from_base_yaml(config_path)
save_path = Path(get_case_results_dir(Cases.PYPSA_EUR_UA.value)) / "long_term"
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
        "run_redispatch": False,
        "security_constrained_redispatch": False,
    },
    load_case_flag=False,
    case_kwargs={
        'snapshot_i_range': slice(0, N_TIMESTEPS),
        'use_unit_commitment': False,
        'unit_commitment_path': "data/unit_commitment_halve_su_sd.csv",
        # 'drop_countries': ["UA"]
    },
)  

# now extract water values 

# now extract water values from the csv


results_dir = Path(get_case_results_dir(Cases.PYPSA_EUR_UA.value)) / "long_term"
water_values_path = results_dir / "water_values.csv"
if water_values_path.exists():
    water_values = pd.read_csv(water_values_path, index_col=0)
    water_values.to_csv("data/water_values.csv")  # save a copy in data/ for easy loading in case creation
else:
    print(f"Water values file not found at {water_values_path}")

save_path = Path(get_case_results_dir(Cases.PYPSA_EUR_UA.value)) / "daily_market"
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
        "run_redispatch": False,
        "security_constrained_redispatch": False,
    },
    load_case_flag=False,
    case_kwargs={
        'snapshot_i_range': slice(0, 24),
        'use_unit_commitment': True,
        'unit_commitment_path': "data/unit_commitment_halve_su_sd.csv",
        'load_water_values': True,
        'water_values_path': "data/water_values.csv",
    },
)  



    
