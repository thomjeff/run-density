# Golden Locations.csv fixtures (#860)

Do **not** check in full-package analysis trees (multi-million-row parquet).

## CI

Unit tests in `tests/unit/test_trajectory_layer.py` and `tests/unit/test_pipeline_through.py`
are the default validation path. Shadow-diff helper: `app.core.locations.shadow_diff`.

## Optional operator goldens

After a known-good **full** analysis:

1. Copy `{run}/sun/reports/Locations.csv` (and other days) aside as baseline.
2. Re-run the same `analysis.json`:

   `python -m app.cli analyze --run-id <id> --through locations`

3. Diff with the helper (exact HH:MM:SS by default):

   ```python
   from pathlib import Path
   from app.core.locations.shadow_diff import compare_locations_csv
   diffs = compare_locations_csv(Path("baseline/Locations.csv"), Path("runflow/analysis/<id>/sun/reports/Locations.csv"))
   ```

Suggested packages: George / FM2027. Re-generate baselines only when Locations semantics change.
