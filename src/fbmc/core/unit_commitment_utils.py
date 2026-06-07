import logging
import pypsa
import pandas as pd

from ..types import DispatchResult


def _extract_commitment_status(
        zonal_net: pypsa.Network,
        dispatch_results: DispatchResult,
    ) -> pd.DataFrame:
    """Return per-snapshot commitment status (True=on, False=off)."""
    snapshots = zonal_net.snapshots
    generators = zonal_net.generators.index
    if zonal_net.model is not None and hasattr(zonal_net.model, "solution") and "Generator-status" in zonal_net.model.solution:
        status_raw = zonal_net.model.solution["Generator-status"].to_pandas()
        if isinstance(status_raw, pd.Series):
            if isinstance(status_raw.index, pd.MultiIndex):
                status = status_raw.unstack()
            else:
                status = status_raw.to_frame().T
        else:
            status = status_raw
        status = status.reindex(index=snapshots, columns=generators, fill_value=0.0)
        return status > 0.5

    # Fallback if status variable is not available: infer on/off from dispatch.
    dispatch = dispatch_results.generators_p.reindex(index=snapshots, columns=generators, fill_value=0.0)
    return dispatch > 1e-6


def _fix_commitment_schedule_and_disable_uc(
        zonal_net: pypsa.Network,
        dispatch_results: DispatchResult,
    ) -> None:
    """Fix on/off schedule from UC run and disable UC binaries.

    For generators that are off, set p_max_pu = 0 and p_min_pu = 0.
    For generators that are on, keep p_max_pu and p_min_pu as in the UC parametrization.
    Ramp-rate parameters are left unchanged and therefore still active in the LP rerun.
    """
    snapshots = zonal_net.snapshots
    generators = zonal_net.generators.index
    status_on = _extract_commitment_status(zonal_net, dispatch_results)

    p_min_uc = zonal_net.get_switchable_as_dense("Generator", "p_min_pu").reindex(index=snapshots, columns=generators, fill_value=0.0)
    p_max_uc = zonal_net.get_switchable_as_dense("Generator", "p_max_pu").reindex(index=snapshots, columns=generators, fill_value=1.0)

    zonal_net.generators_t.p_min_pu = p_min_uc.where(status_on, 0.0)
    zonal_net.generators_t.p_max_pu = p_max_uc.where(status_on, 0.0)
    zonal_net.generators.loc[:, "committable"] = False
