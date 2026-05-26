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


def _temporal_average(prices: pd.DataFrame) -> pd.DataFrame:
	average_prices = prices.apply(pd.to_numeric, errors="coerce").mean(axis=0).dropna()
	out = average_prices.rename("avg_price").to_frame()
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


def _merge_prices_with_shapes(countries: gpd.GeoDataFrame, avg_prices: pd.DataFrame) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
	country_code_col = _select_country_code_column(countries)
	countries = countries.copy()
	countries["country_code"] = countries[country_code_col].astype(str).str.upper()
	if "name" in countries.columns:
		country_names = countries["name"].astype(str).str.upper()
		for country_name, country_code in COUNTRY_NAME_CODE_OVERRIDES.items():
			is_country = country_names.str.contains(country_name, regex=False)
			countries.loc[is_country, "country_code"] = country_code

	avg_prices = avg_prices.copy()
	avg_prices["country_code"] = avg_prices["zone"].map(_normalize_zone_code)

	merged = countries.merge(avg_prices[["country_code", "avg_price"]], on="country_code", how="left")
	return merged, avg_prices


def _plot_prices_map(
	merged: gpd.GeoDataFrame,
	avg_prices: pd.DataFrame,
	case_name: str,
	source: str,
	output_path: Path,
	minx: float = -12.0,
	maxx: float = 41.0,
	miny: float = 34.0,
	maxy: float = 59.0,
	price_limits: tuple[float, float] | None = (0.0, 110.0),
) -> None:
	fig, ax = plt.subplots(figsize=(13, 8), dpi=150)

	merged.plot(ax=ax, color="#eceff1", edgecolor="white", linewidth=0.3)
	plot_kwargs = {
		"ax": ax,
		"column": "avg_price",
		"cmap": "YlOrRd",
		"linewidth": 0.45,
		"edgecolor": "#1f2937",
		"legend": True,
		"legend_kwds": {"label": "Market price [EUR/MWh]", "shrink": 0.7},
	}
	if price_limits is not None:
		plot_kwargs["vmin"], plot_kwargs["vmax"] = price_limits

	merged.dropna(subset=["avg_price"]).plot(**plot_kwargs)

	plotted = merged.dropna(subset=["avg_price"])

	ax.set_xlim(minx, maxx)
	ax.set_ylim(miny, maxy)

	missing_zones = sorted(set(avg_prices["country_code"]) - set(plotted["country_code"]))

	ax.set_axis_off()
	ax.set_title(f"UA coupling {source.replace('_', ' ')} market prices\n{case_name}", fontsize=14, pad=16)

	if missing_zones:
		fig.text(
			0.5,
			0.03,
			f"Unmapped zones: {', '.join(missing_zones)}",
			ha="center",
			fontsize=8,
			color="#6b7280",
		)

	output_path.parent.mkdir(parents=True, exist_ok=True)
	fig.tight_layout()
	fig.savefig(output_path, bbox_inches="tight")
	plt.close(fig)


def run_plot(
	case_name: str = "pypsa-eur-ua/base",
	source: str = "clearing",
	results_root: Path | None = None,
	analysis_dir: Path | None = None,
	output_path: Path | None = None,
	geojson_path: Path | None = None,
	price_limits: tuple[float, float] | None = (0.0, 110.0),
) -> Path:
	analysis = Path(analysis_dir) if analysis_dir is not None else _default_analysis_dir(case_name, results_root)
	prices = _load_prices(analysis, source=source)
	avg_prices = _temporal_average(prices)

	shapes_path = _ensure_countries_geojson(Path(geojson_path) if geojson_path is not None else COUNTRIES_GEOJSON_PATH)
	countries = gpd.read_file(shapes_path)
	merged, normalized_avg = _merge_prices_with_shapes(countries, avg_prices)

	if output_path is None:
		out_plot = analysis / "plots" / f"{source}_market_prices_map.png"
	else:
		out_plot = Path(output_path)

	_plot_prices_map(
		merged=merged,
		avg_prices=normalized_avg,
		case_name=case_name,
		source=source,
		output_path=out_plot,
		price_limits=price_limits,
	)
	normalized_avg.to_csv(analysis / f"{source}_market_prices_temporal_average.csv", index=False)
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
	case_names = [
		# "pypsa-eur-ua/base",
		# "pypsa-eur-ua/ntc-max",
		"pypsa-eur-ua/ntc-2450",
		# "pypsa-eur-ua/disconnected",
	]
	for case_name in case_names:
		main(case_name=case_name)

