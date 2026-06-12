from pathlib import Path

from fbmc.settings import FBMCConfig
from fbmc.api import main, run_fbmc
from fbmc import Cases, create_case
from fbmc.api import redispatch_workflow

config_path = Path("config/base_config.yaml")
config = FBMCConfig.from_base_yaml(config_path)
config.gsk_strategy = "P_NOM"

case_data = create_case(case=Cases.BASIC_THREE_NODE)

fbmc_result = run_fbmc(
    zonal_net=case_data['zonal_net'],
    nodal_net=case_data['nodal_net'],
    config=config,
)


print(fbmc_result.net_positions)
print(fbmc_result.zonal_net.model)



