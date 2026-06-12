from fbmc.settings import FBMCConfig
from fbmc.api import run_fbmc
from example_networks.main import create_case, Cases


config = FBMCConfig.from_base_yaml("config/base_config.yaml")
case_data = create_case(case=Cases.BASIC_THREE_NODE)

fbmc_result = run_fbmc(
    zonal_net=case_data['zonal_net'],
    nodal_net=case_data['nodal_net'],
    config=config,
)

print(fbmc_result.dispatch_results)
print(fbmc_result.net_positions)




