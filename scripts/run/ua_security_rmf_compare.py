"""Usage: python -m scripts.run.ua_security_rmf_compare [--start-index N] [--n-timesteps N]

Compare two UA base-network runs:
- Security constraints ON, RMF=0.1
- Security constraints OFF, RMF=0.4

Writes per-run outputs and comparison CSVs for zonal market prices and net positions.
"""

from __future__ import annotations

import argparse
import os
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pypsa

from fbmc.api import main
from fbmc.case_creation.main import Cases
from fbmc.case_creation.network_conversion import nodal_to_zonal
from fbmc.settings import FBMCConfig
from fbmc.enums import BaseCaseStrategy, GSKStrategy
from fbmc.paths import get_case_results_dir, get_input_networks_dir


DEFAULT_START_INDEX = 24 * 4 * 4
DEFAULT_N_TIMESTEPS = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare UA runs: security ON + RMF 0.1 versus security OFF + RMF 0.4",
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
        "--case",
        default="base",
        choices=["base"],
        help="UA scenario case to run (default: %(default)s).",
    )
    parser.add_argument(
        "--variant",
        default="red",
        help="UA input variant folder under pypsa-eur-ua (default: %(default)s).",
    )
    return parser.parse_args()


def prepare_networks(base_nodal_net: pypsa.Network) -> tuple[pypsa.Network, pypsa.Network]:
    nodal_net = deepcopy(base_nodal_net)
    nodal_net.buses.loc[:, "zone_name"] = nodal_net.buses.country
    zonal_net = nodal_to_zonal(nodal_net, bus_zone_map=nodal_net.buses.zone_name)
    return nodal_net, zonal_net


def run_case(
    base_nodal_net: pypsa.Network,
    save_path: Path,
    snapshot_slice: slice,
    security_constraints: bool,
    rmf: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    nodal_net, zonal_net = prepare_networks(base_nodal_net)

    config = FBMCConfig.from_base_yaml(Path("config/base_config.yaml"))
    config.add_security_constraints = security_constraints

    main(
        save_path=save_path,
        case_name=None,
        zonal_net=zonal_net,
        nodal_net=nodal_net,
        config=config,
        config_overrides={
            "gsk_strategy": GSKStrategy.P_NOM,
            "base_case_strategy": BaseCaseStrategy.ZERO_FLOWS,
            "reliability_margin_factor": rmf,
            "run_redispatch": False,
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

    prices = pd.read_csv(save_path / "zonal_market_prices.csv", index_col=0)
    net_positions = pd.read_csv(save_path / "net_positions_zone_p.csv", index_col=0)
    return prices, net_positions


def align_numeric(a: pd.DataFrame, b: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    common_snapshots = a.index.intersection(b.index)
    common_zones = a.columns.intersection(b.columns)
    a_num = a.loc[common_snapshots, common_zones].apply(pd.to_numeric, errors="coerce")
    b_num = b.loc[common_snapshots, common_zones].apply(pd.to_numeric, errors="coerce")
    return a_num, b_num


def summarize_diff(low_name: str, high_name: str, low_df: pd.DataFrame, high_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    a, b = align_numeric(low_df, high_df)
    diff = b - a
    summary = pd.DataFrame(
        {
            f"mean_{low_name}": a.mean(axis=0),
            f"mean_{high_name}": b.mean(axis=0),
            f"mean_diff_{high_name}_minus_{low_name}": diff.mean(axis=0),
            "mean_abs_diff": diff.abs().mean(axis=0),
            "max_abs_diff": diff.abs().max(axis=0),
        }
    ).sort_values("mean_abs_diff", ascending=False)
    return diff, summary


def main_cli() -> None:
    # Prevent an interactive stop if workflow code contains breakpoint().
    os.environ.setdefault("PYTHONBREAKPOINT", "0")

    args = parse_args()
    if args.n_timesteps < 1:
        raise ValueError("--n-timesteps must be >= 1")

    snapshot_slice = slice(args.start_index, args.start_index + args.n_timesteps)

    # For now this comparison script targets the UA base model only.
    input_case_folder = "pypsa-eur-ua"
    input_path = get_input_networks_dir() / input_case_folder / args.variant / "nodal.nc"
    if not input_path.exists():
        raise FileNotFoundError(f"UA nodal network not found: {input_path}")

    base_nodal_net = pypsa.Network(input_path)

    output_dir = get_case_results_dir(Cases.PYPSA_EUR_UA.value) / "security-rmf-compare" / args.case / args.variant
    output_dir.mkdir(parents=True, exist_ok=True)

    sec_on_label = "sec_on_rmf_0_1"
    sec_off_label = "sec_off_rmf_0_4"

    sec_on_dir = output_dir / sec_on_label
    sec_off_dir = output_dir / sec_off_label
    sec_on_dir.mkdir(parents=True, exist_ok=True)
    sec_off_dir.mkdir(parents=True, exist_ok=True)

    print("Running scenario: security constraints ON, RMF=0.1")
    prices_sec_on, np_sec_on = run_case(
        base_nodal_net,
        sec_on_dir,
        snapshot_slice,
        security_constraints=True,
        rmf=0.1,
    )

    print("Running scenario: security constraints OFF, RMF=0.5")
    prices_sec_off, np_sec_off = run_case(
        base_nodal_net,
        sec_off_dir,
        snapshot_slice,
        security_constraints=False,
        rmf=0.5,
    )

    prices_diff, prices_summary = summarize_diff(sec_on_label, sec_off_label, prices_sec_on, prices_sec_off)
    np_diff, np_summary = summarize_diff(sec_on_label, sec_off_label, np_sec_on, np_sec_off)

    prices_sec_on.to_csv(output_dir / f"prices_{sec_on_label}.csv")
    prices_sec_off.to_csv(output_dir / f"prices_{sec_off_label}.csv")
    prices_diff.to_csv(output_dir / f"prices_diff_{sec_off_label}_minus_{sec_on_label}.csv")
    prices_summary.to_csv(output_dir / f"prices_diff_summary_{sec_off_label}_minus_{sec_on_label}_by_zone.csv")

    np_sec_on.to_csv(output_dir / f"net_positions_{sec_on_label}.csv")
    np_sec_off.to_csv(output_dir / f"net_positions_{sec_off_label}.csv")
    np_diff.to_csv(output_dir / f"net_positions_diff_{sec_off_label}_minus_{sec_on_label}.csv")
    np_summary.to_csv(output_dir / f"net_positions_diff_summary_{sec_off_label}_minus_{sec_on_label}_by_zone.csv")

    print("Saved outputs in:")
    print(f"- {output_dir}")
    if not prices_summary.empty:
        zone = prices_summary.index[0]
        val = prices_summary.iloc[0]["mean_abs_diff"]
        print(f"Largest average absolute price change: {zone} ({val:.3f} EUR/MWh)")
    if not np_summary.empty:
        zone = np_summary.index[0]
        val = np_summary.iloc[0]["mean_abs_diff"]
        print(f"Largest average absolute net-position change: {zone} ({val:.3f} MW)")


if __name__ == "__main__":
    main_cli()
