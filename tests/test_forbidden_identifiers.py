import pathlib

FORBID = ["paceCsv", "flow.csv", "density.csv", "segments_old.csv"]  # runtime use only
ALLOW_IN = ["archive/"]  # allow occurrences inside archive

def test_forbidden_identifiers_absent():
    root = pathlib.Path(__file__).resolve().parents[1]
    offenders = []
    for p in root.rglob("*.*"):
        # skip common binaries
        if p.suffix.lower() in {".png",".jpg",".jpeg",".gif",".pdf",".zip",".gz",".pptx",".xlsx",".xls"}:
            continue
        # allow in archive
        rel = p.relative_to(root).as_posix()
        if any(rel.startswith(a) for a in ALLOW_IN):
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for s in FORBID:
            if s in txt:
                offenders.append((rel, s))
    assert not offenders, f"Forbidden identifiers found (outside archive): {offenders}"
