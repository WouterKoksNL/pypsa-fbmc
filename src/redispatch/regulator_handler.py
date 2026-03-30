
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 26 19:04:55 2024

@author: wouterko
"""

import pypsa
import pandas as pd
from pypsa.descriptors import get_switchable_as_dense as as_dense


SMALL_NUMBER_OPTIMIZATION = 1e-4  # limit for optimization stability


class RegulatorHandler:
    """Class handling up- and downregulators in a network. """

    up_identifier_str = "_up"  # suffix attached to upregulators' index to identify them
    down_identifier_str = "_dn"  # suffix attached to downregulators' index to identify them
    

    def __init__(
        self,
        net: pypsa.Network,
        gens_p_old: pd.DataFrame,
        flex_gens_up: pd.Series,
        flex_gens_down: pd.Series,

        stage_identifier_str: str = '_rd',
        alpha_mc: None | float | pd.Series = None,
        da_marginal_cost: None | pd.DataFrame = None,
        set_downreg_price_to_marginal_cost: bool = True, 
    ):
        self.net: pypsa.Network = net  # net to add up- and downregulators to. Can be zonal or nodal
        
        self.gens_p_old: pd.DataFrame = gens_p_old
        self.flex_gens_up: pd.Series = flex_gens_up
        self.flex_gens_down: pd.Series = flex_gens_down

        self.alpha_mc: None | float | pd.Series = alpha_mc  # float or pd.DataFrame
        self.stage_identifier_str: str = stage_identifier_str  # a suffix that will be added to generator names to identify it as redispatch up/downregulation.
        self.da_marginal_cost: None | pd.DataFrame = da_marginal_cost  # marginal cost without flexibility cost
        self.set_downreg_price_to_marginal_cost: bool = set_downreg_price_to_marginal_cost  # whether to set downregulation price to marginal cost of the generator

        self.up_regulation_lim_pu: pd.DataFrame
        self.down_regulation_lim_pu: pd.DataFrame
        self.marginal_cost_up: pd.DataFrame
        self.marginal_cost_down: pd.DataFrame

    def add_up_down_reg(self) -> pypsa.Network:
        """
        Fix generation (p_set) in new_net to the output of old_net in old_net.generators_t.p (must not be empty).
        Generation limits in old_net.generators_t.p_min_pu and old_net.generators_t.p_max_pu (or non time-dependent) are retained,
        but old_net.generators_t.p_set is not taken into account!

        Add new generators to new_net that up/downregulate
        the actual generators. Scale marginal cost of up- and downregulation by mc_fact_up and mc_fact_dn respectively.
        Based on redispatch model at https://pypsa.readthedocs.io/en/latest/examples/scigrid-redispatch.html
        The main differences are the (possibly) time-dependent marginal cost, and possibility of generators to have sign=-1 (flexible loads)
        """
        self._check_generator_compatibility()
        self._fix_generation()

        self._make_up_down_regulators()
        self._calc_time_dependent_params()

        self._add_to_network()

        self.net.generators_t.p = pd.DataFrame(
            index=self.net.snapshots
        )  # reset production

        return self.net

    def _check_generator_compatibility(self) -> None:
        assert (self.net.generators.index.values == self.gens_p_old.columns).all(), (
            "Generators in net must be the same as those in old_net"
        )

    def _fix_generation(self):
        self.net.generators_t.p_set.loc[:, self.gens_p_old.columns] = (
            self.gens_p_old.values
        )

    def _make_up_down_regulators(self):
        self.net.generators.loc[:, 'main_generator'] = self.net.generators.index
        self.up_regulators = self.net.generators.loc[self.flex_gens_up].copy()
        self.down_regulators = self.net.generators.loc[self.flex_gens_down].copy()

        self.up_regulators.index = (
            self.up_regulators.index
            + self.stage_identifier_str
            + self.up_identifier_str
        )
        self.down_regulators.index = (
            self.down_regulators.index
            + self.stage_identifier_str
            + self.down_identifier_str
        )

        return

    def _calc_time_dependent_params(self) -> None:
        """
        Calculate time-dependent values for:
        Up- and downregulation, marginal_cost of up- and downregulation and up- and downregulation limits.
        Ensure the right axis is targeted even when we have only one snapshot, by turning up/down_regulation_lim_pu into a DataFrame if it was a Series.
        Also prevent optimization stability issues by limiting their values.
        """
        gen_inds_up = self.net.generators.loc[self.flex_gens_up].index.copy()
        gen_inds_down = self.net.generators.loc[self.flex_gens_down].index.copy()
        # Calculate marginal costs for up and down regulation


        if self.alpha_mc is None:
            self.marginal_cost_up = as_dense(self.net, 'Generator', 'marginal_cost').loc[:, gen_inds_up].values
            if self.set_downreg_price_to_marginal_cost:
                self.marginal_cost_down = -as_dense(self.net, 'Generator', 'marginal_cost').loc[:, gen_inds_down].values 
            else:
                self.marginal_cost_down = 0  # no revenue from downregulation
        else:
            self.marginal_cost_up = (
                (1 + self.alpha_mc) * self.da_marginal_cost.loc[:, gen_inds_up].values.T
            ).T
            self.marginal_cost_down = -(
                (1 - self.alpha_mc) * self.da_marginal_cost.loc[:, gen_inds_down].values.T
            ).T

        # Calculate up and down regulation limits

        self.up_regulation_lim_pu = (
            as_dense(self.net, "Generator", "p_max_pu").loc[:, self.flex_gens_up]
            - self.gens_p_old.loc[:, self.flex_gens_up]
            / self.net.generators.p_nom.loc[self.flex_gens_up]
        ).fillna(0)  # fill with zero in case of p_nom=0
        self.down_regulation_lim_pu = (
            self.gens_p_old.loc[:, self.flex_gens_down]
            / self.net.generators.p_nom.loc[self.flex_gens_down]
            - as_dense(self.net, "Generator", "p_min_pu").loc[:, self.flex_gens_down]
        ).fillna(0) # fill with zero in case of p_nom=0
        # ensure the right axis is targeted even when we have only one snapshot
        if isinstance(self.up_regulation_lim_pu, pd.Series):
            self.up_regulation_lim_pu = pd.DataFrame(self.up_regulation_lim_pu)
            self.down_regulation_lim_pu = pd.DataFrame(self.down_regulation_lim_pu)

        self.up_regulation_lim_pu[
            self.up_regulation_lim_pu < SMALL_NUMBER_OPTIMIZATION
        ] = 0
        self.down_regulation_lim_pu[
            self.down_regulation_lim_pu < SMALL_NUMBER_OPTIMIZATION
        ] = 0

    def _add_to_network(self) -> None:
        gens_bus_up = self.net.generators.loc[
            self.up_regulators.index.str.replace(
                f"{self.stage_identifier_str}{self.up_identifier_str}", ""
            )
        ].bus
        gens_bus_down = self.net.generators.loc[
            self.down_regulators.index.str.replace(
                f"{self.stage_identifier_str}{self.down_identifier_str}", ""
            )
        ].bus

        self.net.add(
            "Generator",
            self.up_regulators.index,
            p_nom=self.up_regulators.p_nom.values,
            bus=gens_bus_up.values,
            p_min_pu=0,
            sign=self.up_regulators.sign.values,
            p_max_pu=self.up_regulation_lim_pu.values,
            marginal_cost=self.marginal_cost_up,
            carrier=self.up_regulators.carrier.values,
        )
        self.net.add(
            "Generator",
            self.down_regulators.index,
            p_nom=self.down_regulators.p_nom.values,
            bus=gens_bus_down.values,
            p_min_pu=0,
            sign=-self.down_regulators.sign.values,
            p_max_pu=self.down_regulation_lim_pu.values,
            marginal_cost=self.marginal_cost_down,
            carrier=self.down_regulators.carrier.values,
        )

    @staticmethod
    def reindex_generators(net: pypsa.Network, stage_identifier_str: str) -> None:
        """
        Reindex generators, removing up- and downregulators. Add their generation to their original generators.
        Takes into account the sign of up- and downregulators, and the sign of the original generators.
        """
        original_indices = net.generators_t.p.columns.str.split(
            stage_identifier_str
        ).str[0]
        gens_p = (
            (net.generators_t.p * net.generators.sign)
            .T.groupby(original_indices)
            .sum()
            .T
        )
        net.remove(
            "Generator",
            net.generators.index[
                net.generators.index.str.contains(stage_identifier_str)
            ],
        )
        net.generators_t.p = net.generators.sign * gens_p.reindex(
            net.generators.index, axis=1
        )
        net.generators_t.p_set = pd.DataFrame(index=net.snapshots)
        # net.generators_t.p_max_pu = net.generators_t.p_max_pu.reindex(net.generators.index, axis=1)
        # net.generators_t.p_min_pu = net.generators_t.p_min_pu.reindex(net.generators.index, axis=1)
        # net.generators_t.marginal_cost = net.generators_t.marginal_cost.reindex(net.generators.index, axis=1)
