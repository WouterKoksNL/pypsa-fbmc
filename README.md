# pypsa-fbmc

This package adds FBMC capabilities for the pypsa package. It further introduces several methods for GSK calculation.

## Documentation

Initial documentation can be found at [pypsa-fbmc.readthedocs.io](https://pypsa-fbmc.readthedocs.io/en/latest/).


## Setup Instructions

To run the FBMC module, follow these steps:

1. **Install Python 3.11.x** 
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


```python
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

print(fbmc_result.dispatch_results)
print(fbmc_result.net_positions)
```


