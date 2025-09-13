# 1. Introduction

## 🎯 **Application Overview**

The **run-density** application is a comprehensive race analysis tool designed to analyze runner flow patterns and crowd density in multi-distance running events. It provides detailed insights into how different race distances interact, where bottlenecks occur, and how runners experience the course.

### **Key Features**

- **Flow Analysis**: Temporal analysis of runner interactions and overtaking patterns
- **Density Analysis**: Crowd density calculations and peak identification
- **Flow↔Density Correlation**: Cross-referencing between flow patterns and density concentrations
- **Detailed Reporting**: Comprehensive markdown and CSV reports
- **API Integration**: RESTful API for programmatic access
- **Real-time Analysis**: Live analysis capabilities for race management

### **Use Cases**

- **Race Directors**: Course planning and bottleneck identification
- **Event Managers**: Crowd control and safety planning
- **Race Analysts**: Performance analysis and course optimization
- **Researchers**: Running event data analysis and research

## 🚀 **Getting Started**

### **Prerequisites**

- Python 3.11 or higher
- Required data files (runners.csv, segments.csv)
- Basic understanding of running event terminology

### **Quick Start**

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Prepare Data**:
   - Ensure `data/runners.csv` contains runner pace data
   - Ensure `data/segments.csv` contains course segment definitions

3. **Run Analysis**:
   ```bash
   python3 -m app.end_to_end_testing
   ```

4. **View Results**:
   - Check `reports/` directory for generated reports
   - Review `Flow.md` for temporal flow analysis
   - Review `Density.md` for crowd density analysis

### **First Steps**

1. **Understand the Data**: Review [Data Inputs](02-data-inputs.md) to understand required file formats
2. **Generate Reports**: Follow [Flow Analysis](03-flow-analysis.md) and [Density Analysis](04-density-analysis.md) guides
3. **Interpret Results**: Use the troubleshooting guides to understand your results

## 📊 **Data Requirements**

### **Required Files**

- **`data/runners.csv`**: Runner pace data with event assignments
- **`data/segments.csv`**: Course segment definitions with flow types

### **Data Quality**

- **Completeness**: All required fields must be populated
- **Accuracy**: Pace data should be realistic and consistent
- **Format**: CSV files must follow specified format requirements
- **Validation**: Use built-in validation tools to check data quality

### **Sample Data Structure**

#### **Runners CSV**
```csv
runner_id,event,pace_min_per_km
1,Full,5.5
2,Half,4.8
3,10K,4.2
```

#### **Segments CSV**
```csv
seg_id,from_km,to_km,flow_type,description
A1,0.0,1.0,overtake,Start to Queen/Regent
F1,5.0,8.0,parallel,Friel to Station Rd
```

## 🎯 **Understanding the Analysis**

### **Flow Analysis**
- **Purpose**: Analyzes how runners of different events interact over time
- **Key Metrics**: Overtaking rates, convergence points, conflict zones
- **Output**: Temporal flow reports showing runner interactions

### **Density Analysis**
- **Purpose**: Calculates crowd density at different course locations
- **Key Metrics**: Peak density, sustained periods, event distribution
- **Output**: Density reports showing crowd concentration patterns

### **Correlation Analysis**
- **Purpose**: Links flow patterns with density concentrations
- **Key Insights**: Where flow conflicts align with density peaks
- **Output**: Integrated reports showing flow-density relationships

## 🔧 **System Architecture**

### **Core Components**

- **Flow Engine**: Temporal flow analysis and overtaking calculations
- **Density Engine**: Crowd density analysis and peak identification
- **Correlation Engine**: Flow-density relationship analysis
- **Report Generator**: Markdown and CSV report creation
- **API Server**: RESTful API for external access

### **Data Flow**

1. **Input**: CSV data files loaded and validated
2. **Processing**: Analysis engines process data according to algorithms
3. **Correlation**: Flow and density results are cross-referenced
4. **Output**: Reports generated in multiple formats
5. **API**: Results made available via RESTful endpoints

## 📈 **Performance Considerations**

### **Computational Requirements**

- **Memory**: Minimum 1GB RAM for full analysis
- **CPU**: Multi-core processing recommended for large datasets
- **Storage**: Sufficient space for report generation

### **Optimization Tips**

- **Data Size**: Larger datasets require more processing time
- **Segment Count**: More segments increase analysis complexity
- **Time Windows**: Smaller time windows provide more detail but require more computation

## 🆘 **Getting Help**

### **Documentation**

- **User Guide**: This comprehensive guide covers all aspects
- **API Reference**: Complete endpoint documentation
- **Troubleshooting**: Common issues and solutions

### **Support**

- **GitHub Issues**: Report bugs and request features
- **Documentation**: Check this guide for common questions
- **Community**: Join discussions for advanced topics

---

**Next**: [Data Inputs](02-data-inputs.md) - Understanding required data formats and validation
