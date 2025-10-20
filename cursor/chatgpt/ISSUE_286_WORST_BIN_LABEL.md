# Bug #286 — Density "Worst Bin" label includes stray numeric

## Problem Recap

**Actual**: `Worst Bin (Bin M2:0.000–0.200 07:00–07:02 (0.000))`  
**Expected**: `Worst Bin: M2 0.000–0.200 km · 07:00–07:02`

**Root cause**: The label builder is appending an extra numeric (likely density or rate) in parentheses at the end of the string.

---

## Implementation Plan

### Front-end (preferred, source of truth for labeling)

Add a single formatter that:
- Builds the label from distance range + time window only
- Never appends any numeric metric
- Is tolerant to field name variations

#### Canonical inputs (bin record)
- `segment_id`: string (e.g., "M2")
- **Distance range** (use km; prefer in this order):
  - `d_start_km`, `d_end_km`
  - `dist_start_km`, `dist_end_km`
  - ELSE: accept meters and convert:
    - `d_start_m`, `d_end_m` (divide by 1000)
- **Time window** (ISO or HH:MM):
  - `t_start`, `t_end` (ISO 8601 or HH:MM)
  - (Ignore any `density`, `rate`, `los`, etc. for this label)

#### Formatter (TypeScript)

```typescript
// worstBinLabel.ts
type BinLike = Record<string, any>;

function pickNumber(obj: BinLike, keys: string[]): number | null {
  for (const k of keys) {
    const v = obj?.[k];
    if (typeof v === "number" && !Number.isNaN(v)) return v;
    if (typeof v === "string" && v.trim() && !Number.isNaN(Number(v))) return Number(v);
  }
  return null;
}

function pickString(obj: BinLike, keys: string[]): string | null {
  for (const k of keys) {
    const v = obj?.[k];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return null;
}

function hhmmFromISO(s: string): string {
  // Accept "HH:MM" or ISO; fallback to raw string if parsing fails
  if (/^\d{2}:\d{2}$/.test(s)) return s;
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

export function formatWorstBinLabel(bin: BinLike): string {
  const segment = pickString(bin, ["segment_id", "seg_id"]) ?? "—";

  // distance in km (accept km first, else convert meters)
  let dStartKm = pickNumber(bin, ["d_start_km", "dist_start_km"]);
  let dEndKm   = pickNumber(bin, ["d_end_km", "dist_end_km"]);
  if (dStartKm == null && dEndKm == null) {
    const dStartM = pickNumber(bin, ["d_start_m", "dist_start_m", "s0_m"]);
    const dEndM   = pickNumber(bin, ["d_end_m", "dist_end_m", "s1_m"]);
    if (dStartM != null) dStartKm = dStartM / 1000;
    if (dEndM   != null) dEndKm   = dEndM   / 1000;
  }
  const hasDistances = dStartKm != null && dEndKm != null;
  const distLabel = hasDistances
    ? `${dStartKm!.toFixed(3)}–${dEndKm!.toFixed(3)} km`
    : "";

  // time window (prefer ISO; accept HH:MM)
  const tStart = pickString(bin, ["t_start", "t0", "start_t"]);
  const tEnd   = pickString(bin, ["t_end", "t1", "end_t"]);
  const hasTimes = !!(tStart && tEnd);
  const timeLabel = hasTimes
    ? `${hhmmFromISO(tStart!)}–${hhmmFromISO(tEnd!)}`
    : "";

  // Compose: "Worst Bin: M2 0.000–0.200 km · 07:00–07:02"
  const parts = [segment];
  if (distLabel) parts.push(distLabel);
  if (timeLabel) parts.push(timeLabel);

  return `Worst Bin: ${parts.join(" · ")}`;
}
```

**Notes**:
- This function never looks at density, rate, etc., so no stray numerics appear.
- It gracefully handles ISO times or already-formatted HH:MM.
- It tolerates legacy key names for distance and segment id.

#### Usage

Replace any ad-hoc string templates with:

```typescript
const label = formatWorstBinLabel(worstBinRecord);
```

---

### Backend (optional, nice-to-have)

If the UI is reading a preformatted field (e.g., `worst_bin_label`), update the exporter to exclude numeric metrics from that string:
- Only include `segment_id`, distance range in km, and HH:MM–HH:MM window.
- Prefer leaving formatting to the FE (above) to avoid future drift.

---

## Acceptance Criteria (QA will verify)

- ✅ Label renders exactly: `Worst Bin: <SEG> <d0–d1 km> · <t0–t1>`  
  e.g., `Worst Bin: M2 0.000–0.200 km · 07:00–07:02`
- ✅ No trailing numeric in parentheses or elsewhere.
- ✅ Works across segments/bins with:
  - ISO timestamps or HH:MM
  - Distances provided in km or meters (converted)
  - Legacy keys (`seg_id`, `d_start_m`, etc.)
- ✅ If either distance or time is missing, the label gracefully omits that part (e.g., `Worst Bin: M2 0.000–0.200 km`)

---

## Test Plan

### Unit tests (FE)

```typescript
import { formatWorstBinLabel } from './worstBinLabel';

test('formats with km + ISO times', () => {
  const bin = { segment_id: 'M2', d_start_km: 0, d_end_km: 0.2, t_start: '2025-10-20T07:00:00Z', t_end: '2025-10-20T07:02:00Z' };
  expect(formatWorstBinLabel(bin)).toBe('Worst Bin: M2 0.000–0.200 km · 07:00–07:02');
});

test('formats with meters + HH:MM', () => {
  const bin = { seg_id: 'A1', d_start_m: 50, d_end_m: 250, t0: '07:10', t1: '07:12' };
  expect(formatWorstBinLabel(bin)).toBe('Worst Bin: A1 0.050–0.250 km · 07:10–07:12');
});

test('omits missing parts', () => {
  const bin = { segment_id: 'B3', d_start_km: 0.4, d_end_km: 0.6 };
  expect(formatWorstBinLabel(bin)).toBe('Worst Bin: B3 0.400–0.600 km');
});
```

### Manual QA

- Open Density page and confirm all "Worst Bin" chips/titles have no trailing `(0.000)` or similar.
- Confirm formatting holds for a few sample segments (including those with only one of distance/time available).

---

## Pitfalls to Avoid

- ❌ Don't concatenate density or rate onto the label. Those belong in the details panel or table, not the label.
- ❌ Don't mix meters/km in the same label; always convert and render km with `toFixed(3)`.
- ❌ Maintain canonical `segment_id`; if only `seg_id` exists, treat it as an alias.

---

## Files to Modify

### Frontend
- Create: `frontend/src/utils/worstBinLabel.ts` (new formatter utility)
- Update: Component(s) that render "Worst Bin" labels (likely in Density page components)
- Add: Unit tests for the formatter

### Backend (Optional)
- Update: `analytics/export_frontend_artifacts.py` or similar if preformatted labels are being generated

---

## Definition of Done

- ✅ Formatter function created with full field name tolerance
- ✅ All "Worst Bin" labels render without stray numerics
- ✅ Unit tests pass for various input formats
- ✅ Manual QA confirms correct display on Density page
- ✅ No regressions in other label displays

