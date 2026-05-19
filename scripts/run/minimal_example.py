from pathlib import Path

from src.config import FBMCConfig
from main import main
from src.case_creation.main import Cases


config_path = Path("config/base_config.yaml")
config = FBMCConfig.from_base_yaml(config_path)
obj = main(
    save_path=Path("results/minimal_example"),
    case_name=Cases.BASIC_THREE_NODE, 
    config=config,
    load_case_flag=False,
)  
print("Zonal market objective: ", obj)