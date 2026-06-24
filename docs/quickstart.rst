Quick Start
===========

Installation
------------

Requires Python 3.11 or later.

.. code-block:: bash

   git clone https://github.com/WouterKoksNL/pypsa-fbmc
   cd pypsa-fbmc
   pip install -e .

You also need a supported LP/MIP solver. The default is **Gurobi**; a free academic
licence is available from `gurobi.com <https://www.gurobi.com>`_. Any solver supported
by `linopy <https://linopy.readthedocs.io>`_ can be used by changing ``solver_name``
in the config.

Running the minimal example
---------------------------

.. code-block:: python

   from fbmc import run_fbmc, FBMCConfig
   from example_networks.main import create_case, Cases

   config = FBMCConfig.from_base_yaml("config/base_config.yaml")
   case_data = create_case(case=Cases.BASIC_THREE_NODE)

   result = run_fbmc(
       zonal_net=case_data["zonal_net"],
       nodal_net=case_data["nodal_net"],
       config=config,
   )

   print(result.net_positions)       # zone net positions per snapshot
   print(result.dispatch_results)    # generator / storage dispatch

What you get back
-----------------

:func:`fbmc.run_fbmc` returns an :class:`~fbmc.types.FBMCResult` with:

* **net_positions** – ``DataFrame[snapshots × zones]`` of zone net positions (MW).
* **dispatch_results** – generator dispatch, storage dispatch, link flows, storage
  levels, and (if LP) water values.
* **fbmc_parameters** – per-subnet zonal PTDFs and RAM values, for inspection or
  post-processing.
* **zonal_net** – the solved zonal PyPSA network with all time-series results attached.
* **base_case** – the nodal network in its base-case state (used to derive PTDFs and RAM).

Configuring the run
-------------------

All options live in :class:`~fbmc.settings.FBMCConfig`. The fastest way to customise
is to load the YAML and override individual fields programmatically:

.. code-block:: python

   from fbmc import FBMCConfig, merge_config_overrides
   from fbmc.enums import GSKStrategy, BaseCaseStrategy

   config = FBMCConfig.from_base_yaml()

   config = merge_config_overrides(config, {
       "gsk_strategy": GSKStrategy.ADJUSTABLE_CAP,
       "base_case_strategy": BaseCaseStrategy.NODAL_OPTIMUM,
       "reliability_margin_factor": 0.10,
       "solver_kwargs": {"solver_name": "highs"},
   })

See :doc:`api/config` for a full description of every parameter.

Providing a custom GSK
----------------------

If you already have GSK values, pass them directly as a dict
``{zone_name: {bus_name: weight}}``:

.. code-block:: python

   gsk = {
       "Zone_A": {"Bus_A1": 0.6, "Bus_A2": 0.4},
       "Zone_B": {"Bus_B1": 1.0},
   }

   result = run_fbmc(zonal_net, nodal_net, config, gsk=gsk)


