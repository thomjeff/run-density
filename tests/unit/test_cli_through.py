"""CLI staged analyze (#860)."""

import pytest

from app.cli import build_parser, main


def test_analyze_parser_through_choices():
    parser = build_parser()
    args = parser.parse_args(["analyze", "--run-id", "abc", "--through", "trajectory"])
    assert args.run_id == "abc"
    assert args.through == "trajectory"


def test_cli_missing_analysis_json(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
    with pytest.raises(SystemExit, match="analysis.json not found"):
        main(["analyze", "--run-id", "missing", "--through", "trajectory"])
