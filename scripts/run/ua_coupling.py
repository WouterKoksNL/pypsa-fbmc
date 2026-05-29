"""Usage: python -m scripts.run.ua_coupling [-t] [-r RUN]"""


from pathlib import Path
import sys
import argparse
import pandas as pd
import pypsa
from copy import deepcopy

from src.config import FBMCConfig
from src.case_creation.main import Cases
from src.enums import GSKStrategy, BaseCaseStrategy
from main import main
from src.paths import get_case_results_dir, get_results_dir, get_input_networks_dir
from src.case_creation.network_conversion import nodal_to_zonal


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Run UA coupling scenarios.",
    )
    parser.add_argument(
        "-t",
        "--test",
        action="store_true",
        help="Run a short test horizon instead of the full horizon.",
    )
    parser.add_argument(
        "-r",
        "--run",
        default=None,
        help="Run only one scenario key from param_dict (default: run all).",
    )
    return parser.parse_args(argv)


args = parse_args(sys.argv[1:])
test_bool = args.test
selected_run = args.run

print(f"Running with test_bool={test_bool}")

if test_bool:
    N_TIMESTEPS_LONG_TERM = 6
    N_TIMESTEPS_MARKET = 2
    SECURITY_CONSTRAINTS_FLAG = False
    RMF = 0.4
else:
    N_TIMESTEPS_LONG_TERM = 24*7
    N_TIMESTEPS_MARKET = 24
    SECURITY_CONSTRAINTS_FLAG = True
    RMF = 0.1
TS_START = 24*4*4


n_market_clearings = int(N_TIMESTEPS_LONG_TERM / N_TIMESTEPS_MARKET)

def prep_base_case(params):
    params["nodal_net"].buses.loc[:, 'zone_name'] = params["nodal_net"].buses.country
    params["zonal_net"] = nodal_to_zonal(params["nodal_net"], bus_zone_map=params["nodal_net"].buses.zone_name)
    return 

def prep_ntc_case(params):
    params["nodal_net"].buses.loc[:, 'zone_name'] = params["nodal_net"].buses.country
    params["zonal_net"] = nodal_to_zonal(params["nodal_net"], bus_zone_map=params["nodal_net"].buses.zone_name)
    # load ntc 
    ntc_path = get_input_networks_dir() / "pypsa-eur-ua-ntc" / "ntc_values.csv"
    ntc_df = pd.read_csv(ntc_path, index_col=0)

    params["zonal_net"].add("Link", ntc_df.index, bus0=ntc_df['zone0'], bus1=ntc_df['zone1'], p_nom=ntc_df['p_nom'], p_min_pu=-1)
    return 

def prep_disconnected_case(params):
    params["nodal_net"].buses.loc[:, 'zone_name'] = params["nodal_net"].buses.country
    params["zonal_net"] = nodal_to_zonal(params["nodal_net"], bus_zone_map=params["nodal_net"].buses.zone_name)
    return

### BASE ###

param_dict = {
    "base": {
        "case_name": None,
        "nodal_net": pypsa.Network(get_input_networks_dir() / "pypsa-eur-ua" / "red"/ "nodal.nc"),
        "save_path": get_case_results_dir(Cases.PYPSA_EUR_UA.value) / "base" / "red",
        "prep_func": prep_base_case,
     },
     "ntc-max": {
        "case_name": None, 
        "save_path": get_case_results_dir(Cases.PYPSA_EUR_UA.value)  / "ntc-max" / "red",
        "nodal_net": pypsa.Network(get_input_networks_dir() / "pypsa-eur-ua-ntc" / "red"/ "nodal.nc"),
        "prep_func": prep_ntc_case, 
     },
     "ntc-2450": {
        "case_name": None, 
        "save_path": get_case_results_dir(Cases.PYPSA_EUR_UA.value)  / "ntc-2450" / "red",
        "nodal_net": pypsa.Network(get_input_networks_dir() / "pypsa-eur-ua-ntc" / "red"/ "nodal.nc"),
        "prep_func": prep_ntc_case, 
     },
    "disconnected": {
        "case_name": None, 
        "save_path": get_case_results_dir(Cases.PYPSA_EUR_UA.value) / "disconnected" / "red",
        "nodal_net": pypsa.Network(get_input_networks_dir() / "pypsa-eur-ua-disconnected" / "red" / "nodal.nc"),
        "prep_func": prep_disconnected_case,
     },
     "np-limit": {
        "case_name": None,
        "nodal_net": pypsa.Network(get_input_networks_dir() / "pypsa-eur-ua" / "red" / "nodal.nc"),
        "save_path": get_case_results_dir(Cases.PYPSA_EUR_UA.value) / "np-limit" / "red",
        "prep_func": prep_base_case,
     }
}

