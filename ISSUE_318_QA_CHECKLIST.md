# Issue #318 - Bin-Level Details Table QA Checklist

## 🧪 QA Checklist

### Scenario Testing
| Scenario | Expected Behavior | Status |
|----------|------------------|---------|
| **Initial Load** | Table shows bins for A1 only; dropdown shows all 22 segments | ⏳ |
| **Segment Change** | API call loads bins for selected segment; table updates | ⏳ |
| **LOS Filter** | Filters visible bins client-side without reloading data | ⏳ |
| **Clear Filters** | Resets to A1 bins and clears LOS selection | ⏳ |
| **Empty Segment** | Shows "No bins available" message; no crash | ⏳ |
| **Performance** | Page loads within 2s; API payload < 200KB | ⏳ |

### Implementation Details
- ✅ **Dropdown**: Shows all 22 segments from `/api/segments/geojson`
- ✅ **Initial Load**: Loads only A1 bins via `/api/bins?segment_id=A1&limit=50000`
- ✅ **Segment Selection**: Makes new API call to `/api/bins?segment_id={selected}&limit=50000`
- ✅ **LOS Filtering**: Client-side filtering of loaded data
- ✅ **Clear Filters**: Reloads A1 data and resets dropdowns

### Performance Optimization
- **Efficient Loading**: Only loads bins for selected segment (not all 19,440 bins)
- **Smart Caching**: Segment data loaded on-demand
- **Client-side Filtering**: LOS filtering without API calls
- **Responsive UI**: Loading states and error handling

### API Endpoints Used
- `GET /api/segments/geojson` - Load segment names for dropdown
- `GET /api/bins?segment_id=A1&limit=50000` - Initial A1 bins
- `GET /api/bins?segment_id={segment}&limit=50000` - Selected segment bins
- `GET /api/bins?segment_id={segment}&los_class={los}&limit=50000` - Combined filters

### Expected Data
- **Total Segments**: 22 (A1-A3, B1-B3, D1-D2, F1, G1, H1, I1, J1-J5, K1, L1-L2, M1-M2)
- **A1 Bins**: ~900 bins (0.0-0.9 km)
- **L1 Bins**: ~720 bins (18.65-20.3 km)
- **Performance**: < 2s load time, < 200KB payload per segment

---
**Status**: Ready for testing
**Implementation**: Optimized segment-based loading
**Architecture**: Flask/Jinja2 + Vanilla JS (per ADR-001)
