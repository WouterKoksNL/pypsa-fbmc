from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.paths import get_results_dir


WATER_VALUATION_RUN_NAME = "water_valuation"
CLEARING_RUN_PREFIX = "clearing_"


def _run_sort_key(run_dir: Path) -> tuple[int, str]:
	try:
		return (int(run_dir.name.removeprefix(CLEARING_RUN_PREFIX)), run_dir.name)
	except ValueError:
		return (10**9, run_dir.name)


def _list_clearing_runs(case_dir: Path) -> list[Path]:
	return sorted(case_dir.glob(f"{CLEARING_RUN_PREFIX}*"), key=_run_sort_key)


def _read_summary(case_dir: Path) -> dict:
	summary_path = case_dir / "summary.json"
	with open(summary_path, "r", encoding="utf-8") as f:
		return json.load(f)


def _read_market_prices(case_dir: Path) -> pd.DataFrame:
	prices_path = case_dir / "zonal_market_prices.csv"
	return pd.read_csv(prices_path, index_col=0)


def _read_net_positions(case_dir: Path) -> pd.DataFrame:
	net_positions_path = case_dir / "net_positions_zone_p.csv"
	return pd.read_csv(net_positions_path, index_col=0)


def _read_load_shedding(case_dir: Path) -> pd.DataFrame:
	load_shedding_path = case_dir / "load_shedding_zone_p.csv"
	if not load_shedding_path.exists():
		return pd.DataFrame()
	return pd.read_csv(load_shedding_path, index_col=0)


def _load_run_prices(run_dirs: Iterable[Path]) -> pd.DataFrame:
	price_frames = [_read_market_prices(run_dir) for run_dir in run_dirs]
	if not price_frames:
		return pd.DataFrame()
	combined_prices = pd.concat(price_frames, axis=0)
	return combined_prices.sort_index()


def _load_run_net_positions(run_dirs: Iterable[Path]) -> pd.DataFrame:
	net_position_frames = [_read_net_positions(run_dir) for run_dir in run_dirs]
	if not net_position_frames:
		return pd.DataFrame()
	combined_net_positions = pd.concat(net_position_frames, axis=0)
	return combined_net_positions.sort_index()


def _load_run_load_shedding(run_dirs: Iterable[Path]) -> pd.DataFrame:
	load_shedding_frames = [_read_load_shedding(run_dir) for run_dir in run_dirs]
	load_shedding_frames = [frame for frame in load_shedding_frames if not frame.empty]
	if not load_shedding_frames:
		return pd.DataFrame()
	combined_load_shedding = pd.concat(load_shedding_frames, axis=0)
	return combined_load_shedding.sort_index()


def _load_run_summaries(run_dirs: Iterable[Path]) -> pd.DataFrame:
	summary_rows = []
	for run_dir in run_dirs:
		summary = _read_summary(run_dir)
		summary["run"] = run_dir.name
		summary_rows.append(summary)

	if not summary_rows:
		return pd.DataFrame()

	return pd.DataFrame(summary_rows).set_index("run")


def _load_case_bundle(case_dir: Path) -> dict[str, pd.DataFrame | dict]:
	clearing_runs = _list_clearing_runs(case_dir)

	return {
		# "water_valuation_summary": _read_summary(water_valuation_dir),
		# "water_valuation_pricess": _read_market_prices(water_valuation_dir),
		"clearing_summaries": _load_run_summaries(clearing_runs),
		"clearing_prices": _load_run_prices(clearing_runs),
		"net_positions_zone_p": _load_run_net_positions(clearing_runs),
		"load_shedding_zone_p": _load_run_load_shedding(clearing_runs),
	}


def run_analysis(
	case_name: str = "pypsa-eur-ua/base",
	results_root: Path | None = None,
	output_dir: Path | None = None,
) -> dict[str, pd.DataFrame | dict]:
	root = Path(results_root) if results_root is not None else get_results_dir()
	case_dir = root / case_name
	bundle = _load_case_bundle(case_dir)

	if output_dir is not None:
		out = Path(output_dir)
	else:
		out = root / "analysis" / case_name
	out.mkdir(parents=True, exist_ok=True)

	bundle["clearing_prices"].to_csv(out / "clearing_prices.csv")
	bundle["clearing_summaries"].to_csv(out / "clearing_summaries.csv")
	bundle["net_positions_zone_p"].to_csv(out / "net_positions_zone_p.csv")
	bundle["load_shedding_zone_p"].to_csv(out / "load_shedding_zone_p.csv")
	# bundle["water_valuation_prices"].to_csv(out / "water_valuation_prices.csv")
	clearing_avg_prices = bundle["clearing_prices"].apply(pd.to_numeric, errors="coerce").mean(axis=0).to_frame("avg_price")
	load_shedding_avg = bundle["load_shedding_zone_p"].apply(pd.to_numeric, errors="coerce").mean(axis=0).to_frame("avg_load_shedding")
	# water_valuation_avg_prices = (
	# 	bundle["water_valuation_prices"].apply(pd.to_numeric, errors="coerce").mean(axis=0).to_frame("avg_price")
	# )
	clearing_avg_prices.to_csv(out / "clearing_prices_temporal_average.csv")
	load_shedding_avg.to_csv(out / "load_shedding_temporal_average.csv")
	# water_valuation_avg_prices.to_csv(out / "water_valuation_prices_temporal_average.csv")
	# (out / "water_valuation_summary.json").write_text(
	# 	json.dumps(bundle["water_valuation_summary"], indent=2),
	# 	encoding="utf-8",
	# )

	return {
		"case_name": pd.DataFrame({"case_name": [case_name]}),
		"clearing_prices": bundle["clearing_prices"],
		"clearing_prices_temporal_average": clearing_avg_prices,
		"clearing_summaries": bundle["clearing_summaries"],
		"net_positions_zone_p": bundle["net_positions_zone_p"],
		"load_shedding_zone_p": bundle["load_shedding_zone_p"],
		"load_shedding_temporal_average": load_shedding_avg,
		# "water_valuation_prices": bundle["water_valuation_prices"],
		# "water_valuation_prices_temporal_average": water_valuation_avg_prices,
		# "water_valuation_summary": pd.DataFrame([bundle["water_valuation_summary"]]),
	}


def main(case_name, results_root, output_dir) -> None:

	case_output_dir = None
	if output_dir:
		case_output_dir = Path(output_dir) / case_name

	results = run_analysis(
		case_name=case_name,
		results_root=Path(results_root) if results_root else None,
		output_dir=case_output_dir,
	)

	print(f"Case: {case_name}")
	print("Clearing prices:")
	print(results["clearing_prices"])
	print()
	# print(results["water_valuation_summary"])
	print()


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Analyze split UA coupling results for one or more cases.")
	
	parser.add_argument("--results-root", default=None)
	parser.add_argument("--output-dir", default=None)
	args = parser.parse_args()
	cases = [
		"pypsa-eur-ua/base/red", 
		# "pypsa-eur-ua/disconnected/red",
		# "pypsa-eur-ua/ntc-max/red",
		# "pypsa-eur-ua/ntc-2450/red",
		"pypsa-eur-ua/np-limit/red",
		]
	for case_name in cases:
		main(case_name, results_root=args.results_root, output_dir=args.output_dir)
