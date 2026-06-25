import pypsa
import linopy as lp

from fbmc.input_network_conversions.network_conversion import nodal_to_zonal
from fbmc.core.input_checks import do_input_checks
from fbmc.core.input_parameters.main import calc_input_parameters
from fbmc.core.main import setup_fbmc_model
from fbmc.core.results_extraction import extract_model_results
from fbmc.settings import FBMCConfig
from fbmc.types import FBMCResult, DispatchResult


class FBMCAccessor:
    def __init__(self, network: pypsa.Network):
        self._n = network

    def to_zonal(self, bus_zone_mapping, **kwargs) -> pypsa.Network:
        return nodal_to_zonal(self._n, bus_zone_map=bus_zone_mapping, **kwargs)

    def create_model(self, nodal: pypsa.Network, config: FBMCConfig, gsk=None, cnecs=None) -> lp.Model:
        do_input_checks(nodal, self._n, gsk, config, cnecs_input=cnecs)
        if nodal.sub_networks.empty:
            nodal.determine_network_topology()
        input_parameters = calc_input_parameters(nodal, gsk, config, cnecs_input=cnecs)
        _, fbmc_parameters = setup_fbmc_model(self._n, input_parameters, config=config)
        self._n._fbmc_parameters = fbmc_parameters
        self._n._fbmc_base_case = input_parameters.base_case
        return self._n.model

    def results(self) -> FBMCResult:
        if self._n.model.termination_condition != "optimal":
            raise ValueError("FBMC optimization did not solve to optimality.")
        extract_model_results(self._n)
        return FBMCResult(
            zonal_net=self._n,
            net_positions=self._n.model.solution["Zone-p"],
            dispatch_results=DispatchResult(self._n),
            fbmc_parameters=self._n._fbmc_parameters,
            base_case=self._n._fbmc_base_case,
        )

doc = "Accessor for FBMC functionality on pypsa.Network objects. Provides methods to create a zonal network from a nodal network, set up and solve the FBMC model, and extract results. \
    Use `network.fbmc.to_zonal(bus_zone_mapping)` to create a zonal network, `network.fbmc.create_model(nodal_network, gsk, cnecs, config)` to set up the FBMC model, and `network.fbmc.results()` to extract results after solving."

pypsa.Network.fbmc = property(FBMCAccessor,
                              doc=doc)
