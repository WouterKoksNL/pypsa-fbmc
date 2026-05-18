from pathlib import Path
import json
from typing import Any

from src.config import FBMCConfig, config_to_dict
from src.types import FBMCWorkflowResult

from .market_prices import calculate_zonal_prices


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

    zonal_prices = calculate_zonal_prices(
        fbmc_results.zonal_net.buses.index, 
        fbmc_results.zonal_net.snapshots,
        z_ptdf_by_subnet,
        fbmc_results.zonal_net.model
        )

    outputs: dict[str, Path] = {}

    prices_path = save_path / "zonal_market_prices.csv"
    zonal_prices.to_csv(prices_path)
    outputs["zonal_market_prices"] = prices_path

    objective_value = None
    if getattr(fbmc_results.zonal_net, "model", None) is not None:
        objective = getattr(fbmc_results.zonal_net.model, "objective", None)
        objective_value = float(objective.value) if objective is not None and objective.value is not None else None

    summary = {
        "fbmc_objective": objective_value,
        "redispatch_cost": float(rd_cost) if rd_cost is not None else None,
    }
    summary_path = save_path / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    outputs["summary"] = summary_path

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

    network_path = save_path / "fbmc_network.nc"
    fbmc_results.zonal_net.export_to_netcdf(network_path)
    outputs["fbmc_network"] = network_path

    return outputs