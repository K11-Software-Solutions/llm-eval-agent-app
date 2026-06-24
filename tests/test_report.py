"""Unit tests for scripts/report.py"""

import json
import sys
from pathlib import Path
from io import StringIO

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.report import parse_rows, render_report, fetch_report_from_api


# ── parse_rows ────────────────────────────────────────────────────────────────

def test_parse_rows_basic(sample_report):
    rows = parse_rows(sample_report)
    assert len(rows) == 2
    assert rows[0]["category"] == "bias"
    assert rows[1]["category"] == "robustness"


def test_parse_rows_types(sample_report):
    rows = parse_rows(sample_report)
    for r in rows:
        assert isinstance(r["pass_count"], int)
        assert isinstance(r["fail_count"], int)
        assert isinstance(r["passed"], bool)


def test_parse_rows_pass_flags(sample_report):
    rows = parse_rows(sample_report)
    assert rows[0]["passed"] is True   # bias passes
    assert rows[1]["passed"] is True   # robustness passes


def test_parse_rows_fail_flag():
    data = {
        "category":          {"0": "fairness"},
        "test_type":         {"0": "min_gender_f1_score"},
        "fail_count":        {"0": 3},
        "pass_count":        {"0": 0},
        "pass_rate":         {"0": "0%"},
        "minimum_pass_rate": {"0": "80%"},
        "pass":              {"0": False},
    }
    rows = parse_rows(data)
    assert rows[0]["passed"] is False


# ── render_report ─────────────────────────────────────────────────────────────

def test_render_report_all_pass(capsys, sample_report):
    rows = parse_rows(sample_report)
    result = render_report("260622-test1", "distilbert", rows)
    captured = capsys.readouterr().out
    assert result is True
    assert "PASS" in captured
    assert "260622-test1" in captured
    assert "distilbert" in captured


def test_render_report_with_fail(capsys):
    data = {
        "category":          {"0": "fairness"},
        "test_type":         {"0": "min_gender_f1_score"},
        "fail_count":        {"0": 3},
        "pass_count":        {"0": 0},
        "pass_rate":         {"0": "0%"},
        "minimum_pass_rate": {"0": "80%"},
        "pass":              {"0": False},
    }
    rows = parse_rows(data)
    result = render_report("260622-test2", "distilbert", rows)
    captured = capsys.readouterr().out
    assert result is False
    assert "FAIL" in captured


def test_render_report_shows_all_categories(capsys, sample_report):
    rows = parse_rows(sample_report)
    render_report("260622-test3", "distilbert", rows)
    captured = capsys.readouterr().out
    assert "bias" in captured
    assert "robustness" in captured


# ── report from file ──────────────────────────────────────────────────────────

def test_load_report_from_file(tmp_path, sample_report):
    model_dir = tmp_path / "distilbert"
    model_dir.mkdir()
    report_file = model_dir / "langtest_report.json"
    report_file.write_text(json.dumps(sample_report))

    from scripts.report import load_report_from_file
    run_id, reports = load_report_from_file(str(report_file))
    assert run_id == "local"
    assert len(reports) == 1
    model_name, data = reports[0]
    assert model_name == "distilbert"
    assert "category" in data


def test_load_report_missing_file():
    from scripts.report import load_report_from_file
    with pytest.raises(SystemExit):
        load_report_from_file("nonexistent/path/report.json")
