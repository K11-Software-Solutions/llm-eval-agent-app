"""
Tests for scripts/generate_charts.py

These tests actually run the chart generation pipeline and verify the output
PNG is a valid, non-trivial image file.
"""

import json
import struct
import zlib
from pathlib import Path

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_audit_log(path: Path, entries: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def _is_valid_png(path: Path) -> bool:
    PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
    with open(path, "rb") as f:
        return f.read(8) == PNG_MAGIC


def _png_dimensions(path: Path) -> tuple[int, int]:
    """Return (width, height) from PNG IHDR chunk."""
    with open(path, "rb") as f:
        f.read(8)              # signature
        f.read(4)              # IHDR length
        f.read(4)              # 'IHDR'
        width  = struct.unpack(">I", f.read(4))[0]
        height = struct.unpack(">I", f.read(4))[0]
    return width, height


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def audit_entries():
    return [
        {
            "timestamp": "2026-05-15T09:00:00+00:00",
            "run_id": "eval_run_demo",
            "repo": "kavitaj11/llm-eval-demo",
            "pr": None, "sha": None,
            "model": "distilbert-base-uncased-finetuned-sst-2-english",
            "overall": "pass",
            "categories": {
                "bias": {"pass_rate": 1.0, "passed": True},
            },
            "confidence": {},
        },
        {
            "timestamp": "2026-06-01T09:00:00+00:00",
            "run_id": "eval_run_research",
            "repo": "kavitaj11/llm-eval-demo",
            "pr": None, "sha": None,
            "model": "distilbert-base-uncased-finetuned-sst-2-english",
            "overall": "fail",
            "categories": {
                "bias":       {"pass_rate": 0.98, "passed": True},
                "fairness":   {"pass_rate": 0.0,  "passed": False},
                "robustness": {"pass_rate": 0.92, "passed": True},
            },
            "confidence": {},
        },
        {
            "timestamp": "2026-06-10T09:00:00+00:00",
            "run_id": "eval_run_multimodel",
            "repo": "kavitaj11/llm-eval-demo",
            "pr": None, "sha": None,
            "model": "textattack_roberta-base-SST-2",
            "overall": "fail",
            "categories": {
                "bias":       {"pass_rate": 0.98, "passed": True},
                "fairness":   {"pass_rate": 0.0,  "passed": False},
                "robustness": {"pass_rate": 0.985, "passed": True},
            },
            "confidence": {},
        },
        {
            "timestamp": "2026-06-23T20:32:33+00:00",
            "run_id": "eval_run_redteam",
            "repo": "local",
            "pr": None, "sha": None,
            "model": "distilbert-base-uncased-finetuned-sst-2-english",
            "overall": "pass",
            "categories": {
                "bias":       {"pass_rate": 0.92, "passed": True},
                "robustness": {"pass_rate": 0.91, "passed": True},
            },
            "confidence": {},
        },
    ]


# ── tests ─────────────────────────────────────────────────────────────────────

class TestLoadAuditEntries:

    def test_returns_empty_list_for_missing_file(self, tmp_path):
        from scripts.generate_charts import load_audit_entries
        result = load_audit_entries(tmp_path / "nonexistent.jsonl")
        assert result == []

    def test_deduplicates_same_run_id_and_date(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        entry = {"timestamp": "2026-06-01T09:00:00+00:00", "run_id": "r1",
                 "overall": "pass", "categories": {}, "confidence": {}}
        _write_audit_log(log, [entry, entry])  # duplicate
        from scripts.generate_charts import load_audit_entries
        result = load_audit_entries(log)
        assert len(result) == 1

    def test_sorted_by_timestamp(self, tmp_path, audit_entries):
        import random
        shuffled = list(audit_entries)
        random.shuffle(shuffled)
        log = tmp_path / "audit.jsonl"
        _write_audit_log(log, shuffled)
        from scripts.generate_charts import load_audit_entries
        result = load_audit_entries(log)
        timestamps = [e["timestamp"] for e in result]
        assert timestamps == sorted(timestamps)

    def test_skips_malformed_lines(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        log.write_text(
            '{"timestamp":"2026-06-01","run_id":"r1","overall":"pass","categories":{},"confidence":{}}\n'
            'NOT JSON\n'
            '{"timestamp":"2026-06-02","run_id":"r2","overall":"fail","categories":{},"confidence":{}}\n',
            encoding="utf-8",
        )
        from scripts.generate_charts import load_audit_entries
        result = load_audit_entries(log)
        assert len(result) == 2


class TestGenerateTrendChart:

    def test_generates_png_file(self, tmp_path, audit_entries):
        log = tmp_path / "audit.jsonl"
        out = tmp_path / "trend_chart.png"
        _write_audit_log(log, audit_entries)
        from scripts.generate_charts import generate_trend_chart
        result = generate_trend_chart(log, out)
        assert result == out
        assert out.exists()

    def test_output_is_valid_png(self, tmp_path, audit_entries):
        log = tmp_path / "audit.jsonl"
        out = tmp_path / "trend_chart.png"
        _write_audit_log(log, audit_entries)
        from scripts.generate_charts import generate_trend_chart
        generate_trend_chart(log, out)
        assert _is_valid_png(out)

    def test_output_is_non_trivial_size(self, tmp_path, audit_entries):
        log = tmp_path / "audit.jsonl"
        out = tmp_path / "trend_chart.png"
        _write_audit_log(log, audit_entries)
        from scripts.generate_charts import generate_trend_chart
        generate_trend_chart(log, out)
        assert out.stat().st_size > 50_000  # at least 50 KB

    def test_output_dimensions_match_figsize(self, tmp_path, audit_entries):
        log = tmp_path / "audit.jsonl"
        out = tmp_path / "trend_chart.png"
        _write_audit_log(log, audit_entries)
        from scripts.generate_charts import generate_trend_chart
        generate_trend_chart(log, out)
        width, height = _png_dimensions(out)
        # figsize=(10,8) at dpi=150 → ~1500x1200px (bbox_inches may add margin)
        assert width  >= 1200
        assert height >= 900

    def test_raises_on_empty_log(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        log.write_text("", encoding="utf-8")
        out = tmp_path / "trend_chart.png"
        from scripts.generate_charts import generate_trend_chart
        with pytest.raises(ValueError, match="No audit log entries"):
            generate_trend_chart(log, out)

    def test_creates_parent_dirs_if_missing(self, tmp_path, audit_entries):
        log = tmp_path / "audit.jsonl"
        out = tmp_path / "nested" / "deep" / "trend_chart.png"
        _write_audit_log(log, audit_entries)
        from scripts.generate_charts import generate_trend_chart
        generate_trend_chart(log, out)
        assert out.exists()

    def test_works_with_bias_only_entries(self, tmp_path):
        entries = [{
            "timestamp": "2026-06-01T09:00:00+00:00",
            "run_id": "r1", "repo": "local",
            "pr": None, "sha": None,
            "model": "distilbert",
            "overall": "pass",
            "categories": {"bias": {"pass_rate": 1.0, "passed": True}},
            "confidence": {},
        }]
        log = tmp_path / "audit.jsonl"
        out = tmp_path / "chart.png"
        _write_audit_log(log, entries)
        from scripts.generate_charts import generate_trend_chart
        generate_trend_chart(log, out)
        assert _is_valid_png(out)

    def test_generates_chart_from_real_audit_log(self):
        """Integration test — generates chart from the actual project audit log."""
        real_log = Path("data/audit_log.jsonl")
        out      = Path("artifacts/eval/trend_chart.png")
        if not real_log.exists():
            pytest.skip("No real audit_log.jsonl present")
        from scripts.generate_charts import generate_trend_chart
        result = generate_trend_chart(real_log, out)
        assert _is_valid_png(result)
        width, height = _png_dimensions(result)
        assert width > 0 and height > 0
        print(f"\nChart generated: {result} ({result.stat().st_size // 1024} KB, {width}x{height}px)")
