# Overlaps CSV Specification

This document describes the schema and validation rules for `overlaps_v2.csv`, 
which enumerates course overlap segments between events (Full, Half, 10K).

---

## Required Columns

Each row must include the following fields:

| Column        | Description |
|---------------|-------------|
| seg_id        | Unique segment identifier (A1, B2, …). |
| segment_label | Human-readable label (e.g., `Start → Friel`). |
| eventA        | First event in overlap (e.g., `10K`). |
| eventB        | Second event in overlap (e.g., `Half` or `Full`). May equal `eventA` for continuity rows. |
| from_km_A     | Start distance (km) for Event A. |
| to_km_A       | End distance (km) for Event A. |
| from_km_B     | Start distance (km) for Event B. |
| to_km_B       | End distance (km) for Event B. |
| direction     | `uni` if same direction, `bi` if opposing flows. |
| width_m       | Effective width of the path in meters (bi = full width, engine applies /2 each way). |

---

## Continuity Rows

Continuity rows are included when `eventA == eventB`.  
They are used to ensure there are **no distance gaps** for a given event across consecutive segments.

Example:  
If Full covers `2.74–4.25 km` without overlap, add:

```
B3,Friel → 10K Turn (Full only),Full,Full,2.74,4.25,2.74,4.25,uni,3.0,continuity row
```

---

## Example CSV Block

```csv
seg_id,segment_label,eventA,eventB,from_km_A,to_km_A,from_km_B,to_km_B,direction,width_m,notes
A1,Start → Friel,10K,Half,0.00,2.70,0.00,2.70,uni,3.0,Shared opening
A2,Start → Friel,10K,Full,0.00,2.70,0.00,2.70,uni,3.0,Shared opening
A3,Start → Friel,Half,Full,0.00,2.70,0.00,2.70,uni,3.0,Shared opening
B1,Friel → 10K Turn,10K,Full,2.70,4.25,2.70,4.25,uni,3.0,Same-direction outbound
B2,Friel → 10K Turn (bi),10K,10K,2.70,4.25,2.70,4.25,bi,1.5,10K outbound meets 10K returning
B3,Friel → 10K Turn (Full only),Full,Full,2.70,4.25,2.70,4.25,uni,3.0,Continuity row
```

---

## Validator Script

Place this in `scripts/validate_overlaps.py`.

```python
#!/usr/bin/env python3
import sys, csv

REQUIRED = [
    "seg_id","segment_label",
    "eventA","eventB",
    "from_km_A","to_km_A",
    "from_km_B","to_km_B",
    "direction","width_m",
]

def main():
    if len(sys.argv) != 2:
        print("Usage: validate_overlaps.py overlaps_v2.csv")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames

        missing = [c for c in REQUIRED if c not in headers]
        if missing:
            print("❌ Validation FAILED\n")
            print(f"Missing required columns: {', '.join(missing)}")
            sys.exit(1)

        rows = list(reader)
        if not rows:
            print("❌ Validation FAILED: No rows found")
            sys.exit(1)

        print("✅ Validation PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## Usage

```bash
chmod +x scripts/validate_overlaps.py
python3 scripts/validate_overlaps.py data/overlaps_v2.csv
echo $?   # exit code (0=pass, 1=fail)
```

---

## CI Integration

Add this to your `Makefile`:

```makefile
validate-overlaps:
	python3 scripts/validate_overlaps.py data/overlaps_v2.csv
```

Add a GitHub Actions job step:

```yaml
- name: Validate overlaps.csv
  run: make validate-overlaps
```

---

## Notes

- Always include continuity rows to avoid logical gaps.  
- Width is applied as full path width. For `bi`, the engine divides by 2 internally.  
- Human-readable labels should match your course maps (`Start → Friel`, `Friel → 10K Turn`, etc.).
