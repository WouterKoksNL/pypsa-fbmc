import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from fbmc.core.parameters.security_constrained import apply_bodf


class TestApplyBodfColumnwiseEquivalence(unittest.TestCase):

	def test_columnwise_and_vectorized_paths_match(self):
		# df has index=branches and columns=snapshots/buses; values are arbitrary but deterministic.
		df = pd.DataFrame(
			{
				"t0": [10.0, -4.0, 7.5, 3.0],
				"t1": [-2.5, 8.0, 1.0, -6.0],
				"t2": [0.0, 5.5, -3.0, 9.0],
			},
			index=pd.Index(["L1", "L2", "L3", "L4"], name="branch"),
		)

		cnec_index = pd.MultiIndex.from_tuples(
			[
				("L1", "L2"),
				("L3", "L1"),
				("L4", "L3"),
				("L2", "L4"),
				("L1", "L3"),
			],
			names=["branch", "outage"],
		)
		bodf = pd.Series([0.2, -0.15, 0.05, -0.3, 0.1], index=cnec_index, name="BODF")

		# Force vectorized path.
		out_vectorized = apply_bodf(df, bodf, matrix_size_limit=None)

		# Force columnwise path.
		out_columnwise = apply_bodf(df, bodf, matrix_size_limit=0)

		assert_frame_equal(out_columnwise, out_vectorized)


if __name__ == "__main__":
		unittest.main()
