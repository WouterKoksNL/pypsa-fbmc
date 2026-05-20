from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.paths import get_results_dir


def _read_summary(case_dir: Path) -> dict:
	summary_path = case_dir / "summary.json"
	with open(summary_path, "r", encoding="utf-8") as f:
		return json.load(f)


def _read_market_prices(case_dir: Path) -> pd.DataFrame:
	prices_path = case_dir / "zonal_market_prices.csv"
	return pd.read_csv(prices_path, index_col=0)


def compare_objective_values(connected_summary: dict, disconnected_summary: dict) -> pd.DataFrame:
	connected_obj = connected_summary.get("fbmc_objective")
	disconnected_obj = disconnected_summary.get("fbmc_objective")

	obj_diff = None
	if connected_obj is not None and disconnected_obj is not None:
		obj_diff = disconnected_obj - connected_obj

	return pd.DataFrame(
		{
			"case": ["pypsa-eur-ua", "pypsa-eur-ua-disconnected", "difference(disconnected-connected)"],
			"fbmc_objective": [connected_obj, disconnected_obj, obj_diff],
		}
	)


def compare_market_prices(
	connected_prices: pd.DataFrame,
	disconnected_prices: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
	common_snapshots = connected_prices.index.intersection(disconnected_prices.index)
	common_zones = connected_prices.columns.intersection(disconnected_prices.columns)

	connected_aligned = connected_prices.loc[common_snapshots, common_zones]
	disconnected_aligned = disconnected_prices.loc[common_snapshots, common_zones]

	price_diff = disconnected_aligned - connected_aligned

	zone_summary = pd.DataFrame(
		{
			"mean_diff": price_diff.mean(axis=0),
			"abs_mean_diff": price_diff.abs().mean(axis=0),
			"max_abs_diff": price_diff.abs().max(axis=0),
		}
	)

	global_summary = pd.DataFrame(
		{
			"metric": ["mean_diff", "abs_mean_diff", "max_abs_diff"],
			"value": [
				float(price_diff.to_numpy().mean()),
				float(price_diff.abs().to_numpy().mean()),
				float(price_diff.abs().to_numpy().max()),
			],
		}
	)

	return zone_summary, global_summary


def run_analysis(
	connected_case_name: str = "pypsa-eur-ua",
	disconnected_case_name: str = "pypsa-eur-ua-disconnected",
	results_root: Path | None = None,
	output_dir: Path | None = None,
) -> dict[str, pd.DataFrame]:
	root = Path(results_root) if results_root is not None else get_results_dir()
	connected_case_dir = root / connected_case_name
	disconnected_case_dir = root / disconnected_case_name

	connected_summary = _read_summary(connected_case_dir)
	disconnected_summary = _read_summary(disconnected_case_dir)
	connected_prices = _read_market_prices(connected_case_dir)
	disconnected_prices = _read_market_prices(disconnected_case_dir)
	breakpoint()
    
	objective_comparison = compare_objective_values(connected_summary, disconnected_summary)
	zone_price_summary, global_price_summary = compare_market_prices(connected_prices, disconnected_prices)

	if output_dir is not None:
		out = Path(output_dir)
	else:
		out = root / "analysis" / f"{connected_case_name}_vs_{disconnected_case_name}"
	out.mkdir(parents=True, exist_ok=True)

	objective_comparison.to_csv(out / "objective_comparison.csv", index=False)
	zone_price_summary.to_csv(out / "market_price_zone_summary.csv")
	global_price_summary.to_csv(out / "market_price_global_summary.csv", index=False)

	return {
		"objective_comparison": objective_comparison,
		"market_price_zone_summary": zone_price_summary,
		"market_price_global_summary": global_price_summary,
	}


def main() -> None:
	parser = argparse.ArgumentParser(description="Compare connected and disconnected UA case results.")
	parser.add_argument("--connected-case", default="pypsa-eur-ua/base")
	parser.add_argument("--disconnected-case", default="pypsa-eur-ua/disconnected")
	parser.add_argument("--results-root", default=None)
	parser.add_argument("--output-dir", default=None)
	args = parser.parse_args()

	results = run_analysis(
		connected_case_name=args.connected_case,
		disconnected_case_name=args.disconnected_case,
		results_root=Path(args.results_root) if args.results_root else None,
		output_dir=Path(args.output_dir) if args.output_dir else None,
	)

	print("Objective comparison:")
	print(results["objective_comparison"])
	print("\nMarket price global summary:")
	print(results["market_price_global_summary"])


if __name__ == "__main__":
	main()
