# Critical Lines for ChatGPT Review

## 🎯 5 Duplicated Event Logic Patterns in `core_density_compute.py`

### Pattern 1: Lines 371-376
```python
for event in segment.events:
    if event == "Full" and density_cfg.get("full_from_km") is not None:
        intervals.append((density_cfg["full_from_km"], density_cfg["full_to_km"]))
    elif event == "Half" and density_cfg.get("half_from_km") is not None:
        intervals.append((density_cfg["half_from_km"], density_cfg["half_to_km"]))
    elif event == "10K" and density_cfg.get("tenk_from_km") is not None:
        intervals.append((density_cfg["tenk_from_km"], density_cfg["tenk_to_km"]))
```

### Pattern 2: Lines 490-495
```python
for event in segment.events:
    if event == "Full" and density_cfg.get("full_from_km") is not None:
        intervals_km.append((density_cfg["full_from_km"], density_cfg["full_to_km"]))
    elif event == "Half" and density_cfg.get("half_from_km") is not None:
        intervals_km.append((density_cfg["half_from_km"], density_cfg["half_to_km"]))
    elif event == "10K" and density_cfg.get("tenk_from_km") is not None:
        intervals_km.append((density_cfg["tenk_from_km"], density_cfg["tenk_to_km"]))
```

### Pattern 3: Lines 849-857
```python
for event in segment.events:
    if event == "Full" and density_cfg.get("full_from_km") is not None:
        from_km = density_cfg["full_from_km"]
        to_km = density_cfg["full_to_km"]
    elif event == "Half" and density_cfg.get("half_from_km") is not None:
        from_km = density_cfg["half_from_km"]
        to_km = density_cfg["half_to_km"]
    elif event == "10K" and density_cfg.get("tenk_from_km") is not None:
        from_km = density_cfg["tenk_from_km"]
        to_km = density_cfg["tenk_to_km"]
    else:
        continue
```

### Pattern 4: Lines 915-923
```python
for event in segment.events:
    if event == "Full" and density_cfg.get("full_from_km") is not None:
        from_km = density_cfg["full_from_km"]
        to_km = density_cfg["full_to_km"]
        event_ranges.append((from_km, to_km, to_km - from_km, event))
    elif event == "Half" and density_cfg.get("half_from_km") is not None:
        from_km = density_cfg["half_from_km"]
        to_km = density_cfg["half_to_km"]
        event_ranges.append((from_km, to_km, to_km - from_km, event))
    elif event == "10K" and density_cfg.get("tenk_from_km") is not None:
        from_km = density_cfg["tenk_from_km"]
        to_km = density_cfg["tenk_to_km"]
        event_ranges.append((from_km, to_km, to_km - from_km, event))
```

### Pattern 5: Lines 985-991
```python
for event in segment.events:
    if event == "Full" and density_cfg.get("full_from_km") is not None:
        min_km = min(min_km, density_cfg["full_from_km"])
        max_km = max(max_km, density_cfg["full_to_km"])
    elif event == "Half" and density_cfg.get("half_from_km") is not None:
        min_km = min(min_km, density_cfg["half_from_km"])
        max_km = max(max_km, density_cfg["half_to_km"])
    elif event == "10K" and density_cfg.get("tenk_from_km") is not None:
        min_km = min(min_km, density_cfg["tenk_from_km"])
        max_km = max(max_km, density_cfg["tenk_to_km"])
```

## 🔍 Key Observations

1. **Identical Logic**: All 5 patterns use the same if/elif structure for Full/Half/10K events
2. **Different Usage**: Each pattern uses the extracted values differently (append, assign, min/max)
3. **Configuration Keys**: All rely on `density_cfg` with keys `full_from_km`, `half_from_km`, `tenk_from_km`
4. **Null Checks**: All check for `is not None` before using configuration values
5. **Event Types**: Only handles "Full", "Half", "10K" event types

## 💡 Proposed Utility Function

```python
def get_event_intervals(event: str, density_cfg: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """
    Extract event-specific interval from density configuration.
    
    Args:
        event: Event type ("Full", "Half", "10K")
        density_cfg: Density configuration dictionary
        
    Returns:
        Tuple of (from_km, to_km) if event configuration exists, None otherwise
    """
    if event == "Full" and density_cfg.get("full_from_km") is not None:
        return (density_cfg["full_from_km"], density_cfg["full_to_km"])
    elif event == "Half" and density_cfg.get("half_from_km") is not None:
        return (density_cfg["half_from_km"], density_cfg["half_to_km"])
    elif event == "10K" and density_cfg.get("tenk_from_km") is not None:
        return (density_cfg["tenk_from_km"], density_cfg["tenk_to_km"])
    return None
```

## ⚠️ Critical Questions for ChatGPT

1. **Is this utility function design optimal?**
2. **How should we handle the different usage patterns (append vs assign vs min/max)?**
3. **Should we create multiple utility functions or one flexible function?**
4. **How to ensure exact same behavior after refactoring?**
5. **What's the best approach for testing this refactoring?**
