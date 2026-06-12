"""Usage: python -m scripts.run.ua_bodf_threshold_compare [--start-index N] [--n-timesteps N]

Run two UA base-network clearings with security constraints enabled and different
BODF size thresholds, then compare zonal market prices.
"""

from __future__ import annotations

import argparse
import os
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pypsa

from ...src.runner import main
from example_networks.main import Cases
from fbmc.input_network_conversions.network_conversion import nodal_to_zonal
from fbmc.settings import FBMCConfig
from fbmc.enums import BaseCaseStrategy, GSKStrategy
from fbmc.paths import get_case_results_dir, get_input_networks_dir


DEFAULT_START_INDEX = 24 * 4 * 4
DEFAULT_N_TIMESTEPS = 1
DEFAULT_THRESHOLDS = (0.00, 0.05)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare UA market prices for two security_constraint_bodf_size_threshold values.",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=DEFAULT_START_INDEX,
        help="Start index in the snapshot axis (default: %(default)s).",
    )
    parser.add_argument(
        "--n-timesteps",
        type=int,
        default=DEFAULT_N_TIMESTEPS,
        help="Number of timesteps to run (default: %(default)s).",
    )
    parser.add_argument(
        "--variant",
        default="red",
        help="UA input variant folder under pypsa-eur-ua (default: %(default)s).",
    )
    parser.add_argument(
        "--thresholds",
        nargs=2,
        type=float,
        default=DEFAULT_THRESHOLDS,
        metavar=("LOW", "HIGH"),
        help=(
            "Two BODF size thresholds to compare. By default interpreted as fractions "
            "(0..1), e.g. --thresholds 0 0.05."
        ),
    )
    parser.add_argument(
        "--thresholds-are-percent",
        action="store_true",
        help="Interpret --thresholds values as percentages, e.g. --thresholds 0 5 => 0.00 and 0.05.",
    )
    return parser.parse_args()


def _threshold_tag(threshold: float) -> str:
    text = f"{threshold:.4f}".rstrip("0").rstrip(".")
    return f"thr_{text.replace('.', '_')}"


def prepare_networks(base_nodal_net: pypsa.Network) -> tuple[pypsa.Network, pypsa.Network]:
    nodal_net = deepcopy(base_nodal_net)
    nodal_net.buses.loc[:, "zone_name"] = nodal_net.buses.country
    zonal_net = nodal_to_zonal(nodal_net, bus_zone_map=nodal_net.buses.zone_name)
    return nodal_net, zonal_net


def run_threshold_case(
    base_nodal_net: pypsa.Network,
    threshold: float,
    save_path: Path,
    snapshot_slice: slice,
) -> pd.DataFrame:
    nodal_net, zonal_net = prepare_networks(base_nodal_net)

    config = FBMCConfig.from_base_yaml(Path("config/base_config.yaml"))
    config.add_security_constraints = True

    main(
        save_path=save_path,
        case_name=None,
        zonal_net=zonal_net,
        nodal_net=nodal_net,
        config=config,
        config_overrides={
            "gsk_strategy": GSKStrategy.P_NOM,
            "base_case_strategy": BaseCaseStrategy.ZERO_FLOWS,
            "reliability_margin_factor": 0.1,
            "run_redispatch": False,
            "security_constraint_bodf_size_threshold": threshold,
        },
        load_case_flag=False,
        case_kwargs={},
        case_alteration_kwargs={
            "snapshot_i_range": snapshot_slice,
            "use_unit_commitment": False,
            "unit_commitment_path": "data/unit_commitment_halve_su_sd.csv",
            "add_zonal_load_shedding": True,
            "load_shedding_cost": 5000,
        },
    )

    prices_path = save_path / "zonal_market_prices.csv"
    return pd.read_csv(prices_path, index_col=0)


def compare_prices(prices_000: pd.DataFrame, prices_005: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    common_snapshots = prices_000.index.intersection(prices_005.index)
    common_zones = prices_000.columns.intersection(prices_005.columns)

    p000 = prices_000.loc[common_snapshots, common_zones].apply(pd.to_numeric, errors="coerce")
    p005 = prices_005.loc[common_snapshots, common_zones].apply(pd.to_numeric, errors="coerce")

    diff = p005 - p000
    summary = pd.DataFrame(
        {
            "mean_price_thr_0_00": p000.mean(axis=0),
            "mean_price_thr_0_05": p005.mean(axis=0),
            "mean_diff_0_05_minus_0_00": diff.mean(axis=0),
            "mean_abs_diff": diff.abs().mean(axis=0),
            "max_abs_diff": diff.abs().max(axis=0),
        }
    ).sort_values("mean_abs_diff", ascending=False)

    return diff, summary


def main_cli() -> None:

    args = parse_args()
    if args.n_timesteps < 1:
        raise ValueError("--n-timesteps must be >= 1")

    thresholds = tuple(args.thresholds)
    if args.thresholds_are_percent:
        thresholds = tuple(t / 100.0 for t in thresholds)

    if any(t < 0 or t > 1 for t in thresholds):
        raise ValueError("Threshold values must be in [0, 1] after conversion.")

    snapshot_slice = slice(args.start_index, args.start_index + args.n_timesteps)

    input_path = get_input_networks_dir() / "pypsa-eur-ua" / args.variant / "nodal.nc"
    if not input_path.exists():
        raise FileNotFoundError(f"UA nodal network not found: {input_path}")

    base_nodal_net = pypsa.Network(input_path)

    output_dir = get_case_results_dir(Cases.PYPSA_EUR_UA.value) / "bodf-threshold-compare" / args.variant
    output_dir.mkdir(parents=True, exist_ok=True)

    run_low_dir = output_dir / _threshold_tag(thresholds[0])
    run_high_dir = output_dir / _threshold_tag(thresholds[1])
    run_low_dir.mkdir(parents=True, exist_ok=True)
    run_high_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running case with security_constraint_bodf_size_threshold={thresholds[0]:.4f}")
    prices_low = run_threshold_case(base_nodal_net, thresholds[0], run_low_dir, snapshot_slice)

    print(f"Running case with security_constraint_bodf_size_threshold={thresholds[1]:.4f}")
    prices_high = run_threshold_case(base_nodal_net, thresholds[1], run_high_dir, snapshot_slice)

    diff, summary = compare_prices(prices_low, prices_high)

    low_file = output_dir / f"market_prices_{_threshold_tag(thresholds[0])}.csv"
    high_file = output_dir / f"market_prices_{_threshold_tag(thresholds[1])}.csv"
    diff_file = output_dir / f"market_prices_diff_{_threshold_tag(thresholds[1])}_minus_{_threshold_tag(thresholds[0])}.csv"
    summary_file = output_dir / f"market_prices_diff_summary_{_threshold_tag(thresholds[1])}_minus_{_threshold_tag(thresholds[0])}_by_zone.csv"

    prices_low.to_csv(low_file)
    prices_high.to_csv(high_file)
    diff.to_csv(diff_file)
    summary.to_csv(summary_file)

    print("Saved outputs:")
    print(f"- {low_file}")
    print(f"- {high_file}")
    print(f"- {diff_file}")
    print(f"- {summary_file}")

    if not summary.empty:
        top_zone = summary.index[0]
        top_change = summary.iloc[0]["mean_abs_diff"]
        print(f"Largest average absolute price change: {top_zone} ({top_change:.3f} EUR/MWh)")


if __name__ == "__main__":
    main_cli()