if selected_run is not None:
    if selected_run not in param_dict:
        available_runs = ", ".join(param_dict.keys())
        raise ValueError(
            f"Unknown run '{selected_run}'. Available runs: {available_runs}"
        )
    runs_to_execute = {selected_run: param_dict[selected_run]}
    print(f"Running selected run='{selected_run}'")
else:
    runs_to_execute = param_dict

# water valuation

# for case, params in deepcopy(param_dict).items():
#     config_path = Path("config/base_config.yaml")
#     config = FBMCConfig.from_base_yaml(config_path)
#     wv_save_path = params["save_path"] / "water_valuation"
#     if not wv_save_path.exists():
#         wv_save_path.mkdir(parents=True)
#     params["prep_func"](params)
#     if "ntc" in case:
#         config.transfer_limit_UA_MD_flag = True
#         config.transfer_limit_UA_MD = "
#     obj3 = main(
#         save_path=wv_save_path,
#         case_name=params["case_name"], 
#         zonal_net=params.get("zonal_net", None),
#         nodal_net=params.get("nodal_net", None),
#         config=config,
#         config_overrides={
#             "gsk_strategy": GSKStrategy.P_NOM,
#             "base_case_strategy": BaseCaseStrategy.ZERO_FLOWS,
#             "reliability_margin_factor": 0.3,
#             "run_redispatch": False,
#         },
#         load_case_flag=False,
#         case_kwargs={},
#         case_alteration_kwargs={
#             'snapshot_i_range': slice(0, N_TIMESTEPS_LONG_TERM),
#             'use_unit_commitment': False,
#             'unit_commitment_path': "data/unit_commitment_halve_su_sd.csv",
#         }
#     )  


for case, params_base in deepcopy(runs_to_execute).items():
    config_path = Path("config/base_config.yaml")
    config = FBMCConfig.from_base_yaml(config_path)
    config.add_security_constraints = SECURITY_CONSTRAINTS_FLAG
    if case == "ntc-2450":
        config.transfer_limit_UA_MD_flag = True
        config.transfer_limit_EUR_UA = 2450 
        config.transfer_limit_UA_EUR = 900
    if case == "np-limit":
        config.net_position_limit_UA_flag = True
        config.net_position_UA_lower_limit = -2450
        config.net_position_UA_upper_limit = 900
    # config.fbmc_create_model_kwargs["linearized_unit_commitment"] = False
    # config.use_unit_commitment = False
    # config.add_security_constraints

    
    for i_clearing in range(n_market_clearings):
        params = deepcopy(params_base)
        params["prep_func"](params)
        save_path = params["save_path"] / f"clearing_{i_clearing}"
        if not save_path.exists():
            save_path.mkdir(parents=True)
        obj3 = main(
            save_path=save_path,
            case_name=params["case_name"], 
            zonal_net=params.get("zonal_net", None),
            nodal_net=params.get("nodal_net", None),
            config=config,
            config_overrides={
                "gsk_strategy": GSKStrategy.P_NOM,
                "base_case_strategy": BaseCaseStrategy.ZERO_FLOWS,
                "reliability_margin_factor": RMF,
                "run_redispatch": False,
            },
            load_case_flag=False,
            case_kwargs={},
            case_alteration_kwargs={
                'snapshot_i_range': slice(TS_START+N_TIMESTEPS_MARKET*i_clearing, TS_START+N_TIMESTEPS_MARKET*(i_clearing+1)),
                'use_unit_commitment': False,
                'unit_commitment_path': "data/unit_commitment_halve_su_sd.csv",
                'add_zonal_load_shedding': True,
                'load_shedding_cost': 5000,
            }
        )  
