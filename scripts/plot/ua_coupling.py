from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import requests

from src.paths import PROJECT_ROOT, get_results_dir


COUNTRIES_GEOJSON_URL = "https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson"
COUNTRIES_GEOJSON_PATH = PROJECT_ROOT / "data" / "geojsons" / "countries.geojson"
COUNTRY_NAME_CODE_OVERRIDES = {
	"KOSOVO": "XK",
	"FRANCE": "FR",
}


def _default_analysis_dir(case_name: str, results_root: Path | None) -> Path:
	root = Path(results_root) if results_root is not None else get_results_dir()
	return root / "analysis" / case_name


def _ensure_countries_geojson(geojson_path: Path = COUNTRIES_GEOJSON_PATH) -> Path:
	geojson_path.parent.mkdir(parents=True, exist_ok=True)
	if geojson_path.exists():
		return geojson_path

	response = requests.get(COUNTRIES_GEOJSON_URL, timeout=30)
	response.raise_for_status()
	geojson_path.write_text(response.text, encoding="utf-8")
	return geojson_path


def _load_prices(analysis_dir: Path, source: str) -> pd.DataFrame:
	source_file = "clearing_prices.csv" if source == "clearing" else "water_valuation_prices.csv"
	return pd.read_csv(analysis_dir / source_file, index_col=0)


def _load_net_positions(analysis_dir: Path) -> pd.DataFrame:
	return pd.read_csv(analysis_dir / "net_positions_zone_p.csv", index_col=0)


def _load_load_shedding(analysis_dir: Path) -> pd.DataFrame:
	load_shedding_path = analysis_dir / "load_shedding_zone_p.csv"
	if not load_shedding_path.exists():
		return pd.DataFrame()
	return pd.read_csv(load_shedding_path, index_col=0)


def _temporal_average_by_zone(data: pd.DataFrame, value_name: str) -> pd.DataFrame:
	average_values = data.apply(pd.to_numeric, errors="coerce").mean(axis=0).dropna()
	out = average_values.rename(value_name).to_frame()
	out.index.name = "zone"
	return out.reset_index()


def _select_country_code_column(countries: gpd.GeoDataFrame) -> str:
	for candidate in [
		"ISO_A2",
		"ISO2",
		"iso_a2",
		"ADM0_A2",
		"ISO3166-1-Alpha-2",
		"iso3166-1-alpha-2",
		"id",
	]:
		if candidate in countries.columns:
			return candidate
	raise ValueError("Could not find a 2-letter country code column in countries GeoJSON")


def _normalize_zone_code(zone: str) -> str:
	return str(zone).strip().upper()


