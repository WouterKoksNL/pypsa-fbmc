from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

from src.paths import PROJECT_ROOT, get_results_dir


COUNTRIES_GEOJSON_URL = "https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson"
COUNTRIES_GEOJSON_PATH = PROJECT_ROOT / "data" / "geojsons" / "countries.geojson"
COUNTRY_NAME_CODE_OVERRIDES = {
	"KOSOVO": "XK",
	"FRANCE": "FR",
}

GENERATION_CARRIER_COLORS = {
	"nuclear": "#8e7cc3",
	"coal": "#4b5563",
	"lignite": "#374151",
	"oil": "#1f2937",
	"ccgt": "#f97316",
	"ocgt": "#fb923c",
	"gas": "#f97316",
	"biomass": "#16a34a",
	"waste": "#65a30d",
	"geothermal": "#b45309",
	"hydro": "#0ea5e9",
	"ror": "#38bdf8",
	"hydropower": "#0ea5e9",
	"onwind": "#22c55e",
	"onshore-wind": "#22c55e",
	"offwind-ac": "#14b8a6",
	"offwind-dc": "#0f766e",
	"offwind-float": "#2dd4bf",
	"offshore-wind": "#14b8a6",
	"solar": "#facc15",
	"solar-hsat": "#eab308",
	"load-shedding": "#dc2626",
	"unknown": "#9ca3af",
}

GENERATION_FALLBACK_COLORS = [
	"#64748b",
	"#0d9488",
	"#2563eb",
	"#d97706",
	"#7c3aed",
	"#be123c",
	"#0f766e",
	"#475569",
]

