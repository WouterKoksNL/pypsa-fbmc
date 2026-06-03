import os
import tomllib
from functools import lru_cache
from pathlib import Path


CONFIG_FILE = Path("paths.toml")


@lru_cache(maxsize=1)
def _load_paths_config() -> dict[str, str]:
    config_path = Path.cwd() / "paths.toml"
    if not config_path.exists():
        return {}

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    paths_config = config.get("paths", {})
    return {
        "input_networks_dir": paths_config.get("input_networks_dir"),
        "unprocessed_input_networks_dir": paths_config.get("unprocessed_input_networks_dir"),
        "results_dir": paths_config.get("results_dir"),
    }


def _resolve_path(path_value: str | Path, default: Path) -> Path:
    if path_value is None:
        return default

    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def get_input_networks_dir() -> Path:
    file_path = _load_paths_config().get("input_networks_dir")
    env_path = os.getenv("PYPSA_FBMC_INPUT_NETWORKS_DIR")
    return _resolve_path(env_path or file_path, Path.cwd() / "inputs")


def get_unprocessed_input_networks_dir() -> Path:
    file_path = _load_paths_config().get("unprocessed_input_networks_dir")
    env_path = os.getenv("PYPSA_FBMC_UNPROCESSED_INPUT_NETWORKS_DIR")
    return _resolve_path(env_path or file_path, Path.cwd() / "inputs" / "unprocessed")


def get_case_input_dir(case_name: str) -> Path:
    return get_input_networks_dir() / case_name

def get_results_dir() -> Path:
    file_path = _load_paths_config().get("results_dir")
    env_path = os.getenv("PYPSA_FBMC_RESULTS_DIR")
    return _resolve_path(env_path or file_path, Path.cwd() / "results")

def get_case_results_dir(case_name: str) -> Path:
    return get_results_dir() / case_name
