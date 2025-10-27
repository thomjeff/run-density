# 7. API Reference

## 🌐 **API Overview**

The run-density application provides a RESTful API for programmatic access to all analysis capabilities. All endpoints return JSON responses and support standard HTTP methods.

### **Base URL**
- **Local Development**: `http://localhost:8080`
- **Cloud Run Production**: `https://run-density-ln4r3sfkha-uc.a.run.app`

### **Authentication**
Currently no authentication required. All endpoints are publicly accessible.

## 📋 **Endpoint Reference**

### **Health & Status Endpoints**

#### **GET /health**
Check application health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-09-12T23:02:00Z",
  "version": "v1.6.24"
}
```

#### **GET /ready**
Check if application is ready to process requests.

**Response:**
```json
{
  "status": "ready",
  "timestamp": "2025-09-12T23:02:00Z"
}
```

### **Analysis Endpoints**

#### **POST /api/density-report**
Generate density analysis report.

**Request Body:**
```json
{
  "paceCsv": "data/runners.csv",
  "segmentsCsv": "data/segments.csv",
  "startTimes": {
    "Full": 420,
    "10K": 440,
    "Half": 460
  },
  "stepKm": 0.1,
  "timeWindow": 120
}
```

**Response:**
```json
{
  "ok": true,
  "engine": "density",
  "timestamp": "2025-09-12T23:02:00Z",
  "summary": {
    "total_segments": 22,
    "events_analyzed": ["Full", "Half", "10K"],
    "analysis_duration": "2.5 minutes"
  },
  "segments": {
    "A1": {
      "summary": {...},
      "time_series": [...],
      "sustained_periods": [...],
      "events_included": ["Full", "Half", "10K"],
      "seg_label": "Start to Queen/Regent",
      "flow_type": "overtake",
      "per_event": {...}
    }
  },
  "report_paths": {
    "markdown_path": "reports/2025-09-12/2025-09-12-2302-Density.md",
    "csv_path": null
  },
  "markdown_content": "# Density Analysis Report\n\n..."
}
```

#### **POST /api/temporal-flow-report**
Generate temporal flow analysis report.

**Request Body:**
```json
{
  "paceCsv": "data/runners.csv",
  "segmentsCsv": "data/segments.csv",
  "startTimes": {
    "Full": 420,
    "10K": 440,
    "Half": 460
  },
  "minOverlapDuration": 10,
  "conflictLengthM": 100
}
```

**Response:**
```json
{
  "ok": true,
  "engine": "temporal_flow",
  "timestamp": "2025-09-12T23:02:00Z",
  "summary": {
    "total_segments": 29,
    "events_analyzed": ["Full", "Half", "10K"],
    "analysis_duration": "3.2 minutes"
  },
  "segments": {
    "A1": {
      "summary": {...},
      "convergence_analysis": {...},
      "overtaking_analysis": {...},
      "flow_type": "overtake",
      "per_event": {...}
    }
  },
  "report_paths": {
    "markdown_path": "reports/2025-09-12/2025-09-12-2302-Flow.md",
    "csv_path": "reports/2025-09-12/2025-09-12-2302-Flow.csv"
  },
  "markdown_content": "# Temporal Flow Analysis Report\n\n...",
  "csv_content": "seg_id,event_a,event_b,flow_type,overtakes_a,overtakes_b,rate_a,rate_b\n..."
}
```

#### **POST /api/temporal-flow**
Generate temporal flow analysis (data only, no reports).

**Request Body:** Same as `/api/temporal-flow-report`

**Response:**
```json
{
  "ok": true,
  "engine": "temporal_flow",
  "timestamp": "2025-09-12T23:02:00Z",
  "summary": {...},
  "segments": {...}
}
```

#### **POST /api/temporal-flow-single**
Generate single segment temporal flow analysis.

**Request Body:**
```json
{
  "paceCsv": "data/runners.csv",
  "segmentsCsv": "data/segments.csv",
  "startTimes": {
    "Full": 420,
    "10K": 440,
    "Half": 460
  },
  "minOverlapDuration": 10,
  "conflictLengthM": 100,
  "segId": "F1",
  "eventA": "Half",
  "eventB": "10K"
}
```

**Response:**
```json
{
  "ok": true,
  "engine": "temporal_flow_single",
  "timestamp": "2025-09-12T23:02:00Z",
  "segment": "F1",
  "event_a": "Half",
  "event_b": "10K",
  "analysis": {
    "summary": {...},
    "convergence_analysis": {...},
    "overtaking_analysis": {...}
  }
}
```

#### **POST /api/flow-density-correlation**
Generate Flow↔Density correlation analysis.

**Request Body:**
```json
{
  "paceCsv": "data/runners.csv",
  "segmentsCsv": "data/segments.csv",
  "startTimes": {
    "Full": 420,
    "10K": 440,
    "Half": 460
  },
  "minOverlapDuration": 10,
  "conflictLengthM": 100,
  "stepKm": 0.1,
  "timeWindow": 120
}
```

**Response:**
```json
{
  "ok": true,
  "engine": "flow_density_correlation",
  "timestamp": "2025-09-12T23:02:00Z",
  "flow_summary": {...},
  "density_summary": {...},
  "correlations": [
    {
      "segment_id": "F1",
      "flow_type": "parallel",
      "density_class": "B",
      "flow_intensity": "High",
      "correlation_type": "critical_correlation",
      "insights": "High flow intensity with moderate density creates optimal passing conditions"
    }
  ],
  "summary_insights": [...],
  "total_correlations": 15,
  "report_paths": {
    "markdown_path": "reports/2025-09-12/2025-09-12-2302-Flow-Density-Correlation.md",
    "csv_path": "reports/2025-09-12/2025-09-12-2302-Flow-Density-Correlation.csv"
  },
  "markdown_content": "# Flow↔Density Correlation Analysis\n\n...",
  "csv_content": "segment_id,flow_type,density_class,flow_intensity,correlation_type\n..."
}
```

## 📝 **Request Models**

### **ReportRequest**
Base request model for all analysis endpoints.

```json
{
  "paceCsv": "string",           // Path to runners CSV file
  "segmentsCsv": "string",       // Path to segments CSV file
  "startTimes": {                // Event start times in minutes
    "Full": 420,                 // 7:00 AM
    "10K": 440,                  // 7:20 AM
    "Half": 460                  // 7:40 AM
  },
  "minOverlapDuration": 10,      // Minimum overlap duration in minutes
  "conflictLengthM": 100         // Conflict zone length in meters
}
```

### **DensityRequest**
Extended request model for density analysis.

```json
{
  "paceCsv": "string",
  "segmentsCsv": "string",
  "startTimes": {...},
  "stepKm": 0.1,                 // Analysis step size in kilometers
  "timeWindow": 120              // Time window in seconds
}
```

### **SingleSegmentRequest**
Request model for single segment analysis.

```json
{
  "paceCsv": "string",
  "segmentsCsv": "string",
  "startTimes": {...},
  "minOverlapDuration": 10,
  "conflictLengthM": 100,
  "segId": "F1",                 // Target segment ID
  "eventA": "Half",              // First event (optional)
  "eventB": "10K"                // Second event (optional)
}
```

## ⚠️ **Error Handling**

### **Common Error Responses**

#### **400 Bad Request**
```json
{
  "detail": "Invalid request parameters"
}
```

#### **404 Not Found**
```json
{
  "detail": "File not found: data/runners.csv"
}
```

#### **500 Internal Server Error**
```json
{
  "detail": "Analysis failed: Invalid data format"
}
```

### **Error Codes**

- **400**: Bad request - Invalid parameters or data format
- **404**: Not found - Missing files or resources
- **422**: Unprocessable entity - Data validation errors
- **500**: Internal server error - Analysis or processing errors

## 🔧 **Usage Examples**

### **cURL Examples**

#### **Health Check**
```bash
curl -X GET "https://run-density-ln4r3sfkha-uc.a.run.app/health"
```

#### **Generate Density Report**
```bash
curl -X POST "https://run-density-ln4r3sfkha-uc.a.run.app/api/density-report" \
  -H "Content-Type: application/json" \
  -d '{
    "paceCsv": "data/runners.csv",
    "segmentsCsv": "data/segments.csv",
    "startTimes": {"Full": 420, "10K": 440, "Half": 460},
    "stepKm": 0.1,
    "timeWindow": 120
  }'
