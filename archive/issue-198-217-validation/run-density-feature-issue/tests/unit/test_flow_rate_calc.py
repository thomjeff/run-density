import unittest
from samples.patches.density_template_engine_patch import compute_flow_rate

class TestFlowRate(unittest.TestCase):
    def test_flow_rate_units(self):
        # 240 runners cross a 6m line in 60s => 40 runners/min/m
        self.assertAlmostEqual(compute_flow_rate(240, 6.0, 60), 40.0, places=5)

    def test_bin_seconds_nonzero(self):
        self.assertAlmostEqual(compute_flow_rate(0, 6.0, 0), 0.0, places=5)
