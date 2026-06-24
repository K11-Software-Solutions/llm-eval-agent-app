"""Unit tests for app/utils.py"""

import csv
import json
from pathlib import Path

import pytest

from app.utils import load_config, load_data, save_report


def test_load_config(sample_config):
    cfg = load_config(str(sample_config))
    assert "models" in cfg
    assert "categories" in cfg
    assert "thresholds" in cfg


def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent/config.yaml")


def test_load_data_jsonl(sample_jsonl):
    rows = load_data(str(sample_jsonl), fmt="jsonl")
    assert len(rows) == 6
    assert all("text" in r and "label" in r for r in rows)


def test_load_data_csv(tmp_path):
    p = tmp_path / "data.csv"
    p.write_text("text,label\nGreat product,1\nTerrible,0\n")
    rows = load_data(str(p), fmt="csv")
    assert len(rows) == 2
    assert rows[0]["text"] == "Great product"


def test_load_data_unsupported_format(sample_jsonl):
    with pytest.raises(ValueError, match="Unsupported data format"):
        load_data(str(sample_jsonl), fmt="parquet")


def test_save_report_json(tmp_path):
    report = {"category": {"0": "bias"}, "pass": {"0": True}}
    path = str(tmp_path / "report.json")
    save_report(report, path, fmt="json")
    loaded = json.loads(Path(path).read_text())
    assert loaded["pass"]["0"] is True


def test_save_report_txt(tmp_path):
    path = str(tmp_path / "report.txt")
    save_report("some report text", path, fmt="txt")
    assert Path(path).read_text() == "some report text"


def test_save_report_unsupported_format(tmp_path):
    with pytest.raises(ValueError, match="Unsupported report format"):
        save_report({}, str(tmp_path / "x.md"), fmt="md")
