from pathlib import Path
import json
from typing import Any
import pandas as pd

from src.config import FBMCConfig, config_to_dict
from src.types import FBMCWorkflowResult

from .market_prices import calculate_zonal_prices


def get_slack_zones(nodal_buses: pd.DataFrame) -> pd.Series:
    """Create a mapping of sub_networks to their respective slack buses.

    Args:
        nodal_buses (pd.DataFrame): DataFrame containing the nodal bus information, including 'control', 'sub_network', and 'zone_name' columns.

    Returns:
        pd.Series: A Series with sub_network as index and zone_name as value, representing the slack zone for each sub_network.
    """
    slack_buses = pd.DataFrame(nodal_buses[nodal_buses.control == 'Slack'])
    # If only one subnetwork, ensure output is still a Series with sub_network as index
    if slack_buses.shape[0] == 1:
        sub_network = slack_buses.iloc[0]['sub_network']
        zone_name = slack_buses.iloc[0]['zone_name']
        return pd.Series({sub_network: zone_name}, name='zone_name')
    return slack_buses.loc[:, ['sub_network', 'zone_name']].reset_index(drop=True).set_index('sub_network')['zone_name']

def process_results(
        fbmc_results: FBMCWorkflowResult, 
        rd_cost: float | None,
        rd_dispatch: Any,
        save_path: Path,
        config: FBMCConfig | None = None,
    ) -> dict[str, Path]:
    """
    Save:
    - zonal market prices 
    - fbmc objective
    - redispatch costs 
    - redispatch dispatch results
    - linopy model
    - Zone-p net positions (if available)
    - fbmc link flows (if links exist)
    - fbmc network

    Returns:
        dict[str, Path]: Paths to saved artifacts.
    """
    save_path = Path(save_path)
    save_path.mkdir(parents=True, exist_ok=True)

    z_ptdf_by_subnet = {
        subnet_name: params.z_ptdf
        for subnet_name, params in fbmc_results.fbmc_parameters.items()
    }


    sn_slack_zone_map = get_slack_zones(fbmc_results.base_case.buses)
    zonal_prices = calculate_zonal_prices(
        fbmc_results.zonal_net.buses.index, 
        fbmc_results.zonal_net.snapshots,
        z_ptdf_by_subnet,
        fbmc_results.zonal_net.model,
        sn_slack_zone_map
        )

    outputs: dict[str, Path] = {}

    prices_path = save_path / "zonal_market_prices.csv"
    zonal_prices.to_csv(prices_path)
    outputs["zonal_market_prices"] = prices_path

    objective_value = None
    if getattr(fbmc_results.zonal_net, "model", None) is not None:
        objective = fbmc_results.zonal_net.model.objective
        objective_value = float(objective.value) 

    summary = {
        "fbmc_objective": objective_value,
        "redispatch_cost": float(rd_cost) if rd_cost is not None else None,
    }
    summary_path = save_path / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    outputs["summary"] = summary_path

    model = getattr(fbmc_results.zonal_net, "model", None)
    if model is not None:
        linopy_model_path = save_path / "linopy_model.nc"
        model.to_netcdf(linopy_model_path)
        outputs["linopy_model"] = linopy_model_path

    if model is not None and hasattr(model, "solution") and "Zone-p" in model.solution:
        net_positions_zone_p = model.solution["Zone-p"].to_pandas()
        net_positions_path = save_path / "net_positions_zone_p.csv"
        net_positions_zone_p.to_csv(net_positions_path)
        outputs["net_positions_zone_p"] = net_positions_path

    if not fbmc_results.zonal_net.links.empty and getattr(fbmc_results.zonal_net.links_t, "p0", None) is not None:
        fbmc_links_path = save_path / "fbmc_links_p0.csv"
        fbmc_results.zonal_net.links_t.p0.to_csv(fbmc_links_path)
        outputs["fbmc_links_p0"] = fbmc_links_path

    if config is not None:
        config_path = save_path / "config.json"
        config_path.write_text(json.dumps(config_to_dict(config), indent=2), encoding="utf-8")
        outputs["config"] = config_path

    if rd_dispatch is not None:
        if getattr(rd_dispatch, "generators_p", None) is not None:
            rd_generators_path = save_path / "redispatch_generators_p.csv"
            rd_dispatch.generators_p.to_csv(rd_generators_path)
            outputs["redispatch_generators_p"] = rd_generators_path

        if getattr(rd_dispatch, "storage_units_p", None) is not None:
            rd_storage_path = save_path / "redispatch_storage_units_p.csv"
            rd_dispatch.storage_units_p.to_csv(rd_storage_path)
            outputs["redispatch_storage_units_p"] = rd_storage_path

        if getattr(rd_dispatch, "links_p0", None) is not None:
            rd_links_path = save_path / "redispatch_links_p0.csv"
            rd_dispatch.links_p0.to_csv(rd_links_path)
            outputs["redispatch_links_p0"] = rd_links_path

        # Save storage levels if available
        if getattr(fbmc_results.dispatch_results, "storage_levels", None) is not None:
            storage_levels_path = save_path / "storage_levels.csv"
            fbmc_results.dispatch_results.storage_levels.to_csv(storage_levels_path)
            outputs["storage_levels"] = storage_levels_path

        # Save water values if available
        if hasattr(fbmc_results.dispatch_results, "water_values"):
            water_values_path = save_path / "water_values.csv"
            water_values_df = fbmc_results.dispatch_results.water_values.to_pandas()
            water_values_df.to_csv(water_values_path)
            outputs["water_values"] = water_values_path


    network_path = save_path / "fbmc_network.nc"
    fbmc_results.zonal_net.export_to_netcdf(network_path)
    outputs["fbmc_network"] = network_path

    return outputs