#!/usr/bin/env python3
"""
One-time fix: truncate a course's geometry and segment data at a given vertex index.

Use when the course has an extra "tail" (e.g. out-and-back that should end earlier).
Example: course has 536 points (0..535) but should end at 489 (Half Turn).
  python scripts/truncate_course_at.py /path/to/course.json 489

This rewrites course.json in place. Ensure you have a backup.
"""

import json
import sys
from pathlib import Path


def truncate_course_at(course_path: Path, end_index: int) -> None:
    with open(course_path, "r") as f:
        data = json.load(f)

    coords = data.get("geometry", {}).get("coordinates") or []
    if not coords:
        print("No geometry coordinates found.")
        sys.exit(1)

    n = len(coords)
    if end_index < 0 or end_index >= n:
        print(f"end_index must be in [0, {n - 1}]. Got {end_index}.")
        sys.exit(1)

    new_len = end_index + 1
    data["geometry"]["coordinates"] = coords[:new_len]

    breaks = data.get("segment_breaks") or []
    data["segment_breaks"] = [i for i in breaks if i <= end_index]

    def num_val(k):
        if isinstance(k, int):
            return k
        if isinstance(k, str) and k.isdigit():
            return int(k, 10)
        return None

    for key in ("segment_break_labels", "segment_break_descriptions", "segment_break_ids"):
        obj = data.get(key)
        if not isinstance(obj, dict):
            continue
        to_del = [k for k in obj if num_val(k) is not None and num_val(k) > end_index]
        for k in to_del:
            del obj[k]

    if "turnaround_indices" in data and isinstance(data["turnaround_indices"], list):
        data["turnaround_indices"] = [i for i in data["turnaround_indices"] if i <= end_index]

    segments = data.get("segments") or []
    data["segments"] = [s for s in segments if (s.get("end_index") or 0) <= end_index]

    with open(course_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Truncated to {new_len} coordinates (0..{end_index}). Segments: {len(data['segments'])}.")


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: truncate_course_at.py <course.json> <end_vertex_index>")
        sys.exit(1)
    course_path = Path(sys.argv[1])
    end_index = int(sys.argv[2], 10)
    if not course_path.exists():
        print(f"File not found: {course_path}")
        sys.exit(1)
    truncate_course_at(course_path, end_index)


if __name__ == "__main__":
    main()
