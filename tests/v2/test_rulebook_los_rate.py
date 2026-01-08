"""
Unit tests ensuring LOS classification is density-only.
"""

import unittest

from app import rulebook


class TestRulebookLosRateIndependence(unittest.TestCase):
    """Ensure LOS classification does not change with rate."""

    def test_los_unchanged_when_rate_changes(self):
        """LOS should be derived from density only, not rate."""
        density = 0.6
        schema_key = "on_course_narrow"
        width_m = 3.0

        low_rate = rulebook.evaluate_flags(
            density_pm2=density,
            rate_p_s=0.1,
            width_m=width_m,
            schema_key=schema_key,
            util_percentile=None,
        )
        high_rate = rulebook.evaluate_flags(
            density_pm2=density,
            rate_p_s=30.0,
            width_m=width_m,
            schema_key=schema_key,
            util_percentile=None,
        )

        expected_los = rulebook.classify_los(
            density,
            rulebook.get_thresholds(schema_key).los,
        )

        self.assertEqual(low_rate.los_class, expected_los)
        self.assertEqual(high_rate.los_class, expected_los)
        self.assertEqual(low_rate.los_class, high_rate.los_class)


if __name__ == "__main__":
    unittest.main()
