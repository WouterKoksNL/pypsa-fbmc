run_fbmc — main entry point
===========================

.. autofunction:: fbmc.api.run_fbmc

Workflow
--------

Calling :func:`~fbmc.api.run_fbmc` executes the following pipeline:

1. **Input validation** – checks that the zonal and nodal networks are consistent.
2. **Topology detection** – runs ``determine_network_topology()`` if needed.
3. **Input parameters** –

   a. Prepares the base-case nodal network according to
      :attr:`~fbmc.settings.FBMCConfig.base_case_strategy`.
   b. Computes (or validates) the GSK matrix.
   c. Selects CNECs and optionally adds N-1 contingency rows.

4. **FBMC model setup** –

   a. Computes nodal and zonal PTDFs.
   b. Computes RAM (upper and lower) for every CNEC.
   c. Creates zone net-position variables and removes nodal balance constraints.
   d. Injects FBMC capacity constraints into the linopy model.

5. **Solve** – calls the configured solver.
6. **Result extraction** – reads optimal values back into the network and builds the
   :class:`~fbmc.types.FBMCResult` object.

Providing a custom GSK
----------------------

The ``gsk`` parameter accepts a plain dict with the structure
``{zone: {bus: weight, ...}, ...}``:

.. code-block:: python

   result = run_fbmc(
       zonal_net=zonal_net,
       nodal_net=nodal_net,
       config=config,
       gsk={"Zone_A": {"Bus1": 0.7, "Bus2": 0.3}},
   )

Omitting ``gsk`` (or passing ``None``) triggers automatic calculation according to
:attr:`~fbmc.settings.FBMCConfig.gsk_strategy`.

See also
--------

* :doc:`/concepts/fbmc_overview` for the algorithm steps.
* :class:`~fbmc.types.FBMCResult` for the return type.
* :class:`~fbmc.settings.FBMCConfig` for all configuration options.