```

#### **Generate Flow Report**
```bash
curl -X POST "https://run-density-ln4r3sfkha-uc.a.run.app/api/temporal-flow-report" \
  -H "Content-Type: application/json" \
  -d '{
    "paceCsv": "data/runners.csv",
    "segmentsCsv": "data/segments.csv",
    "startTimes": {"Full": 420, "10K": 440, "Half": 460},
    "minOverlapDuration": 10,
    "conflictLengthM": 100
  }'
```

### **Python Examples**

#### **Using requests library**
```python
import requests
import json

# Health check
response = requests.get("https://run-density-ln4r3sfkha-uc.a.run.app/health")
print(response.json())

# Generate density report
data = {
    "paceCsv": "data/runners.csv",
    "segmentsCsv": "data/segments.csv",
    "startTimes": {"Full": 420, "10K": 440, "Half": 460},
    "stepKm": 0.1,
    "timeWindow": 120
}

response = requests.post(
    "https://run-density-ln4r3sfkha-uc.a.run.app/api/density-report",
    json=data
)

if response.status_code == 200:
    result = response.json()
    print(f"Analysis completed: {result['summary']}")
else:
    print(f"Error: {response.json()['detail']}")
```

## 📊 **Response Formats**

### **Standard Response Structure**
All successful responses follow this structure:

```json
{
  "ok": true,                    // Success indicator
  "engine": "string",            // Analysis engine used
  "timestamp": "ISO8601",        // Analysis timestamp
  "summary": {...},              // Analysis summary
  "segments": {...},             // Detailed segment data
  "report_paths": {...},         // Generated report file paths
  "markdown_content": "string",  // Report content (when available)
  "csv_content": "string"        // CSV content (when available)
}
```

### **Report Content**
When available, responses include the full report content in `markdown_content` and `csv_content` fields, allowing immediate access to results without additional file operations.

## 🔍 **Flow-Audit API**

### **Endpoint**: `POST /api/flow-audit`

Generate detailed flow analysis for specific segments with comprehensive validation.

#### **Request Body**
```json
{
  "paceCsv": "data/runners.csv",
  "segmentsCsv": "data/segments.csv", 
  "startTimes": {"Full": 420, "10K": 440, "Half": 460},
  "segId": "F1",
  "eventA": "Half",
  "eventB": "10K",
  "minOverlapDuration": 10.0,
  "conflictLengthM": 100.0,
  "outputDir": "reports"
}
```

#### **Parameters**
- **paceCsv**: Path to runner pace data
- **segmentsCsv**: Path to segment configuration
- **startTimes**: Event start times in minutes
- **segId**: Target segment ID (e.g., "F1")
- **eventA**: First event for comparison
- **eventB**: Second event for comparison
- **minOverlapDuration**: Minimum overlap duration (seconds)
- **conflictLengthM**: Conflict zone length (meters)
- **outputDir**: Output directory for reports

#### **Response**
```json
{
  "ok": true,
  "segment_id": "F1",
  "event_a": "Half",
  "event_b": "10K",
  "overtakes_a": 694,
  "overtakes_b": 451,
  "overtake_percentage_a": 76.1,
  "overtake_percentage_b": 73.0,
  "has_convergence": true,
  "convergence_point_km": 6.5,
  "validation_applied": true,
  "discrepancy_detected": true,
  "flow_audit_data": {...},
  "report_paths": {...}
}
```

#### **Special Features**
- **F1 Validation**: Automatic two-step validation for F1 segment
- **Discrepancy Detection**: Warns when validation differs from main calculation
- **Per-Runner Analysis**: Individual runner entry/exit time tracking
- **Detailed Diagnostics**: 33-column comprehensive audit data
- **Conservative Results**: Uses validation results when discrepancies occur

#### **When to Use Flow-Audit**
- **Complex segments** requiring detailed validation
- **Troubleshooting** unexpected flow patterns
- **F1 segment analysis** with automatic validation
- **Deep analysis** of specific event pairs
- **Validation** of standard flow calculations

---

**Next**: [Troubleshooting](08-troubleshooting.md) - Common issues and solutions
