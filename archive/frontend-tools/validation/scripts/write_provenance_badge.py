from jinja2 import Template
import json
from pathlib import Path

def write_badge(meta_path: str, out_path: str):
    meta = json.loads(Path(meta_path).read_text())
    tpl = Template(Path("frontend/validation/templates/_provenance.html").read_text())
    html = tpl.render(meta=meta)
    Path(out_path).write_text(html)

if __name__ == "__main__":
    write_badge("data/meta.json", "frontend/validation/output/provenance_snippet.html")
