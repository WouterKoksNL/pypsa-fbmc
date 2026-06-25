Critical Network Elements & Contingencies (CNECs)
=================================================

A *Critical Network Element and Contingency* (CNEC) is a pair :math:`(b, c)` where
:math:`b` is a monitored branch and :math:`c` is an outage scenario (or *"no outage"*
for N-0 elements). CNECs determine which flow constraints are included in the FBMC
optimisation.

N-0 CNECs
---------

An N-0 CNEC monitors branch :math:`b` under *normal* operating conditions (no outage).
The capacity constraint is expressed via the *Remaining Available Margin* (RAM):

.. math::

   \underline{RAM}_{\ell,t} \;\le\; \sum_n z\text{PTDF}_{\ell,n}\, p_{n,t} \;\le\; \overline{RAM}_{\ell,t}
   \qquad \forall \ell \in \mathcal{C},\; \forall t \in \mathcal{T}

where the upper and lower RAM values are defined as:

.. math::

   \overline{RAM}_{\ell,t}  &= \overline{F}_\ell - F^{\mathrm{REF}}_{\ell,t} - S_{\ell}
     \qquad \forall \ell \in \mathcal{C},\; \forall t \in \mathcal{T} \\
   \underline{RAM}_{\ell,t} &= -\overline{F}_\ell - F^{\mathrm{REF}}_{\ell,t} + S_{\ell}
     \qquad \forall \ell \in \mathcal{C},\; \forall t \in \mathcal{T}

Here :math:`\overline{F}_\ell` is the thermal limit, :math:`F^{\mathrm{REF}}_{\ell,t}` is
the reference flow (computed from the reference programme), and :math:`S_{\ell}` is the
flow reliability margin (FRM) / safety slack applied to the line.

N-1 CNECs (security constraints)
----------------------------------

When :attr:`~fbmc.settings.FBMCConfig.add_security_constraints` is ``True``, the CNEC
set is extended with N-1 pairs :math:`(\ell, o)` where :math:`\ell` is a monitored branch
and :math:`o` is an outaged branch. The post-contingency flow is:

.. math::

   f_\ell^{N\text{-}1}(o)
   = f_\ell^{N\text{-}0} + BODF_{\ell,o} \cdot f_o^{N\text{-}0}

The RAM bounds for N-1 CNECs follow the same structure as N-0, but indexed over
outage scenarios as well:

.. math::

   \overline{RAM}_{\ell,o,t}  &= \overline{F}_\ell - F^{\mathrm{REF}}_{\ell,o,t} - S_{\ell,o}
     \qquad \forall (\ell,o) \in \mathcal{C},\; \forall t \in \mathcal{T} \\
   \underline{RAM}_{\ell,o,t} &= -\overline{F}_\ell - F^{\mathrm{REF}}_{\ell,o,t} + S_{\ell,o}
     \qquad \forall (\ell,o) \in \mathcal{C},\; \forall t \in \mathcal{T}

Here :math:`F^{\mathrm{REF}}_{\ell,o,t}` is the reference flow on branch :math:`\ell`
after outage :math:`o`, and :math:`S_{\ell,o}` is the FRM slack for that CNEC pair.

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
     - Only the CNECs directly passed to :attr:`~fbmc.api.run_fbmc()`

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
