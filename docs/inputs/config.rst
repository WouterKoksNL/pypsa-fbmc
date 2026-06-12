Configuration — FBMCConfig
==========================

.. autoclass:: fbmc.settings.FBMCConfig
   :members:
   :undoc-members:

.. autofunction:: fbmc.settings.merge_config_overrides

Loading configuration
---------------------

The recommended way to create a config is to load a YAML file and then apply any
programmatic overrides:

.. code-block:: python

   from fbmc import FBMCConfig, merge_config_overrides

   config = FBMCConfig.from_base_yaml("config/base_config.yaml")

   config = merge_config_overrides(config, {
       "reliability_margin_factor": 0.10,
       "add_security_constraints": False,
       "solver_kwargs": {"solver_name": "highs"},
   })

YAML format
-----------

The base config YAML file lives at ``config/base_config.yaml``. All top-level keys
correspond directly to :class:`FBMCConfig` field names:

.. code-block:: yaml

   reliability_margin_factor: 0.05
   min_ram: 0.0
   gsk_strategy: ADJUSTABLE_CAP
   gsk_kwargs:
     ADJUSTABLE_CAP:
       adjustable_carriers: [CCGT, coal, lignite, OCGT]
   base_case_strategy: NODAL_OPTIMUM
   add_security_constraints: true
   solver_kwargs:
     solver_name: highs

Parameter reference
-------------------

RAM
~~~

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Parameter
     - Default
     - Description
   * - ``reliability_margin_factor``
     - ``0.0``
     - FRM as a fraction of branch capacity; reduces available RAM on every CNEC.
       Must be in [0, 1].
   * - ``min_ram``
     - ``0.0``
     - Minimum RAM floor as a fraction of capacity. Ensures cross-zonal headroom
       is always at least this fraction even on heavily loaded branches.

CNEC selection
~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Parameter
     - Default
     - Description
   * - ``cnec_setting``
     - ``ALL``
     - :class:`~fbmc.enums.CNECStrategy` — ``ALL`` or ``CUSTOM``.
     - Branches loaded below this fraction of capacity are excluded from the CNEC set.
   * - ``cne_list``
     - ``None``
     - Explicit list of branch names when using ``CNECStrategy.CUSTOM``.
   * - ``add_security_constraints``
     - ``True``
     - Include N-1 contingency CNECs.
   * - ``security_constraint_bodf_size_threshold``
     - ``0.2``
     - Minimum BODF magnitude to include an N-1 CNEC row.
   * - ``security_constraint_bodf_columnwise_matrix_size_limit``
     - ``5 000 000``
     - Memory guard: maximum number of elements in the BODF matrix column.

GSK
~~~

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Parameter
     - Default
     - Description
   * - ``gsk_strategy``
     - ``CURRENT_GENERATION``
     - :class:`~fbmc.enums.GSKStrategy` — how bus-level weights are computed.
   * - ``gsk_kwargs``
     - see below
     - Strategy-specific keyword arguments (nested dict keyed by strategy name).

Default ``gsk_kwargs``:

.. code-block:: python

   {
       "ADJUSTABLE_CAP": {
           "adjustable_carriers": ("CCGT", "coal", "lignite", "OCGT", "oil"),
       },
       "ITERATIVE_UNCERTAINTY": {
           "uncertain_carriers": ("offshore-wind", "onshore-wind"),
           "num_scenarios": 100,
           "gen_variation_std_dev": 0.5,
           "load_variation_std_dev": 0.5,
       },
       "ITERATIVE_FBMC": {
           "uncertain_carriers": ("offshore-wind", "onshore-wind"),
           "num_scenarios": 100,
           "max_gsk_iterations": 5,
           "initial_gsk_strategy": "BUS_P",
           "gen_variation_std_dev": 0.5,
           "load_variation_std_dev": 0.5,
       },
       "MERIT_ORDER": {"standard_deviation": 5},
   }

Base case
~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Parameter
     - Default
     - Description
   * - ``base_case_strategy``
     - ``ZERO_FLOWS``
     - :class:`~fbmc.enums.BaseCaseStrategy` — how the reference operating point is set.
   * - ``marginal_cost_load_shedding``
     - ``1e5``
     - Value of lost load (€/MWh) used in nodal optimisations.

Solver
~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Parameter
     - Default
     - Description
   * - ``solver_kwargs``
     - ``{"solver_name": "gurobi"}``
     - Passed directly to ``pypsa.Network.optimize``. Use ``"highs"`` for the
       open-source alternative.
   * - ``create_model_kwargs``
     - ``{}``
     - Passed to ``pypsa.Network.optimize.create_model()``.

Market design (Ukraine coupling)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 40 10 50

   * - Parameter
     - Default
     - Description
   * - ``transfer_limit_UA_flag``
     - ``False``
     - Apply an absolute limit on total transfer volume to/from Ukraine.
   * - ``transfer_limit_EUR_UA``
     - ``None``
     - Forward transfer limit EUR→UA (MW).
   * - ``transfer_limit_UA_EUR``
     - ``None``
     - Backward transfer limit UA→EUR (MW).
   * - ``net_position_limit_UA_flag``
     - ``False``
     - Apply lower/upper bounds on Ukraine's net position.
   * - ``net_position_UA_lower_limit``
     - ``None``
     - Lower bound on Ukraine net position (MW).
   * - ``net_position_UA_upper_limit``
     - ``None``
     - Upper bound on Ukraine net position (MW).
   * - ``upper_ram_only_flag``
     - ``False``
     - Enforce only upper RAM constraints (no lower bound).
