"""
Application Constants

This module contains all application-wide constants to avoid magic numbers
and improve maintainability.
"""

# Time conversion constants
SECONDS_PER_MINUTE = 60.0
SECONDS_PER_HOUR = 3600.0
MINUTES_PER_HOUR = 60

# Default analysis parameters
DEFAULT_STEP_KM = 0.03
DEFAULT_TIME_WINDOW_SECONDS = 300
DEFAULT_MIN_OVERLAP_DURATION = 5.0
DEFAULT_CONFLICT_LENGTH_METERS = 100.0
DEFAULT_CONVERGENCE_STEP_KM = 0.01

# Tolerance values
TEMPORAL_OVERLAP_TOLERANCE_SECONDS = 5.0
TRUE_PASS_DETECTION_TOLERANCE_SECONDS = 2.0  # Reduced tolerance for true pass detection
DENSITY_EPSILON = 1e-6

# Dynamic conflict length thresholds
CONFLICT_LENGTH_SHORT_SEGMENT_M = 100.0  # For segments <= 1.0km
CONFLICT_LENGTH_MEDIUM_SEGMENT_M = 150.0  # For segments 1.0-2.0km  
CONFLICT_LENGTH_LONG_SEGMENT_M = 200.0   # For segments > 2.0km
SEGMENT_LENGTH_MEDIUM_THRESHOLD_KM = 1.0
SEGMENT_LENGTH_LONG_THRESHOLD_KM = 2.0

# Distance conversion
METERS_PER_KM = 1000.0

# Density analysis thresholds
DENSITY_AREAL_COMFORTABLE_THRESHOLD = 1.0
DENSITY_AREAL_BUSY_THRESHOLD = 1.8
DENSITY_CROWD_LOW_THRESHOLD = 1.5
DENSITY_CROWD_MEDIUM_THRESHOLD = 3.0

# Pace analysis thresholds
PACE_SIMILAR_THRESHOLD = 1.0  # minutes per km
PACE_MODERATE_DIFFERENCE_THRESHOLD = 2.0  # minutes per km

# Time formatting
TIME_FORMAT_HOURS = "%02d:%02d:%02d"
TIME_FORMAT_MINUTES = "%02d:%02d"

# Sample sizes for reporting
MAX_SAMPLE_SIZE = 10

# TOT (Time Over Threshold) analysis
DEFAULT_TOT_THRESHOLDS = [10, 20, 50, 100]
DEFAULT_TIME_BIN_SECONDS = 30

# Narrative smoothing
MIN_SUSTAINED_PERIOD_MINUTES = 2.0

# Binning thresholds for flow analysis
TEMPORAL_BINNING_THRESHOLD_MINUTES = 10.0  # Use time bins if overlap > 10 minutes
SPATIAL_BINNING_THRESHOLD_METERS = 100.0   # Use distance bins if conflict zone > 100m
SUSPICIOUS_OVERTAKING_RATE_THRESHOLD = 0.5  # Flag overtaking rates > 50% as suspicious

# E2E Testing URLs
CLOUD_RUN_URL = "https://run-density-ln4r3sfkha-uc.a.run.app"
LOCAL_RUN_URL = "http://localhost:8080"
TEST_SERVER_URL = "http://testserver:8080"

# Fraction validation and clamping
MIN_NORMALIZED_FRACTION = 0.0
MAX_NORMALIZED_FRACTION = 1.0
FRACTION_CLAMP_REASON_OUTSIDE_RANGE = "outside_A_range_normalized"
FRACTION_CLAMP_REASON_NEGATIVE = "negative_fraction_clamped"
FRACTION_CLAMP_REASON_EXCEEDS_ONE = "fraction_exceeds_one_clamped"
