# Bin Dataset Validation Tools

This directory contains validation tools for the bin dataset generation feature (Issues #198, #217, #222).

## 🛠️ **Available Tools**

### **1. verify_bins.py**
**Purpose**: Validate that bin artifacts are generated correctly  
**Usage**: `python scripts/validation/verify_bins.py --reports-dir ./reports/YYYY-MM-DD`  
**Source**: ChatGPT Local Ground Truth validation package  

### **2. reconcile_bins_simple.py** 
**Purpose**: Compare bin-level vs segment-level density calculations  
**Usage**: `python scripts/validation/reconcile_bins_simple.py --bins ./reports/YYYY-MM-DD/bins.parquet --segments-json ./reports/YYYY-MM-DD/map_data_*.json`  
**Source**: Adapted from ChatGPT reconciliation analysis for Issue #222  

### **3. run_local_bins.sh**
**Purpose**: End-to-end local testing with bin generation  
**Usage**: `bash scripts/validation/run_local_bins.sh`  
**Source**: ChatGPT Local Ground Truth validation package  

## 🎯 **Validation Workflow**

### **Local Testing**:
1. `bash scripts/validation/run_local_bins.sh` - Generate bins locally
2. `python scripts/validation/verify_bins.py --reports-dir ./reports/YYYY-MM-DD` - Verify artifacts
3. `python scripts/validation/reconcile_bins_simple.py --bins ... --segments-json ...` - Check consistency

### **Cloud Run Testing**:
1. `python e2e.py --cloud` - Full E2E with bin generation
2. Download artifacts from GCS
3. Run verification and reconciliation tools

## ⚙️ **Configuration**

**Optimal Cloud Run Config** (validated in Issues #198/#217):
- CPU: 2
- Memory: 3GB
- Timeout: 600s
- Environment: `ENABLE_BIN_DATASET=true`

## 🔍 **Known Issues**

- **Issue #222**: Scale mismatch between bin and segment densities requiring diagnostic analysis
- See GitHub Issues for latest status and resolution progress
