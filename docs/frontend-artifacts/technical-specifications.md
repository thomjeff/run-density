# Front-End Technical Specifications

## API Integration Points

### Existing Backend Endpoints
```javascript
// Health Check
GET /health
GET /ready

// Report Generation
POST /api/density-report
POST /api/temporal-flow-report

// Data Analysis
POST /api/density
POST /api/temporal-flow

// Overtake Analysis
POST /api/overtake
POST /api/overlap
```

### Request/Response Examples

#### Temporal Flow Analysis Request
```json
{
  "pace_csv": "data/runners.csv",
  "segments_csv": "data/segments_new.csv",
  "start_times": {
    "10K": 440,
    "Half": 460,
    "Full": 420
  },
  "min_overlap_duration": 5.0,
  "conflict_length_m": 100.0
}
```

#### Temporal Flow Analysis Response
```json
{
  "ok": true,
  "engine": "temporal_flow",
  "timestamp": "2025-09-05T22:13:33",
  "start_times": {"10K": 440, "Half": 460, "Full": 420},
  "min_overlap_duration": 5.0,
  "conflict_length_m": 100.0,
  "total_segments": 29,
  "segments_with_convergence": 15,
  "segments": [
    {
      "seg_id": "A2",
      "segment_label": "Queen/Regent to WSB mid-point",
      "flow_type": "overtake",
      "event_a": "Half",
      "event_b": "10K",
      "from_km_a": 0.9,
      "to_km_a": 1.8,
      "from_km_b": 0.9,
      "to_km_b": 1.8,
      "convergence_point": 1.31,
      "has_convergence": true,
      "total_a": 912,
      "total_b": 618,
      "overtaking_a": 4,
      "overtaking_b": 1,
      "convergence_zone_start": 1.26,
      "convergence_zone_end": 1.36,
      "conflict_length_m": 100.0,
      "sample_a": [1618, 1619, 1620],
      "sample_b": [1529]
    }
  ]
}
```

## Component Architecture

### React Component Structure
```
src/
├── components/
│   ├── AnalysisForm/
│   │   ├── EventConfiguration.tsx
│   │   ├── AnalysisParameters.tsx
│   │   ├── DataSources.tsx
│   │   └── SubmitButton.tsx
│   ├── ResultsDisplay/
│   │   ├── FlowAnalysisTab.tsx
│   │   ├── DensityAnalysisTab.tsx
│   │   ├── MapVisualizationTab.tsx
│   │   └── ResultsTable.tsx
│   ├── DataManagement/
│   │   ├── SegmentsViewer.tsx
│   │   ├── PaceDataViewer.tsx
│   │   ├── FileUpload.tsx
│   │   └── TemplateDownload.tsx
│   ├── Map/
│   │   ├── CourseMap.tsx
│   │   ├── SegmentOverlay.tsx
│   │   ├── DensityHeatmap.tsx
│   │   └── FlowVectors.tsx
│   └── Common/
│       ├── ProgressIndicator.tsx
│       ├── DownloadButton.tsx
│       ├── HelpTooltip.tsx
│       └── ErrorBoundary.tsx
├── hooks/
│   ├── useAnalysis.ts
│   ├── useFileUpload.ts
│   ├── useMapData.ts
│   └── useProgress.ts
├── services/
│   ├── api.ts
│   ├── fileService.ts
│   └── mapService.ts
└── types/
    ├── analysis.ts
    ├── segments.ts
    └── results.ts
```

## State Management

### Redux Store Structure
```typescript
interface AppState {
  analysis: {
    isRunning: boolean;
    progress: number;
    results: AnalysisResults | null;
    error: string | null;
  };
  data: {
    segments: Segment[];
    paceData: Runner[];
    isLoaded: boolean;
  };
  ui: {
    activeTab: 'flow' | 'density' | 'map';
    selectedSegment: string | null;
    mapView: MapViewState;
  };
  user: {
    preferences: UserPreferences;
    recentAnalyses: AnalysisHistory[];
  };
}
```

## File Upload Specifications

### Supported File Formats
- **CSV Files**: Comma-separated values with UTF-8 encoding
- **Maximum File Size**: 50MB per file
- **Required Columns**: As specified in data templates

### Upload Validation
```typescript
interface FileValidation {
  isValid: boolean;
  errors: string[];
  warnings: string[];
  preview: any[];
  columnMapping: Record<string, string>;
}
```

### Template Files
- `segments_template.csv`: Standardized segments file format
- `pace_data_template.csv`: Standardized pace data format
- `validation_rules.json`: File validation specifications

## Map Integration

### Leaflet.js Configuration
```typescript
const mapConfig = {
  center: [45.4215, -75.6972], // Ottawa coordinates
  zoom: 12,
  maxZoom: 18,
  minZoom: 8,
  layers: [
    'OpenStreetMap',
    'Course Overlay',
    'Segment Boundaries',
    'Density Heatmap',
    'Flow Vectors'
  ]
};
```

### Map Data Layers
```typescript
interface MapLayer {
  id: string;
  name: string;
  type: 'overlay' | 'marker' | 'heatmap' | 'vector';
  data: any[];
  style: LayerStyle;
  visible: boolean;
}
```

## Performance Optimization

### Code Splitting
```typescript
const AnalysisForm = lazy(() => import('./components/AnalysisForm'));
const ResultsDisplay = lazy(() => import('./components/ResultsDisplay'));
const MapVisualization = lazy(() => import('./components/Map'));
```

### Data Virtualization
- Virtual scrolling for large datasets
- Lazy loading of map tiles
- Debounced search and filtering
- Memoized expensive calculations

### Caching Strategy
- Service worker for offline capability
- Local storage for user preferences
- Session storage for temporary data
- CDN for static assets

## Security Considerations

### Input Validation
- Client-side validation for immediate feedback
- Server-side validation for security
- File type and size restrictions
- XSS prevention in user inputs

### API Security
- HTTPS for all communications
- Request rate limiting
- CORS configuration
- Input sanitization

## Testing Strategy

### Unit Tests
- Component rendering tests
- Hook functionality tests
- Utility function tests
- API integration tests

### Integration Tests
- End-to-end user workflows
- File upload scenarios
- Map interaction tests
- Download functionality tests

### Performance Tests
- Load time measurements
- Memory usage monitoring
- Large dataset handling
- Map rendering performance

## Deployment Configuration

### Build Configuration
```json
{
  "build": {
    "target": "es2015",
    "minify": true,
    "sourcemap": false,
    "outDir": "dist"
  },
  "serve": {
    "port": 3000,
    "host": "localhost"
  }
}
```

### Environment Variables
```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_MAP_TILE_URL=https://tile.openstreetmap.org
VITE_MAX_FILE_SIZE=52428800
VITE_ENABLE_ANALYTICS=false
```

## Browser Compatibility

### Supported Browsers
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

### Progressive Enhancement
- Basic functionality without JavaScript
- Enhanced features with modern browsers
- Graceful degradation for older browsers
- Mobile-responsive design