GENERATION_STACK_ORDER = {
	"nuclear": 10,
	"lignite": 20,
	"coal": 30,
	"ccgt": 40,
	"ocgt": 50,
	"gas": 50,
	"geothermal": 60,
	"biomass": 70,
	"waste": 80,
	"hydro": 90,
	"hydropower": 90,
	"ror": 100,
	"offwind-ac": 110,
	"offwind-dc": 120,
	"offwind-float": 130,
	"offshore-wind": 120,
	"onwind": 140,
	"onshore-wind": 140,
	"solar": 150,
	"solar-hsat": 160,
	"oil": 170,
	"unknown": 180,
	"load-shedding": 999,
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


def _load_generation_mix(analysis_dir: Path) -> pd.DataFrame:
	generation_mix_path = analysis_dir / "generation_mix.csv"
	if not generation_mix_path.exists():
		return pd.DataFrame()
	try:
		return pd.read_csv(generation_mix_path, index_col=0, header=[0, 1])
	except pd.errors.EmptyDataError:
		return pd.DataFrame()


def _load_storage_mix(analysis_dir: Path) -> pd.DataFrame:
	storage_mix_path = analysis_dir / "storage_mix.csv"
	if not storage_mix_path.exists():
		return pd.DataFrame()
	try:
		return pd.read_csv(storage_mix_path, index_col=0, header=[0, 1])
	except pd.errors.EmptyDataError:
		return pd.DataFrame()


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


def _normalize_carrier_name(carrier: str) -> str:
	return str(carrier).strip().lower().replace("_", "-")


def _carrier_color(carrier: str, fallback_index: int) -> str:
	normalized = _normalize_carrier_name(carrier)
	if normalized in GENERATION_CARRIER_COLORS:
		return GENERATION_CARRIER_COLORS[normalized]
	return GENERATION_FALLBACK_COLORS[fallback_index % len(GENERATION_FALLBACK_COLORS)]


def _sort_generation_mix_columns(columns: pd.Index) -> list[str]:
	def _sort_key(carrier: str) -> tuple[int, str]:
		normalized = _normalize_carrier_name(carrier)
		priority = GENERATION_STACK_ORDER.get(normalized, 500)
		return priority, normalized

	column_names = [str(col) for col in columns]
	return sorted(column_names, key=_sort_key)


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


def _prepare_generation_mix(generation_mix: pd.DataFrame, country: str | None = None) -> pd.DataFrame:
	if generation_mix.empty:
		return pd.DataFrame()

	if not isinstance(generation_mix.columns, pd.MultiIndex):
		return generation_mix.copy()

	if country is None:
		mix = generation_mix.T.groupby(level=1).sum().T
		return mix.sort_index(axis=1)

	country_code = _normalize_zone_code(country)
	country_generation_mix = generation_mix.loc[:, generation_mix.columns.get_level_values(0) == country_code]
	if country_generation_mix.empty:
		return pd.DataFrame()

	mix = country_generation_mix.T.groupby(level=1).sum().T
	return mix.sort_index(axis=1)


def _prepare_storage_mix(storage_mix: pd.DataFrame, country: str | None = None) -> pd.DataFrame:
	if storage_mix.empty:
		return pd.DataFrame()

	if not isinstance(storage_mix.columns, pd.MultiIndex):
		mix = storage_mix.copy()
		mix.columns = [f"storage:{str(column)}" for column in mix.columns]
		return mix

	if country is None:
		mix = storage_mix.T.groupby(level=1).sum().T
	else:
		country_code = _normalize_zone_code(country)
		country_storage_mix = storage_mix.loc[:, storage_mix.columns.get_level_values(0) == country_code]
		if country_storage_mix.empty:
			return pd.DataFrame()
		mix = country_storage_mix.T.groupby(level=1).sum().T

	mix = mix.sort_index(axis=1)
	mix.columns = [f"storage:{str(column)}" for column in mix.columns]
	return mix


def _combine_generation_and_storage_mix(
	generation_mix: pd.DataFrame,
	storage_mix: pd.DataFrame,
) -> pd.DataFrame:
	if generation_mix.empty and storage_mix.empty:
		return pd.DataFrame()
	if generation_mix.empty:
		return storage_mix.copy()
	if storage_mix.empty:
		return generation_mix.copy()

	combined = pd.concat([generation_mix, storage_mix], axis=1).fillna(0.0)
	return combined


def _extract_country_net_position(net_positions: pd.DataFrame, country: str | None) -> pd.Series | None:
	if country is None or net_positions.empty:
		return None

	country_code = _normalize_zone_code(country)
	if country_code not in net_positions.columns:
		return None

	return pd.to_numeric(net_positions.loc[:, country_code], errors="coerce")


def _plot_generation_mix(
	generation_mix: pd.DataFrame,
	output_path: Path,
	country: str | None = None,
	net_position: pd.Series | None = None,
) -> None:
	if generation_mix.empty:
		return

	ordered_columns = _sort_generation_mix_columns(generation_mix.columns)
	generation_mix = generation_mix.loc[:, ordered_columns]

	fig, ax = plt.subplots(figsize=(13, 8), dpi=150)
	x_values = np.arange(len(generation_mix.index)) / 24.0
	color_cycle = [_carrier_color(str(carrier), index) for index, carrier in enumerate(generation_mix.columns)]
	ax.stackplot(
		x_values,
		generation_mix.to_numpy().T,
		labels=generation_mix.columns,
		colors=color_cycle,
	)
	ax.set_xlabel("Time [days]")
	ax.set_ylabel("Generation [MW]")
	ax.tick_params(axis="x", rotation=45)
	if net_position is not None:
		net_position = net_position.reindex(generation_mix.index)
		ax_net = ax.twinx()
		ax_net.plot(
			x_values,
			net_position.to_numpy(),
			color="#111827",
			linewidth=1.6,
			label="Net position",
		)
		ax_net.set_ylabel("Net position [MW]", color="#111827")
		ax_net.tick_params(axis="y", labelcolor="#111827")
		handles, labels = ax.get_legend_handles_labels()
		net_handles, net_labels = ax_net.get_legend_handles_labels()
		ax.legend(handles + net_handles, labels + net_labels, loc="upper left", bbox_to_anchor=(1.02, 1.0))
	else:
		ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0))
	if country is None:
		title = "Generation and storage power mix by carrier\nAll countries"
	else:
		title = f"Generation and storage power mix by carrier\n{_normalize_zone_code(country)}"
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

	fig, ax = plt.subplots()
	for country in available_countries:
		x_values = np.arange(len(prices.loc[:, country])) / 24.0
		ax.plot(x_values, prices.loc[:, country], label=country, ls=ls[country], color=colors[country])
	ax.set_xlabel("Time [days]")
	ax.set_ylabel(y_label)
	ax.tick_params(axis="x", rotation=45)
	

	output_path.parent.mkdir(parents=True, exist_ok=True)
	ax.legend()
	fig.savefig(output_path, bbox_inches="tight")
	plt.close(fig)

