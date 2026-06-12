Critical Network Elements & Contingencies (CNECs)
=================================================

A *Critical Network Element and Contingency* (CNEC) is a pair :math:`(b, c)` where
:math:`b` is a monitored branch and :math:`c` is an outage scenario (or *"no outage"*
for N-0 elements). CNECs determine which flow constraints are included in the FBMC
optimisation.

N-0 CNECs
---------

An N-0 CNEC monitors branch :math:`b` under *normal* operating conditions (no outage).
The capacity constraint is simply:

.. math::

   -c_b \;\le\; f_b \;\le\; c_b

In FBMC terms this becomes:

.. math::

   RAM_b^{lower}
   \;\le\;
   \sum_z zPTDF_{b,z} \cdot NP_z
   \;\le\;
   RAM_b^{upper}

N-1 CNECs (security constraints)
----------------------------------

When :attr:`~fbmc.settings.FBMCConfig.add_security_constraints` is ``True``, the CNEC
set is extended with N-1 pairs. For each monitored branch :math:`b` and each outaged
branch :math:`j \ne b`, the post-contingency flow is:

.. math::

   f_b^{N\text{-}1}(j)
   = f_b^{N\text{-}0} + BODF_{b,j} \cdot f_j^{N\text{-}0}

Only contingencies with a significant impact are kept — those for which the BODF
magnitude exceeds :attr:`~fbmc.settings.FBMCConfig.security_constraint_bodf_size_threshold`
(default ``0.2``). This controls the size of the constraint matrix.

Bridge branches
---------------

Network bridges — branches whose removal disconnects the network — are always excluded
from the CNEC set because no feasible power flow exists after such an outage. These are
identified using a graph-theoretic bridge-finding algorithm before CNEC selection.

CNEC strategies
---------------

The CNEC set is controlled by :attr:`~fbmc.settings.FBMCConfig.cnec_setting`:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Strategy
     - Description
   * - ``ALL``
     - All non-bridge branches (N-0) plus all significant N-1 pairs (when security
       constraints are enabled).
   * - ``CUSTOM``
     - Only the CNECs listed in :attr:`~fbmc.settings.FBMCConfig.cne_list`.

Additionally, :attr:`~fbmc.settings.FBMCConfig.line_usage_threshold` (default ``0.2``)
can be used to filter out lightly loaded branches whose constraints are unlikely to bind.

CNEC dimensions in the code
-----------------------------

Internally, CNECs are stored as an ``xarray.Coordinates`` object:

* **N-0 CNEC** – a single coordinate ``cnec`` whose values are branch names.
* **N-1 CNEC** – a multi-index coordinate ``(cnec, outage)`` representing the branch /
  outage pair.

The zPTDF and RAM arrays carry this ``cnec`` coordinate, so each constraint row is
self-describing.

Implementation
--------------

* ``src/fbmc/core/input_parameters/cnec.py``
* ``src/fbmc/core/derived_parameters/bridge_branches.py``
* Key functions:

  - :func:`fbmc.core.input_parameters.cnec.cnec_router` – top-level dispatcher.
  - :func:`fbmc.core.input_parameters.cnec.cnec_subnet_router` – per-subnet CNEC selection.
