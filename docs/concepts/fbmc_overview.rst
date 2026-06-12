FBMC Overview
=============

Flow-Based Market Coupling (FBMC) is the capacity allocation method used in the Central
Western European (CWE) electricity market. Instead of pre-allocating fixed bilateral
transfer capacities (Net Transfer Capacities, NTCs) between zones, FBMC derives feasible
zonal schedules directly from the physical network constraints.

The algorithm implemented in this package follows the steps below.

.. _fbmc-steps:

Algorithm steps
---------------

1. **Base case** – Solve or specify the initial nodal operating point. This determines
   the reference flows on every branch
   (see :doc:`../inputs/base_case`, :doc:`ram`).

2. **GSK calculation** – Build the Generation Shift Key matrix, which maps a change in
   a zone's net position to power injections at individual buses
   (see :doc:`../inputs/gsk`).

3. **PTDF & zonal PTDF** – Compute the nodal Power Transfer Distribution Factor matrix
   from network admittances, then project it onto zones using the GSK to obtain the
   zonal PTDF (see :doc:`ptdf`).

4. **CNEC selection** – Identify the Critical Network Elements (and Contingencies)
   whose capacity constraints will be enforced (see :doc:`../inputs/cnec`).

5. **RAM calculation** – For each CNEC compute the Remaining Available Margin: the
   headroom left for cross-zonal flows after accounting for base-case flows and a
   reliability margin (see :doc:`ram`).

6. **Market clearing** – Solve the zonal dispatch optimisation subject to the FBMC
   capacity constraints

   .. math::

      RAM^{lower}_{b} \;\le\; \sum_{z} zPTDF_{b,z} \cdot NP_{z}
                             \;\le\; RAM^{upper}_{b}
      \quad \forall\, b \in \mathcal{B}_{CNEC}

   together with the global power balance :math:`\sum_z NP_z = 0`.

Relationship between key matrices
----------------------------------

.. math::

   \underbrace{\mathbf{zPTDF}}_{B \times Z}
   \;=\;
   \underbrace{\mathbf{PTDF}}_{B \times N}
   \cdot
   \underbrace{\mathbf{GSK}^{\top}}_{N \times Z}

where :math:`B` is the number of monitored branches, :math:`N` the number of buses,
and :math:`Z` the number of bidding zones.
