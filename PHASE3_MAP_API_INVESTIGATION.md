# Phase 3: app/api/map.py Investigation Results

**Issue:** #544  
**Date:** December 19, 2025  
**Status:** ✅ Investigation Complete

---

## Summary

**File:** `app/api/map.py` (12.9% coverage, 1,029 lines)

**Finding:** Multiple unused endpoints that are not called by frontend or E2E tests.

---

## Endpoints Analysis

### ✅ Used Endpoints (KEEP)
None found - Frontend uses `/api/segments/geojson` from `app/routes/api_segments.py` instead.

### ❌ Unused Endpoints (CANDIDATES FOR REMOVAL)

#### 1. Cache Management Endpoints (6 endpoints, ~280 lines)
These are admin/debug endpoints not used by frontend or E2E tests:

- **`POST /api/clear-cache`** (lines 744-763, ~20 lines)
  - Calls `clear_bin_cache()` from `app.bin_analysis`
  - Not used by frontend
  - Not used by E2E tests

- **`GET /api/cache-management`** (lines 770-800, ~31 lines)
  - Returns cache statistics
  - Not used by frontend
  - Not used by E2E tests

- **`POST /api/invalidate-segment`** (lines 802-844, ~43 lines)
  - Invalidates cache for specific segment
  - Not used by frontend
  - Not used by E2E tests

- **`GET /api/cache-status`** (lines 846-884, ~39 lines)
  - Gets cache status for analysis results
  - Uses `get_global_cache_manager()` from `app.cache_manager`
  - Not used by frontend
  - Not used by E2E tests

- **`GET /api/cached-analysis`** (lines 889-947, ~59 lines)
  - Gets cached analysis results
  - Uses `get_global_cache_manager()` from `app.cache_manager`
  - Not used by frontend
  - Not used by E2E tests

- **`POST /api/cleanup-cache`** (lines 1003-1028, ~26 lines)
  - Cleans up old cache entries
  - Uses `get_global_cache_manager()` from `app.cache_manager`
  - Not used by frontend
  - Not used by E2E tests

#### 2. Broken Endpoint (1 endpoint, ~52 lines)

- **`GET /api/map-data`** (lines 949-1001, ~53 lines)
  - **BROKEN:** Calls `get_storage_service()` which is not defined or imported
  - Will fail at runtime with `NameError`
  - Not used by frontend
  - Not used by E2E tests
  - Comment says "Maps are visualization-only and read from existing reports"

#### 3. Legacy Map Endpoints (8 endpoints, ~650 lines)
These endpoints appear to be legacy v1 API endpoints not used by the current frontend:

- **`GET /api/map/manifest`** (lines 45-149, ~105 lines)
  - Returns map session metadata
  - Not used by frontend (frontend uses `/api/segments/geojson`)

- **`GET /api/map/segments`** (lines 152-369, ~218 lines)
  - Returns segment corridors as GeoJSON
  - Not used by frontend (frontend uses `/api/segments/geojson`)

- **`GET /api/map/bins`** (lines 370-455, ~86 lines)
  - Returns filtered bins for time window and viewport
  - Not used by frontend

- **`GET /api/bins-data`** (lines 456-528, ~73 lines)
  - Returns bin-level data
  - Not used by frontend

- **`POST /api/flow-bins`** (lines 529-622, ~94 lines)
  - Returns flow bin data
  - Not used by frontend

- **`POST /api/export-bins`** (lines 623-678, ~56 lines)
  - Exports bins as CSV/GeoJSON
  - Not used by frontend

- **`GET /api/map-config`** (lines 679-714, ~36 lines)
  - Returns map configuration
  - Not used by frontend

- **`GET /api/map-status`** (lines 715-742, ~28 lines)
  - Returns map system status
  - Not used by frontend

---

## Dependencies Analysis

### Functions Used by Cache Management Endpoints

**From `app.bin_analysis`:**
- `clear_bin_cache()` - Used by `/clear-cache`
- `get_cache_stats()` - Used by `/cache-management`
- `_bin_cache` - Used by `/invalidate-segment`
- `calculate_dataset_hash()` - Used by `/invalidate-segment`, `/cache-status`, `/cached-analysis`

**From `app.cache_manager`:**
- `get_global_cache_manager()` - Used by `/cache-status`, `/cached-analysis`, `/cleanup-cache`
- `CacheManager.get_cache_status()` - Used by `/cache-status`
- `CacheManager.get_analysis()` - Used by `/cached-analysis`
- `CacheManager.cleanup_old_entries()` - Used by `/cleanup-cache`

**Decision:** If cache management endpoints are removed, we should verify if `get_global_cache_manager()` and its methods are used elsewhere. If not, they may also be candidates for removal from `app/cache_manager.py`.

---

## Recommendation

### High Priority: Remove Broken Endpoint
1. **`GET /api/map-data`** - Broken (undefined `get_storage_service()`), not used

### Medium Priority: Remove Unused Cache Management Endpoints
2. **6 cache management endpoints** - Admin/debug endpoints, not used by frontend or E2E tests

### Low Priority: Review Legacy Map Endpoints
3. **8 legacy map endpoints** - May be used by other tools or kept for backward compatibility. Verify before removal.

---

## Estimated Impact

- **Broken endpoint:** ~53 lines
- **Cache management endpoints:** ~280 lines
- **Total if all removed:** ~333 lines (cache endpoints only)
- **Total if legacy endpoints also removed:** ~983 lines (entire file)

---

## Next Steps

1. Remove broken `/api/map-data` endpoint
2. Remove 6 cache management endpoints (if confirmed unused)
3. Verify if `get_global_cache_manager()` methods are used elsewhere
4. Review legacy map endpoints for backward compatibility needs

