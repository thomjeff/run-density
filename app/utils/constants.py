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
TEST_SERVER_URL = "http://localhost:8080"

# Fraction validation and clamping
MIN_NORMALIZED_FRACTION = 0.0
MAX_NORMALIZED_FRACTION = 1.0
FRACTION_CLAMP_REASON_OUTSIDE_RANGE = "outside_A_range_normalized"
FRACTION_CLAMP_REASON_NEGATIVE = "negative_fraction_clamped"
FRACTION_CLAMP_REASON_EXCEEDS_ONE = "fraction_exceeds_one_clamped"

# Convergence point analysis
CONVERGENCE_POINT_TOLERANCE_KM = 0.1  # 100m tolerance around convergence points
DISTANCE_BIN_SIZE_KM = 0.1  # 100m distance bins

# Day short codes for v2 (Issue #495)
DAY_SHORT_CODES = ['fri', 'sat', 'sun', 'mon']

# Mapping event names to day of the week (DEPRECATED - will be removed in Phase 10)
# v2 uses Event.day property instead of these constants
EVENT_DAYS = {
    "Elite": "Saturday",
    "Open": "Saturday",
    "Full": "Sunday",
    "Half": "Sunday",
    "10K": "Sunday",
}

# Event groups by day (DEPRECATED - will be removed in Phase 10)
# v2 uses Event filtering instead of these constants
SATURDAY_EVENTS = {"Elite", "Open"}
SUNDAY_EVENTS = {"Full", "Half", "10K"}
ALL_EVENTS = SATURDAY_EVENTS | SUNDAY_EVENTS

# Map configuration
DEFAULT_PACE_CSV = "data/runners.csv"
DEFAULT_SEGMENTS_CSV = "data/segments.csv"
# DEFAULT_START_TIMES removed (Issue #512) - Start times must come from API request, not constants

# Bin dataset configuration (Issue #198) - ChatGPT PR1 fixes
DEFAULT_BIN_SIZE_KM = 0.1  # 100m bins per ChatGPT recommendation
FALLBACK_BIN_SIZE_KM = 0.2  # Fallback for performance issues
MAX_BIN_DATASET_SIZE_MB = 15  # File size limit per ChatGPT
BIN_MAX_FEATURES = 10000  # Feature count limit per ChatGPT
BIN_MAX_GEOJSON_MB_GZ = 15  # Compressed GeoJSON size limit
DEFAULT_BIN_TIME_WINDOW_SECONDS = 60  # 1-minute analysis windows per ChatGPT
MAX_BIN_GENERATION_TIME_SECONDS = 120  # P95 target per ChatGPT performance plan (relaxed for initial deployment)
BIN_HARD_LIMIT_SECONDS = 180  # Absolute ceiling before failover per ChatGPT
BIN_SCHEMA_VERSION = "1.0.0"  # Schema version for validation (updated per ChatGPT)

# Hotspot preservation for bin dataset generation (ChatGPT final optimizations)
HOTSPOT_SEGMENTS = {
    "F1",   # Bridge approaches - critical for reopening decisions
    "H1",   # Trail/Aberdeen critical counterflow area
    "J1", "J4", "J5",  # Bridge/Mill complex - high traffic convergence
    "K1",   # Bridge/Mill to Station - major throughput area
    "L1"    # Trail/Aberdeen counterflow - operational decisions
}

# Map center coordinates (Fredericton, NB)
MAP_CENTER_LAT = 45.9620
MAP_CENTER_LON = -66.6500
MAP_DEFAULT_ZOOM = 14

# Map tile provider
MAP_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
MAP_TILE_ATTRIBUTION = "&copy; OpenStreetMap contributors"
MAP_MAX_ZOOM = 20

# Default segment properties
DEFAULT_SEGMENT_WIDTH_M = 5.0
DEFAULT_FLOW_TYPE = "none"
DEFAULT_ZONE = "green"

# Map density thresholds for zone determination (frontend)
MAP_DENSITY_THRESHOLDS = {
    "green": 0.36,
    "yellow": 0.54,
    "orange": 0.72,
    "red": 1.08
}

# Map zone colors
MAP_ZONE_COLORS = {
    "green": "#4CAF50",
    "yellow": "#FFC107",
    "orange": "#FF9800",
    "red": "#F44336",
    "dark-red": "#B71C1C"
}

# Storage Configuration (Issue #452)
# GCS bucket names (configurable via environment variables)
GCS_BUCKET_RUNFLOW = "runflow"  # New UUID-based structure

# Storage root directories
RUNFLOW_ROOT_LOCAL = "/Users/jthompson/Documents/runflow"  # Must match docker-compose.yml volume mount
RUNFLOW_ROOT_CONTAINER = "/app/runflow"

# Run metadata
RUN_ID_MIN_LENGTH = 10

# Location Report Configuration (Issue #277)
LOCATION_SNAP_THRESHOLD_M = 50.0  # Maximum distance for snapping location to segment
LOCATION_SETUP_BUFFER_MINUTES = 45  # Minutes before earliest runner start for loc_start
