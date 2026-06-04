from pathlib import Path
import json
from typing import Any
import pandas as pd

from fbmc.settings import FBMCConfig, config_to_dict
from fbmc.types import FBMCResult

from .market_prices import calculate_zonal_prices


def calculate_zonal_load_shedding(fbmc_results: FBMCResult) -> pd.DataFrame:
    """Aggregate load-shedding generator dispatch to zonal totals per snapshot."""
    zonal_net = fbmc_results.zonal_net
    snapshots = zonal_net.snapshots
    zones = zonal_net.buses.index

    load_shedding_gens = zonal_net.generators.index[zonal_net.generators.carrier == "load-shedding"]
    if len(load_shedding_gens) == 0:
        return pd.DataFrame(0.0, index=snapshots, columns=zones)

    generator_dispatch = fbmc_results.dispatch_results.generators_p
    if generator_dispatch.empty:
        return pd.DataFrame(0.0, index=snapshots, columns=zones)

    existing_load_shedding_gens = [g for g in load_shedding_gens if g in generator_dispatch.columns]
    if len(existing_load_shedding_gens) == 0:
        return pd.DataFrame(0.0, index=snapshots, columns=zones)

    load_shedding_dispatch = generator_dispatch.loc[:, existing_load_shedding_gens]
    zone_map = zonal_net.generators.loc[existing_load_shedding_gens, "bus"]
    zonal_load_shedding = load_shedding_dispatch.T.groupby(zone_map).sum().T
    return zonal_load_shedding.reindex(columns=zones, fill_value=0.0)


def calculate_generation_mix(fbmc_results: FBMCResult) -> pd.DataFrame:
    """Aggregate generator dispatch by bus and carrier for each snapshot."""
    zonal_net = fbmc_results.zonal_net
    generator_dispatch = fbmc_results.dispatch_results.generators_p

    if generator_dispatch.empty:
        return pd.DataFrame(index=zonal_net.snapshots)

    existing_generators = [g for g in zonal_net.generators.index if g in generator_dispatch.columns]
    if len(existing_generators) == 0:
        return pd.DataFrame(index=generator_dispatch.index)

    generator_dispatch = generator_dispatch.loc[:, existing_generators]
    bus_labels = zonal_net.generators.loc[existing_generators, "bus"].astype(str)
    carrier_labels = zonal_net.generators.loc[existing_generators, "carrier"].fillna("Unknown").astype(str)

    generation_mix = generator_dispatch.T.groupby([bus_labels, carrier_labels]).sum().T
    return generation_mix.sort_index(axis=1)


def calculate_storage_mix(fbmc_results: FBMCResult) -> pd.DataFrame:
    """Aggregate storage-unit active power by bus and carrier for each snapshot."""
    zonal_net = fbmc_results.zonal_net
    storage_dispatch = fbmc_results.dispatch_results.storage_units_p

    if storage_dispatch is None or storage_dispatch.empty:
        return pd.DataFrame(index=zonal_net.snapshots)

    existing_storage_units = [su for su in zonal_net.storage_units.index if su in storage_dispatch.columns]
    if len(existing_storage_units) == 0:
        return pd.DataFrame(index=storage_dispatch.index)

    storage_dispatch = storage_dispatch.loc[:, existing_storage_units]
    bus_labels = zonal_net.storage_units.loc[existing_storage_units, "bus"].astype(str)
    carrier_labels = zonal_net.storage_units.loc[existing_storage_units, "carrier"].fillna("Unknown").astype(str)

    storage_mix = storage_dispatch.T.groupby([bus_labels, carrier_labels]).sum().T
    return storage_mix.sort_index(axis=1)


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
        fbmc_results: FBMCResult, 
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

    zonal_load_shedding = calculate_zonal_load_shedding(fbmc_results)
    load_shedding_path = save_path / "load_shedding_zone_p.csv"
    zonal_load_shedding.to_csv(load_shedding_path)
    outputs["load_shedding_zone_p"] = load_shedding_path

    generation_mix = calculate_generation_mix(fbmc_results)
    generation_mix_path = save_path / "generation_mix.csv"
    generation_mix.to_csv(generation_mix_path)
    outputs["generation_mix"] = generation_mix_path

    storage_mix = calculate_storage_mix(fbmc_results)
    storage_mix_path = save_path / "storage_mix.csv"
    storage_mix.to_csv(storage_mix_path)
    outputs["storage_mix"] = storage_mix_path

    if getattr(fbmc_results.dispatch_results, "storage_units_p", None) is not None:
        storage_units_p_path = save_path / "storage_units_p.csv"
        fbmc_results.dispatch_results.storage_units_p.to_csv(storage_units_p_path)
        outputs["storage_units_p"] = storage_units_p_path

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
        water_values = getattr(fbmc_results.dispatch_results, "water_values", None)
        if water_values is not None:
            water_values_path = save_path / "water_values.csv"
            water_values_df = water_values.to_pandas()
            water_values_df.to_csv(water_values_path)
            outputs["water_values"] = water_values_path


    network_path = save_path / "fbmc_network.nc"
    fbmc_results.zonal_net.export_to_netcdf(network_path)
    outputs["fbmc_network"] = network_path

    return outputs