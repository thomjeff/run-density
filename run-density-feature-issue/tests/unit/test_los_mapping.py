import unittest
from samples.patches.density_template_engine_patch import map_los, Schema

class TestLOSMapping(unittest.TestCase):
    def test_start_corral_mapping(self):
        thresholds = {
            "A": {"max": 0.40},
            "B": {"min": 0.40, "max": 0.70},
            "C": {"min": 0.70, "max": 0.95},
            "D": {"min": 0.95, "max": 1.20},
            "E": {"min": 1.20, "max": 1.60},
            "F": {"min": 1.60},
        }
        self.assertEqual(map_los(1.01, thresholds), "D")
        self.assertEqual(map_los(1.25, thresholds), "E")
