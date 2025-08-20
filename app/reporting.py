from typing import Dict, Optional, Tuple

ZONE_THRESHOLDS = [
    (1.0, "green"),
    (2.0, "amber"),
    (3.5, "red"),
    (float("inf"), "dark-red"),
]

def zone_for(areal_density: float) -> str:
    for cutoff, label in ZONE_THRESHOLDS:
        if areal_density < cutoff:
            return label
    return "dark-red"

def hms_from_seconds(sec: int) -> str:
    sec = int(round(sec))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def coerce_clock(value: Optional[str], fallback_seconds: Optional[int]) -> str:
    """
    Prefer a 'HH:MM:SS' string; otherwise format seconds.
    """
    if isinstance(value, str) and len(value.split(":")) == 3:
        return value
    if isinstance(fallback_seconds, (int, float)):
        return hms_from_seconds(int(fallback_seconds))
    return "N/A"

def format_report(
    *,
    eventA: str,
    eventB: str,
    from_km: float,
    to_km: float,
    segment_name: str,          # "A"
    segment_label: str,         # "Start to Friel"
    direction: str,             # "uni" | "bi"
    width_m: float,             # 3.0 or 1.5
    # counts
    runners_A: int,
    runners_B: int,
    # overlap band actually checked (can be narrower than [from_km,to_km])
    overlap_from_km: Optional[float],
    overlap_to_km: Optional[float],
    # first overlap
    first_overlap_clock: Optional[str],   # "07:48:15" if you pass it, else None
    first_overlap_seconds: Optional[float],  # if no clock, we format from seconds
    first_overlap_km: Optional[float],
    first_overlap_bibA: Optional[str] = None,
    first_overlap_bibB: Optional[str] = None,
    # peak
    peak_total: Optional[int] = None,
    peak_A: Optional[int] = None,
    peak_B: Optional[int] = None,
    peak_km: Optional[float] = None,
    peak_areal_density: Optional[float] = None
) -> str:
    # header lines
    lines = []
    lines.append(
        f"Checking {eventA} vs {eventB} from {from_km:.2f}km–{to_km:.2f}km, Segment {segment_name}"
    )
    # (Start times must be injected by caller – see main.py below)
    # We'll just slot placeholders that caller replaces.
    lines.append("{__START_TIMES__}")  # placeholder
    lines.append(f"Runners: {eventA}: {runners_A}, {eventB}: {runners_B}")
    lines.append(
        f"Segment: {segment_label} | Direction: {direction} | Width: {width_m:.1f}m"
    )

    if overlap_from_km is not None and overlap_to_km is not None:
        lines.append(f"Overlap Segment: {overlap_from_km:.2f}km–{overlap_to_km:.2f}km")

    # first overlap
    if first_overlap_km is not None and (first_overlap_clock or first_overlap_seconds is not None):
        clock = first_overlap_clock or hms_from_seconds(int(first_overlap_seconds))
        bibA = first_overlap_bibA or "N/A"
        bibB = first_overlap_bibB or "N/A"
        lines.append(
            f"First overlap: {clock} at {first_overlap_km:.2f}km ({eventA}: {bibA}, {eventB}: {bibB})"
        )

    # peak
    if (
        peak_total is not None
        and peak_A is not None
        and peak_B is not None
        and peak_km is not None
        and peak_areal_density is not None
    ):
        zone = zone_for(peak_areal_density)
        lines.append(
            f"Peak: {peak_total} ({peak_A} from {eventA}, {peak_B} from {eventB}) at {peak_km:.2f}km — {peak_areal_density:.2f} ppl/m² [{zone}]"
        )

    return "\n".join(lines)