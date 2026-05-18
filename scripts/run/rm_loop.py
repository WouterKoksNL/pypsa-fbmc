from src.fbmc import main
from src.case_creation.main import Cases
from src.types import GSKStrategy, BaseCaseStrategy


rm_list = [0.0, 0.1, 0.2, 0.3]
for r in rm_list:
    obj3 = main(
        case_name=Cases.PYPSA_EUR_UA, 
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
            'snapshot_i_range': slice(0, 24),
            # 'drop_countries': ["UA"]
        },
    )  
