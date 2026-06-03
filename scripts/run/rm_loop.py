from pathlib import Path

from fbmc.settings import FBMCConfig
from fbmc.core import main
from fbmc.case_creation.main import Cases
from fbmc.enums import GSKStrategy, BaseCaseStrategy
from fbmc.paths import get_case_results_dir

rm_list = [0.0, 0.1, 0.2, 0.3]
config_path = Path("config/base_config.yaml")
config = FBMCConfig.from_base_yaml(config_path)

for r in rm_list:
    save_path = Path(get_case_results_dir(Cases.PYPSA_EUR_UA.value))  / f"n-0_RM_{str(config.reliability_margin_factor)}"
    obj3 = main(
        save_path=save_path,
        case_name=Cases.PYPSA_EUR_UA, 
        config=config,
        config_overrides={
            "gsk_strategy": GSKStrategy.P_NOM,
            "base_case_strategy": BaseCaseStrategy.ZERO_FLOWS,
            "advanced_hybrid_coupling_flag": False,
            "reliability_margin_factor": r,
            "add_security_constraints": False,
            "security_constrained_redispatch": False,
        },
        load_case_flag=False,
        case_kwargs={
            'snapshot_i_range': slice(0, 24*7),
            'use_unit_commitment': True,
            'unit_commitment_path': "data/unit_commitment_halve_su_sd.csv",
            # 'drop_countries': ["UA"]
        },
    )  



