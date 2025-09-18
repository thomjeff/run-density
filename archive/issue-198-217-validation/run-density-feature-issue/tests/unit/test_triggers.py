import unittest
from samples.patches.density_template_engine_patch import Schema, should_fire

class TestTriggers(unittest.TestCase):
    def test_density_trigger(self):
        schema = Schema(
            los_thresholds={
                "D": {"min": 0.95, "max": 1.20},
                "E": {"min": 1.20, "max": 1.60},
                "F": {"min": 1.60},
            },
            flow_ref={"warn": 80, "critical": 110},
            debounce_bins=2,
            cooldown_bins=2,
        )
        metrics = {"density": 1.22, "flow": 70}
        trig = {"schema": "start_corral", "density_gte": "E"}
        self.assertTrue(should_fire(trig, metrics, schema))

    def test_flow_trigger(self):
        schema = Schema(
            los_thresholds={"D": {"min": 0.72, "max": 1.08},"E":{"min":1.08,"max":1.63},"F":{"min":1.63}},
            flow_ref={"warn": 60, "critical": 90},
            debounce_bins=2,
            cooldown_bins=2,
        )
        metrics = {"density": 0.9, "flow": 95}
        trig = {"schema": "on_course_narrow", "flow_gte": "critical"}
        self.assertTrue(should_fire(trig, metrics, schema))
