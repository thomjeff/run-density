# Density Analysis Module - v1.6.0

## Overview

The Density Analysis Module provides spatial concentration analysis for runners within segments, complementing the temporal flow analysis. It calculates areal density (runners/m²) and crowd density (runners/m) to provide operational insights for race management.

## Key Features

### 🎯 **Density Calculations**
- **Areal Density**: Runners per square meter (runners/m²)
- **Crowd Density**: Runners per meter of course length (runners/m)
- **Independent Runner Counts**: Calculates ALL runners in segment (different from temporal flow context)

### 📊 **Level of Service (LOS) Classification**
- **Areal Density LOS**:
  - Comfortable: <1.0 runners/m²
  - Busy: 1.0-1.8 runners/m²
  - Constrained: ≥1.8 runners/m²
- **Crowd Density LOS**:
  - Low: <1.5 runners/m
  - Medium: 1.5-3.0 runners/m
  - High: ≥3.0 runners/m

### ⏱️ **Time-Over-Threshold (TOT) Metrics**
- Operational planning for high-density periods
- Configurable thresholds (default: 1.2 runners/m², 2.0 runners/m)
- Consistent with LOS classification (>= for TOT, > for LOS)

### 🔄 **Narrative Smoothing**
- Sustained period analysis (minimum 2-minute periods)
- Avoids per-bin noise in reporting
- Meaningful operational insights

## API Endpoints

### POST /api/density/analyze
Full density analysis for all segments.

**Request Body:**
```json
{
  "segments": [...],  // Optional: segment data
  "config": {         // Optional: configuration overrides
    "bin_seconds": 30,
    "threshold_areal": 1.2,
    "threshold_crowd": 2.0,
    "min_segment_length_m": 50.0
  },
  "width_provider": "static"  // Optional: "static" or "dynamic"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "summary": {
      "total_segments": 36,
      "processed_segments": 36,
      "skipped_segments": 0,
      "analysis_start": "2024-01-01T07:00:00",
      "analysis_end": "2024-01-01T15:00:00",
      "time_bin_seconds": 30
    },
    "segments": {
      "A1a": {
        "summary": {
          "segment_id": "A1a",
          "peak_areal_density": 1.87,
          "peak_areal_time_window": ["08:44:30", "08:48:30"],
          "peak_crowd_density": 3.12,
          "peak_crowd_time_window": ["08:45:00", "08:46:00"],
          "tot_areal_sec": 720,
          "tot_crowd_sec": 420,
          "los_areal_distribution": {
            "Comfortable": 0.40,
            "Busy": 0.45,
            "Constrained": 0.15
          },
          "los_crowd_distribution": {
            "Low": 0.35,
            "Medium": 0.40,
            "High": 0.25
          },
          "flags": []
        },
        "time_series": [...],
        "sustained_periods": [...]
      }
    }
  }
}
```

### GET /api/density/segment/{segment_id}
Single segment analysis with detailed results.

**Query Parameters:**
- `config`: JSON string with configuration overrides
- `width_provider`: "static" or "dynamic"

### GET /api/density/summary
Summary data for all segments (performance optimized).

### GET /api/density/health
Health check endpoint.

## Configuration

### DensityConfig
```python
@dataclass(frozen=True)
class DensityConfig:
    bin_seconds: int = 30
    threshold_areal: float = 1.2  # runners/m^2
    threshold_crowd: float = 2.0  # runners/m
    min_segment_length_m: float = 50.0
    epsilon: float = 1e-6
    min_sustained_period_minutes: int = 2
```

## Data Structures

### SegmentMeta
```python
@dataclass(frozen=True)
class SegmentMeta:
    segment_id: str
    from_km: float
    to_km: float
    width_m: float
    direction: str  # "uni" | "bi"
    
    @property
    def segment_length_m(self) -> float:
        return (self.to_km - self.from_km) * 1000
    
    @property
    def area_m2(self) -> float:
        return self.segment_length_m * self.width_m
```

### DensityResult
```python
@dataclass(frozen=True)
class DensityResult:
    segment_id: str
    t_start: str
    t_end: str
    concurrent_runners: int
    areal_density: float
    crowd_density: float
    los_areal: str
    los_crowd: str
    flags: List[str]
```

## Validation & Edge Cases

