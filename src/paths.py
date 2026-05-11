import os
import tomllib
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "paths.toml"


@lru_cache(maxsize=1)
def _load_paths_config() -> dict[str, str]:
    if not CONFIG_FILE.exists():
        return {}

    with open(CONFIG_FILE, "rb") as f:
        config = tomllib.load(f)

    paths_config = config.get("paths", {})
    return {
        "input_networks_dir": paths_config.get("input_networks_dir"),
        "unprocessed_input_networks_dir": paths_config.get("unprocessed_input_networks_dir"),
    }


def _resolve_from_project(path_value: str | Path, default: Path) -> Path:
    if path_value is None:
        return default

    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def get_input_networks_dir() -> Path:
    file_path = _load_paths_config().get("input_networks_dir")
    env_path = os.getenv("PYPSA_FBMC_INPUT_NETWORKS_DIR")
    return _resolve_from_project(env_path or file_path, PROJECT_ROOT / "input_networks")


def get_unprocessed_input_networks_dir() -> Path:
    file_path = _load_paths_config().get("unprocessed_input_networks_dir")
    env_path = os.getenv("PYPSA_FBMC_UNPROCESSED_INPUT_NETWORKS_DIR")
    return _resolve_from_project(env_path or file_path, PROJECT_ROOT / "unprocessed_input_networks")


def get_case_input_dir(case_name: str) -> Path:
    return get_input_networks_dir() / case_name