def run_plot(
	case_name: str = "pypsa-eur-ua/base",
	source: str = "clearing",
	country: str | None = None,
	results_root: Path | None = None,
	analysis_dir: Path | None = None,
	output_path: Path | None = None,
	net_position_output_path: Path | None = None,
	generation_mix_output_path: Path | None = None,
	geojson_path: Path | None = None,
	price_limits: tuple[float, float] | None = (0.0, 300.0),
	z_limits: tuple[float, float] | None = (-4000.0, 4000.0),
) -> Path:
	analysis = Path(analysis_dir) if analysis_dir is not None else _default_analysis_dir(case_name, results_root)
	prices = _load_prices(analysis, source=source)
	net_positions = _load_net_positions(analysis)
	load_shedding = _load_load_shedding(analysis)
	generation_mix = _load_generation_mix(analysis)
	storage_mix = _load_storage_mix(analysis)

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
	if generation_mix_output_path is None:
		if country is None:
			generation_mix_out_plot = analysis / "plots" / "generation_mix.png"
		else:
			generation_mix_out_plot = analysis / "plots" / f"generation_mix_{_normalize_zone_code(country)}.png"
	else:
		generation_mix_out_plot = Path(generation_mix_output_path)

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
	generation_mix = _prepare_generation_mix(generation_mix, country=country)
	storage_mix = _prepare_storage_mix(storage_mix, country=country)
	combined_mix = _combine_generation_and_storage_mix(generation_mix, storage_mix)
	country_net_position = _extract_country_net_position(net_positions, country=country)
	_plot_generation_mix(
		generation_mix=combined_mix,
		output_path=generation_mix_out_plot,
		country=country,
		net_position=country_net_position,
	)
	return out_plot


def main(case_name: str = "pypsa-eur-ua/base") -> None:
	parser = argparse.ArgumentParser(description="Plot temporally averaged UA coupling market prices on a country map")

	# parser.add_argument("--source", choices=["clearing", "water_valuation"], default="clearing")
	parser.add_argument("--country", default=None)
	parser.add_argument("--results-root", default=None)
	parser.add_argument("--analysis-dir", default=None)
	parser.add_argument("--output-path", default=None)
	parser.add_argument("--generation-mix-output-path", default=None)
	parser.add_argument("--geojson-path", default=None)
	args = parser.parse_args()

	out_plot = run_plot(
		case_name=case_name,
		source="clearing",
		country=args.country,
		results_root=Path(args.results_root) if args.results_root else None,
		analysis_dir=Path(args.analysis_dir) if args.analysis_dir else None,
		output_path=Path(args.output_path) if args.output_path else None,
		generation_mix_output_path=Path(args.generation_mix_output_path) if args.generation_mix_output_path else None,
		geojson_path=Path(args.geojson_path) if args.geojson_path else None,
	)

	print(f"Saved plot to: {out_plot}")


if __name__ == "__main__":
	cases = [
		# "pypsa-eur-ua/base/red", 
		# "pypsa-eur-ua/disconnected/redload",
		# "pypsa-eur-ua/ntc-max/redload",
		"pypsa-eur-ua/ntc-2450/red",
		# "pypsa-eur-ua/np-limit/red",
		# "pypsa-eur-ua/base/test", 
		]
	for case in cases:
		main(case_name=case)