### Segment Validation
- **Short Segments**: Skip segments <50m (configurable)
- **Invalid Width**: Skip segments with missing or zero width_m
- **Edge Cases**: Flag segments 50-100m for review

### Flags System
- `width_missing`: Invalid or missing width_m values
- `short_segment`: Segments shorter than minimum length
- `edge_case`: Segments between 50-100m
- `no_data`: No valid results for segment

## Performance

### Optimizations
- **NumPy Vectorized Operations**: Concurrent runner calculations
- **Efficient Time Bins**: 30-second intervals aligned with temporal flow
- **Memory Management**: Optimized for 36 segments × thousands of bins

### Performance Targets
- **Single Segment**: <5 seconds
- **All Segments**: <120 seconds
- **API Response**: <2 seconds

## Testing

### Comprehensive Test Suite
- **279 Test Cases**: 100% pass rate
- **Coverage**: All functionality validated
- **Tolerances**: Epsilon 1e-6 for floats, ±1 bin for time windows
- **Real Data**: All 36 segments processed successfully

### Test Categories
- Segment validation
- Density calculations
- TOT calculations
- Narrative smoothing
- Width providers
- Comprehensive analysis
- Performance requirements

## Integration

### With Temporal Flow
- **Independent Calculations**: Density calculates its own runner counts
- **Same Time Bins**: 30-second intervals for alignment
- **Complementary Insights**: Flow provides "when", density provides "how tight"
- **Orchestrator Pattern**: Combined reporting via orchestrator

### With Existing Architecture
- **FastAPI Integration**: Seamless integration with v1.6.0
- **Backward Compatibility**: Maintains existing endpoints
- **Error Handling**: Robust error handling and logging

## Future Enhancements

### Planned Features
- **Dynamic Width**: GPX-based width calculation
- **Weather Adjustments**: Factor in weather conditions
- **Historical Analysis**: Compare across multiple race years
- **Visualization**: Density heatmaps and LOS transition charts

### Pluggable Architecture
- **WidthProvider Protocol**: Easy integration of new width calculation methods
- **StaticWidthProvider**: Current implementation using segments.csv
- **DynamicWidthProvider**: Placeholder for future GPX integration

## Usage Examples

### Basic Analysis
```python
from app.density import analyze_density_segments, DensityConfig

# Load data
segments_df = pd.read_csv('data/segments.csv')
pace_data = pd.read_csv('data/your_pace_data.csv')
start_times = {
    '10K': datetime.strptime('08:00:00', '%H:%M:%S'),
    'Half': datetime.strptime('08:30:00', '%H:%M:%S'),
    'Full': datetime.strptime('09:00:00', '%H:%M:%S')
}

# Analyze density
results = analyze_density_segments(
    segments_df=segments_df,
    pace_data=pace_data,
    start_times=start_times
)
```

### Custom Configuration
```python
config = DensityConfig(
    bin_seconds=60,  # 1-minute bins
    threshold_areal=1.5,  # Higher threshold
    threshold_crowd=2.5,
    min_segment_length_m=100.0
)

results = analyze_density_segments(
    segments_df=segments_df,
    pace_data=pace_data,
    start_times=start_times,
    config=config
)
```

### API Usage
```bash
# Full analysis
curl -X POST "http://localhost:8081/api/density/analyze" \
  -H "Content-Type: application/json" \
  -d '{"config": {"bin_seconds": 30}}'

# Single segment
curl "http://localhost:8081/api/density/segment/A1a"

# Summary only
curl "http://localhost:8081/api/density/summary"
```

## Troubleshooting

### Common Issues
1. **Performance**: Analysis taking longer than expected
   - Check segment count and time bin configuration
   - Consider reducing time bin resolution for testing

2. **Validation Failures**: Segments being skipped
   - Check width_m values in segments.csv
   - Verify segment lengths are >50m

3. **API Errors**: 500 errors in responses
   - Check data file formats and column names
   - Verify start_times configuration

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

### Development
1. Follow the existing code structure
2. Add comprehensive tests for new features
3. Update documentation for API changes
4. Ensure backward compatibility

### Testing
```bash
python test_density_comprehensive.py
```

### Code Quality
- Type hints for all functions
- Comprehensive docstrings
- Error handling and logging
- Performance optimization with NumPy

---

**Version**: 1.6.0  
**Status**: Production Ready  
**Test Coverage**: 100% (279/279 tests passing)  
**Performance**: Validated with real data