def _merge_values_with_shapes(
	countries: gpd.GeoDataFrame,
	zone_values: pd.DataFrame,
	value_col: str,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
	country_code_col = _select_country_code_column(countries)
	countries = countries.copy()
	countries["country_code"] = countries[country_code_col].astype(str).str.upper()
	if "name" in countries.columns:
		country_names = countries["name"].astype(str).str.upper()
		for country_name, country_code in COUNTRY_NAME_CODE_OVERRIDES.items():
			is_country = country_names.str.contains(country_name, regex=False)
			countries.loc[is_country, "country_code"] = country_code

	zone_values = zone_values.copy()
	zone_values["country_code"] = zone_values["zone"].map(_normalize_zone_code)

	merged = countries.merge(zone_values[["country_code", value_col]], on="country_code", how="left")
	return merged, zone_values


def _plot_metric_map(
	merged: gpd.GeoDataFrame,
	value_col: str,
	title: str,
	legend_label: str,
	output_path: Path,
	cmap: str = "YlOrRd",
	minx: float = -12.0,
	maxx: float = 41.0,
	miny: float = 34.0,
	maxy: float = 59.0,
	value_limits: tuple[float, float] | None = None,
) -> None:
	fig, ax = plt.subplots(figsize=(13, 8), dpi=150)

	merged.plot(ax=ax, color="#eceff1", edgecolor="white", linewidth=0.3)
	plot_kwargs = {
		"ax": ax,
		"column": value_col,
		"cmap": cmap,
		"linewidth": 0.45,
		"edgecolor": "#1f2937",
		"legend": True,
		"legend_kwds": {"label": legend_label, "shrink": 0.7},
	}
	if value_limits is not None:
		plot_kwargs["vmin"], plot_kwargs["vmax"] = value_limits

	merged.dropna(subset=[value_col]).plot(**plot_kwargs)

	ax.set_xlim(minx, maxx)
	ax.set_ylim(miny, maxy)

	ax.set_axis_off()
	ax.set_title(title, fontsize=14, pad=16)

	output_path.parent.mkdir(parents=True, exist_ok=True)
	fig.tight_layout()
	fig.savefig(output_path, bbox_inches="tight")
	plt.close(fig)



def plot_timeseries(
	prices, 
	output_path: Path,
	countries: list[str],
	ls: dict[str, str],
	colors: dict[str, str],
	y_label: str,
	):
	available_countries = [country for country in countries if country in prices.columns]
	if not available_countries:
		return

	plt.figure()
	for country in available_countries:
		plt.plot(prices.loc[:, country], label=country, ls=ls[country], color=colors[country])
	plt.xlabel("Time [h]")
	plt.ylabel(y_label)
	

	output_path.parent.mkdir(parents=True, exist_ok=True)
	plt.legend()
	plt.savefig(output_path, bbox_inches="tight")
	plt.close()

def run_plot(
	case_name: str = "pypsa-eur-ua/base",
	source: str = "clearing",
	results_root: Path | None = None,
	analysis_dir: Path | None = None,
	output_path: Path | None = None,
	net_position_output_path: Path | None = None,
	geojson_path: Path | None = None,
	price_limits: tuple[float, float] | None = (0.0, 110.0),
	z_limits: tuple[float, float] | None = (-3000.0, 3000.0),
) -> Path:
	analysis = Path(analysis_dir) if analysis_dir is not None else _default_analysis_dir(case_name, results_root)
	prices = _load_prices(analysis, source=source)
	net_positions = _load_net_positions(analysis)
	load_shedding = _load_load_shedding(analysis)

	avg_prices = _temporal_average_by_zone(prices, value_name="avg_price")
	avg_net_positions = _temporal_average_by_zone(net_positions, value_name="avg_net_position")

	shapes_path = _ensure_countries_geojson(Path(geojson_path) if geojson_path is not None else COUNTRIES_GEOJSON_PATH)
	countries = gpd.read_file(shapes_path)
	prices_merged, normalized_avg_prices = _merge_values_with_shapes(countries, avg_prices, value_col="avg_price")
	net_positions_merged, normalized_avg_net_positions = _merge_values_with_shapes(
		countries,
		avg_net_positions,
		value_col="avg_net_position",
	)

	if output_path is None:
		out_plot = analysis / "plots" / f"{source}_market_prices_map.png"
	else:
		out_plot = Path(output_path)
	if net_position_output_path is None:
		net_position_out_plot = analysis / "plots" / "net_positions_map.png"
	else:
		net_position_out_plot = Path(net_position_output_path)

	_plot_metric_map(
		merged=prices_merged,
		value_col="avg_price",
		title=f"UA coupling {source.replace('_', ' ')} market prices\n{case_name}",
		legend_label="Market price [EUR/MWh]",
		output_path=out_plot,
		cmap="YlOrRd",
		value_limits=price_limits,
	)
	_plot_metric_map(
		merged=net_positions_merged,
		value_col="avg_net_position",
		title=f"UA coupling net positions\n{case_name}",
		legend_label="Net position [MW]",
		output_path=net_position_out_plot,
		cmap="coolwarm_r",
		value_limits=z_limits,
	)
	normalized_avg_prices.to_csv(analysis / f"{source}_market_prices_temporal_average.csv", index=False)
	normalized_avg_net_positions.to_csv(analysis / "net_positions_temporal_average.csv", index=False)
	
	countries = ["DE", "PL", "HU", "UA"]
	ls = {country: "-" if country == "UA" else "--" for country in countries}
	colors = {
		"DE": "#6b7280",
		"PL": "#10b981",
		"HU": "#8b5cf6",
		"UA": "#ef4444",
	}
	plot_timeseries(
		prices=prices,
		output_path=analysis / f"plots/{source}_market_prices_timeseries.png",
		countries=countries,
		ls=ls,
		colors=colors,
		y_label="Market price [EUR/MWh]",
	)
	plot_timeseries(
		prices=net_positions,
		output_path=analysis / "plots/net_positions_timeseries.png",
		countries=countries,
		ls=ls,
		colors=colors,
		y_label="Net position [MW]",
	)
	if not load_shedding.empty:
		plot_timeseries(
			prices=load_shedding,
			output_path=analysis / "plots/load_shedding_timeseries.png",
			countries=countries,
			ls=ls,
			colors=colors,
			y_label="Load shedding [MW]",
		)
	return out_plot


def main(case_name: str = "pypsa-eur-ua/base") -> None:
	parser = argparse.ArgumentParser(description="Plot temporally averaged UA coupling market prices on a country map")

	# parser.add_argument("--source", choices=["clearing", "water_valuation"], default="clearing")
	parser.add_argument("--results-root", default=None)
	parser.add_argument("--analysis-dir", default=None)
	parser.add_argument("--output-path", default=None)
	parser.add_argument("--geojson-path", default=None)
	args = parser.parse_args()

	out_plot = run_plot(
		case_name=case_name,
		source="clearing",
		results_root=Path(args.results_root) if args.results_root else None,
		analysis_dir=Path(args.analysis_dir) if args.analysis_dir else None,
		output_path=Path(args.output_path) if args.output_path else None,
		geojson_path=Path(args.geojson_path) if args.geojson_path else None,
	)

	print(f"Saved plot to: {out_plot}")


if __name__ == "__main__":
	cases = [
		"pypsa-eur-ua/base/red", 
		# "pypsa-eur-ua/disconnected/red",
		# "pypsa-eur-ua/ntc-max/red",
		# "pypsa-eur-ua/ntc-2450/red",
		"pypsa-eur-ua/np-limit/red",
		]
	for case in cases:
		main(case_name=case)

