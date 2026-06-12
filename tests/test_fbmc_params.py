import unittest
import pandas as pd
import numpy as np
import pypsa
import fbmc.core.pos_neg_method.main as fbmc_main
import fbmc.core.input_parameters.cnec as cne_params
import fbmc.core.derived_parameters as fbmc_params


class TestGetNetworkPtdf(unittest.TestCase):

    def setUp(self):
        self.basecase_network = pypsa.Network()
        self.basecase_network.set_snapshots(range(2))
        
        # Add three buses in a triangle configuration
        self.basecase_network.add("Bus", "bus1", v_nom=220)
        self.basecase_network.add("Bus", "bus2", v_nom=220)
        self.basecase_network.add("Bus", "bus3", v_nom=220)
        
        # Add lines forming a triangle
        self.basecase_network.add("Line", "line1", 
            bus0="bus1",
            bus1="bus2",
            x=0.2,      # reactance
            r=0.01,     # resistance
            b=0.001,    # susceptance
            s_nom=300   # thermal rating
        )
        self.basecase_network.add("Line", "line2",
            bus0 = "bus1",
            bus1 = "bus3",
            x = 0.2,
            r = 0.01,
            b = 0.001,
            s_nom = 300
        )

        self.basecase_network.add("Line", "line3", 
            bus0="bus2",
            bus1="bus3",
            x=0.2,
            r=0.01,
            b=0.001,
            s_nom=200
        )
        
    def test_get_network_ptdf(self):
        ptdf, _ = fbmc_params.get_network_ptdf(self.basecase_network)
        self.assertEqual(ptdf.columns.tolist(), ['bus1', 'bus2', 'bus3'])
        self.assertEqual(ptdf.index.tolist(), ['line1', 'line2', 'line3'])
        
        # Check that PTDF matrix has expected properties
        self.assertFalse((ptdf == 0).all().all(), "PTDF matrix should not be all zeros")
        
        # Check row sums based on line connectivity to reference bus
        ref_bus = 'bus1'  # The reference bus used in the PTDF calculation
        for line_name in ptdf.index:
            line = self.basecase_network.lines.loc[line_name]
            if line.bus0 == ref_bus or line.bus1 == ref_bus:
                # Lines connected to reference bus should sum to approximately -1
                self.assertTrue(np.isclose(ptdf.loc[line_name].sum(), -1.0), 
                               f"Sum of PTDF row for {line_name} connected to reference bus should be close to -1")
            else:
                # Lines not connected to reference bus should sum to approximately 0
                self.assertTrue(np.isclose(ptdf.loc[line_name].sum(), 0.0), 
                               f"Sum of PTDF row for {line_name} not connected to reference bus should be close to 0")

if __name__ == '__main__':
    unittest.main()