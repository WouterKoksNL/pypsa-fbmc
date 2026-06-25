Quick Start
===========

Installation
------------

Requires Python 3.11 or later.

.. code-block:: bash

   git clone https://github.com/WouterKoksNL/pypsa-fbmc
   pip install ./pypsa-fbmc

You also need a supported LP/MIP solver. The default is **Gurobi**; a free academic
licence is available from `gurobi.com <https://www.gurobi.com>`_. Any solver supported
by `linopy <https://linopy.readthedocs.io>`_ can be used by changing ``solver_name``
in the config.

Running the minimal example
---------------------------

Importing :mod:`fbmc` registers a ``.fbmc`` accessor on every :class:`pypsa.Network`.
The workflow is:

1. Build nodal and zonal networks.
2. **Create the FBMC model** – attach FBMC capacity constraints to the zonal network's
   linopy model.
3. **Solve** – call the standard PyPSA/linopy solver.
4. **Extract results** – read optimal values back into the network.

.. code-block:: python

   import pypsa
   import fbmc                          # registers pypsa.Network.fbmc
   from fbmc import FBMCConfig

   # --- build a nodal network ---
   nodal_net = pypsa.Network()
   nodal_net.set_snapshots(["1", "2"])
   nodal_net.add("Bus", ["A1", "B1", "B2"])
   nodal_net.buses.loc[:, "zone_name"] = ["A", "B", "B"]
   nodal_net.add("Line", "B1-A1", bus0="B1", bus1="A1", x=1, s_nom=12)
   nodal_net.add("Line", "B1-B2", bus0="B1", bus1="B2", x=1, s_nom=12)
   nodal_net.add("Line", "A1-B2", bus0="A1", bus1="B2", x=1, s_nom=12)
   nodal_net.add("Generator", "gen_A1", bus="A1", p_nom=100, marginal_cost=400)
   nodal_net.add("Generator", "gen_B1", bus="B1", p_nom=100, marginal_cost=100)
   nodal_net.add("Generator", "gen_B2", bus="B2", p_nom=100, marginal_cost=200)
   nodal_net.add("Load", "load_A1", bus="A1", p_set=[15, 15])

   # --- derive the zonal network (one bus per zone) ---
   zonal_net = nodal_net.fbmc.to_zonal(nodal_net.buses["zone_name"])

   # --- create model, solve, extract results ---
   config = FBMCConfig.from_base_yaml()
   zonal_net.fbmc.create_model(nodal_net, config=config)
   zonal_net.model.solve(**config.solver_kwargs)
   result = zonal_net.fbmc.results()

   print(result.dispatch_results)
   print(result.net_positions)

What you get back
-----------------

:meth:`~fbmc.accessor.FBMCAccessor.results` returns an :class:`~fbmc.types.FBMCResult`
with:

* **net_positions** – ``DataArray[snapshot × Zone]`` of zone net positions (MW).
* **dispatch_results** – :class:`~fbmc.types.DispatchResult` with generator dispatch,
  storage dispatch, link flows, storage levels, and (if LP) water values.
* **fbmc_parameters** – per-subnet zonal PTDFs and RAM values, for inspection or
  post-processing.
* **zonal_net** – the solved zonal PyPSA network with all time-series results attached.
* **base_case** – the nodal network in its base-case state (used to derive PTDFs and RAM).

Configuring the run
-------------------

All options live in :class:`~fbmc.settings.FBMCConfig`. The default configuration is
loaded from ``config/base_config.yaml`` via :meth:`~fbmc.settings.FBMCConfig.from_base_yaml`
(built-in defaults are used if the file is absent). To override individual fields:

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

Pass GSK values directly as a ``{zone_name: {bus_name: weight}}`` dict
(or a snapshot-keyed dict of such dicts for time-varying GSKs):

.. code-block:: python

   gsk = {
       "Zone_A": {"Bus_A1": 0.6, "Bus_A2": 0.4},
       "Zone_B": {"Bus_B1": 1.0},
   }

   zonal_net.fbmc.create_model(nodal_net, config=config, gsk=gsk)
   zonal_net.model.solve(**config.solver_kwargs)
   result = zonal_net.fbmc.results()
