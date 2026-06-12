# pypsa-fbmc

This package adds FBMC capabilities for the pypsa package. It further introduces several methods for GSK calculation.

WARNING: While the notebooks work, at this stage of development, the package will contain bugs and is not meant for production.

## Setup Instructions

To run the FBMC module, follow these steps:

1. **Install Python 3.11.x** (e.g. from https://www.python.org/downloads/release/python-3118/)

2. **Clone the repository:**

```bash
git clone https://github.com/WouterKoksNL/pypsa-fbmc/tree/dev
cd pypsa-fbmc
```

3. **Create and activate a virtual environment:**

- On **Windows (Command Prompt)**:

```cmd
py -3.11 -m venv venv
venv\Scripts\activate.bat
```

- On **macOS/Linux**:

```bash
python3.11 -m venv venv
source venv/bin/activate
```

4. **Install dependencies:**

```bash
.\venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

5. **Activate gurobi (or another solver)**

Package included in dependencies; Instructions for licence and further installation can be found here: https://support.gurobi.com/hc/en-us/articles/14799677517585-Getting-Started-with-Gurobi-Optimizer.

It is also possible to choose another optimiser, but you will have to update the `solver =`to other options in the config. 

6. **Run the code:**

Example: 

´´´
from fbmc.settings import FBMCConfig
from fbmc.api import run_fbmc
from example_networks.main import create_case, Cases


config = FBMCConfig.from_base_yaml("config/base_config.yaml")
case_data = create_case(case=Cases.BASIC_THREE_NODE)

fbmc_result = run_fbmc(
    zonal_net=case_data['zonal_net'],
    nodal_net=case_data['nodal_net'],
    config=config,
)

print(fbmc_result.dispatch_results.generators_p)
print(fbmc_result.net_positions)
´´´

Prepared scripts can be found under /scripts. Run the minimal example using
´python -m scripts.run.minimal_example´

## Input Network Location

Input network folders are configured centrally in `src/paths.py`.

- `get_input_networks_dir()` defaults to `input_networks/`
- `get_unprocessed_input_networks_dir()` defaults to `unprocessed_input_networks/`

You can set both locations in the project file `paths.toml`:

```toml
[paths]
input_networks_dir = "input_networks"
unprocessed_input_networks_dir = "unprocessed_input_networks"
```

If these values are relative, they are resolved from the project root.

You can override these locations with environment variables:

- `PYPSA_FBMC_INPUT_NETWORKS_DIR`
- `PYPSA_FBMC_UNPROCESSED_INPUT_NETWORKS_DIR`

Environment variables take precedence over `paths.toml`. If an override path is relative, it is resolved from the project root.