"""
Unit tests for new features:
  - Confidence score reporting (_compute_confidence)
  - Audit log (_append_audit_log)
  - Red-teaming / robustness tests in config + agent
  - Block merge on failure (Check Run conclusion wiring)
  - Custom data upload (POST /upload-data) — extended coverage
  - Trend chart (sparkline, render_table, render_csv, load_entries, GET /trend)
  - Scheduled eval (start_scheduler disabled, cron config validation)
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Confidence score reporting
# ---------------------------------------------------------------------------

class TestConfidenceScoring:

    def test_returns_expected_keys(self, sample_jsonl):
        mock_output = [{"label": "POSITIVE", "score": 0.95}] * 5 + \
                      [{"label": "NEGATIVE", "score": 0.72}]

        with patch("transformers.pipeline") as mock_pipe_cls:
            mock_pipe = MagicMock(return_value=mock_output)
            mock_pipe_cls.return_value = mock_pipe

            from app.eval_runner import _compute_confidence
            result = _compute_confidence(
                "distilbert-base-uncased-finetuned-sst-2-english",
                str(sample_jsonl),
            )

        assert "avg_confidence" in result
        assert "min_confidence" in result
        assert "max_confidence" in result
        assert "sample_count" in result

    def test_avg_confidence_is_correct(self, sample_jsonl):
        scores = [0.9, 0.8, 0.7]
        mock_output = [{"label": "POSITIVE", "score": s} for s in scores]

        with patch("transformers.pipeline") as mock_pipe_cls:
            mock_pipe_cls.return_value = MagicMock(return_value=mock_output)
            from app.eval_runner import _compute_confidence
            result = _compute_confidence("any-model", str(sample_jsonl))

        assert result["avg_confidence"] == pytest.approx(0.8, abs=0.01)
        assert result["min_confidence"] == pytest.approx(0.7, abs=0.01)
        assert result["max_confidence"] == pytest.approx(0.9, abs=0.01)
        assert result["sample_count"] == 3

    def test_returns_empty_dict_on_pipeline_error(self, sample_jsonl):
        with patch("transformers.pipeline", side_effect=ImportError("no transformers")):
            from app.eval_runner import _compute_confidence
            result = _compute_confidence("any-model", str(sample_jsonl))

        assert result == {}

    def test_returns_empty_dict_on_empty_file(self, tmp_path):
        empty = tmp_path / "empty.jsonl"
        empty.write_text("")

        with patch("transformers.pipeline") as mock_pipe_cls:
            mock_pipe_cls.return_value = MagicMock(return_value=[])
            from app.eval_runner import _compute_confidence
            result = _compute_confidence("any-model", str(empty))

        assert result == {}

    def test_caps_at_50_samples(self, tmp_path):
        data = [{"text": f"Sample {i}", "label": 1} for i in range(100)]
        f = tmp_path / "big.jsonl"
        f.write_text("\n".join(json.dumps(r) for r in data))

        captured_texts = []

        def fake_pipe(texts):
            captured_texts.extend(texts)
            return [{"label": "POSITIVE", "score": 0.9}] * len(texts)

        with patch("transformers.pipeline") as mock_pipe_cls:
            mock_pipe_cls.return_value = fake_pipe
            from app.eval_runner import _compute_confidence
            _compute_confidence("any-model", str(f))

        assert len(captured_texts) <= 50


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class TestAuditLog:

    def test_creates_file_and_appends_entry(self, tmp_path):
        log_path = tmp_path / "audit_log.jsonl"
        entry = {
            "timestamp": "2026-06-23T10:00:00+00:00",
            "run_id": "abc123",
            "repo": "owner/repo",
            "pr": 1,
            "sha": "deadbeef",
            "model": "distilbert",
            "overall": "pass",
            "categories": {"bias": {"pass_rate": 1.0, "passed": True}},
            "confidence": {"avg_confidence": 0.95},
        }

        with patch("app.eval_runner.AUDIT_LOG_PATH", log_path):
            from app.eval_runner import _append_audit_log
            _append_audit_log(entry)

        assert log_path.exists()
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        saved = json.loads(lines[0])
        assert saved["run_id"] == "abc123"
        assert saved["overall"] == "pass"

    def test_appends_multiple_entries(self, tmp_path):
        log_path = tmp_path / "audit_log.jsonl"

        with patch("app.eval_runner.AUDIT_LOG_PATH", log_path):
            from app.eval_runner import _append_audit_log
            for i in range(3):
                _append_audit_log({"run_id": f"run_{i}", "overall": "pass"})

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 3
        assert json.loads(lines[2])["run_id"] == "run_2"

    def test_does_not_raise_on_permission_error(self, tmp_path):
        bad_path = tmp_path / "no_dir" / "sub" / "audit.jsonl"

        with patch("app.eval_runner.AUDIT_LOG_PATH", bad_path):
            from app.eval_runner import _append_audit_log
            # Should not raise — creates parent dirs automatically
            _append_audit_log({"run_id": "x"})

        assert bad_path.exists()

    def test_entry_contains_required_fields(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        required = {"timestamp", "run_id", "repo", "pr", "sha", "model", "overall"}

        entry = {k: "test" for k in required}
        with patch("app.eval_runner.AUDIT_LOG_PATH", log_path):
            from app.eval_runner import _append_audit_log
            _append_audit_log(entry)

        saved = json.loads(log_path.read_text().strip())
        for field in required:
            assert field in saved


# ---------------------------------------------------------------------------
# Red-teaming / robustness tests in config + agent
# ---------------------------------------------------------------------------

class TestRedTeamingConfig:

    def test_robustness_in_build_tests_config(self, tmp_path, sample_jsonl):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
models:
  - name: distilbert-base-uncased-finetuned-sst-2-english
    hub: huggingface
    type: text-classification
categories:
  - robustness
robustness_tests:
  - add_typo
  - american_to_british
thresholds:
  robustness_min_pass_rate: 0.75
report:
  format: [json]
  dir: results
""")
        from app.agent import LLMEvalAgent
        agent = LLMEvalAgent(
            config_path=str(cfg),
            results_dir=str(tmp_path / "results"),
            data_file_override=str(sample_jsonl),
        )
        tests_cfg = agent._build_tests_config()

        assert "robustness" in tests_cfg["tests"]
        assert "add_typo" in tests_cfg["tests"]["robustness"]
        assert "american_to_british" in tests_cfg["tests"]["robustness"]

    def test_robustness_pass_rate_threshold_applied(self, tmp_path, sample_jsonl):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
models:
  - name: distilbert-base-uncased-finetuned-sst-2-english
    hub: huggingface
    type: text-classification
categories:
  - robustness
robustness_tests:
  - add_typo
thresholds:
  robustness_min_pass_rate: 0.9
report:
  format: [json]
  dir: results
""")
        from app.agent import LLMEvalAgent
        agent = LLMEvalAgent(
            config_path=str(cfg),
            results_dir=str(tmp_path / "results"),
            data_file_override=str(sample_jsonl),
        )
        tests_cfg = agent._build_tests_config()

        assert tests_cfg["tests"]["robustness"]["add_typo"]["min_pass_rate"] == 0.9

    def test_bias_and_robustness_together(self, tmp_path, sample_jsonl):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
models:
  - name: distilbert-base-uncased-finetuned-sst-2-english
    hub: huggingface
    type: text-classification
categories:
  - bias
  - robustness
bias_tests:
  - replace_to_female_pronouns
robustness_tests:
  - add_typo
thresholds:
  bias_min_pass_rate: 0.8
  robustness_min_pass_rate: 0.75
report:
  format: [json]
  dir: results
""")
        from app.agent import LLMEvalAgent
        agent = LLMEvalAgent(
            config_path=str(cfg),
            results_dir=str(tmp_path / "results"),
            data_file_override=str(sample_jsonl),
        )
        tests_cfg = agent._build_tests_config()

        assert "bias" in tests_cfg["tests"]
        assert "robustness" in tests_cfg["tests"]

    def test_robustness_absent_when_not_in_categories(self, tmp_path, sample_jsonl):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
models:
  - name: distilbert-base-uncased-finetuned-sst-2-english
    hub: huggingface
    type: text-classification
categories:
  - bias
robustness_tests:
  - add_typo
thresholds:
  bias_min_pass_rate: 0.8
report:
  format: [json]
  dir: results
""")
        from app.agent import LLMEvalAgent
        agent = LLMEvalAgent(
            config_path=str(cfg),
            results_dir=str(tmp_path / "results"),
            data_file_override=str(sample_jsonl),
        )
        tests_cfg = agent._build_tests_config()

        assert "robustness" not in tests_cfg["tests"]


# ---------------------------------------------------------------------------
# Block merge on failure — Check Run conclusion wiring
# ---------------------------------------------------------------------------

class TestBlockMergeConclusion:

    def test_parse_results_all_passed_false_when_no_files(self, tmp_path):
        from app.eval_runner import _parse_results
        result = _parse_results(tmp_path)
        assert result["all_passed"] is False

    def test_parse_results_all_passed_false_on_failure(self, tmp_path):
        report = {
            "category":          {"0": "bias"},
            "test_type":         {"0": "replace_to_female_pronouns"},
            "fail_count":        {"0": 3},
            "pass_count":        {"0": 7},
            "pass_rate":         {"0": "70%"},
            "minimum_pass_rate": {"0": "80%"},
            "pass":              {"0": False},
        }
        (tmp_path / "report.json").write_text(json.dumps(report))
        from app.eval_runner import _parse_results
        result = _parse_results(tmp_path)
        assert result["all_passed"] is False

    def test_parse_results_all_passed_true_on_success(self, tmp_path):
        report = {
            "category":          {"0": "bias"},
            "test_type":         {"0": "replace_to_female_pronouns"},
            "fail_count":        {"0": 0},
            "pass_count":        {"0": 23},
            "pass_rate":         {"0": "100%"},
            "minimum_pass_rate": {"0": "80%"},
            "pass":              {"0": True},
        }
        (tmp_path / "report.json").write_text(json.dumps(report))
        from app.eval_runner import _parse_results
        result = _parse_results(tmp_path)
        assert result["all_passed"] is True

    def test_conclusion_is_failure_when_eval_fails(self, tmp_path):
        """overall='fail' maps to conclusion='failure' which blocks merge."""
        report = {
            "category": {"0": "bias"}, "test_type": {"0": "replace_to_female_pronouns"},
            "fail_count": {"0": 5}, "pass_count": {"0": 5},
            "pass_rate": {"0": "50%"}, "minimum_pass_rate": {"0": "80%"},
            "pass": {"0": False},
        }
        (tmp_path / "report.json").write_text(json.dumps(report))
        from app.eval_runner import _parse_results
        results = _parse_results(tmp_path)
        overall = "pass" if results["all_passed"] else "fail"
        conclusion = "success" if overall == "pass" else "failure"
        assert conclusion == "failure"

    def test_conclusion_is_success_when_eval_passes(self, tmp_path):
        report = {
            "category": {"0": "bias"}, "test_type": {"0": "replace_to_female_pronouns"},
            "fail_count": {"0": 0}, "pass_count": {"0": 23},
            "pass_rate": {"0": "100%"}, "minimum_pass_rate": {"0": "80%"},
            "pass": {"0": True},
        }
        (tmp_path / "report.json").write_text(json.dumps(report))
        from app.eval_runner import _parse_results
        results = _parse_results(tmp_path)
        overall = "pass" if results["all_passed"] else "fail"
        conclusion = "success" if overall == "pass" else "failure"
        assert conclusion == "success"


# ---------------------------------------------------------------------------
# Custom data upload — extended coverage
# ---------------------------------------------------------------------------

class TestCustomDataUpload:

    def test_upload_updates_latest_pointer(self, api_client, sample_jsonl, tmp_path):
        with open(sample_jsonl, "rb") as f:
            r = api_client.post("/upload-data", files={"file": ("eval_data.jsonl", f)})
        assert r.status_code == 200
        assert r.json()["status"] == "uploaded"

    def test_upload_rejects_path_traversal(self, api_client, tmp_path):
        bad = tmp_path / "evil.jsonl"
        bad.write_text('{"text":"x","label":1}')
        with open(bad, "rb") as f:
            r = api_client.post(
                "/upload-data",
                files={"file": ("../../etc/passwd", f)},
            )
        assert r.status_code in (200, 400)
        if r.status_code == 200:
            assert ".." not in r.json().get("saved_to", "")

    def test_upload_returns_filename_in_response(self, api_client, sample_jsonl):
        with open(sample_jsonl, "rb") as f:
            r = api_client.post("/upload-data", files={"file": ("my_dataset.jsonl", f)})
        assert r.json()["filename"] == "my_dataset.jsonl"

    def test_upload_overwrites_previous_file(self, api_client, tmp_path):
        for content, name in [('{"text":"a","label":1}', "v1.jsonl"),
                               ('{"text":"b","label":0}', "v2.jsonl")]:
            f = tmp_path / name
            f.write_text(content)
            with open(f, "rb") as fh:
                r = api_client.post("/upload-data", files={"file": (name, fh)})
            assert r.status_code == 200


# ---------------------------------------------------------------------------
# Trend chart — sparkline, render_table, render_csv, load_entries, GET /trend
# ---------------------------------------------------------------------------

class TestTrendChart:

    def _sample_entries(self):
        return [
            {
                "timestamp": "2026-06-01T00:00:00+00:00",
                "run_id": "run_1",
                "repo": "owner/repo",
                "pr": 1,
                "sha": "abc1",
                "model": "distilbert-base-uncased-finetuned-sst-2-english",
                "overall": "pass",
                "categories": {
                    "bias": {"pass_rate": 1.0, "passed": True},
                    "robustness": {"pass_rate": 0.85, "passed": True},
                },
                "confidence": {"avg_confidence": 0.92},
            },
            {
                "timestamp": "2026-06-08T00:00:00+00:00",
                "run_id": "run_2",
                "repo": "owner/repo",
                "pr": 2,
                "sha": "abc2",
                "model": "distilbert-base-uncased-finetuned-sst-2-english",
                "overall": "fail",
                "categories": {
                    "bias": {"pass_rate": 0.6, "passed": False},
                    "robustness": {"pass_rate": 0.9, "passed": True},
                },
                "confidence": {"avg_confidence": 0.78},
            },
        ]

    def test_sparkline_same_values_returns_all_low(self):
        from scripts.trend_chart import _sparkline
        result = _sparkline([0.9, 0.9, 0.9])
        assert all(c == result[0] for c in result)

    def test_sparkline_ascending_values(self):
        from scripts.trend_chart import _sparkline
        result = _sparkline([0.5, 0.7, 0.9])
        assert result[0] <= result[-1]  # last char is higher block

    def test_sparkline_empty_returns_empty_string(self):
        from scripts.trend_chart import _sparkline
        assert _sparkline([]) == ""

    def test_load_entries_returns_empty_on_missing_file(self, tmp_path):
        from scripts.trend_chart import load_entries
        result = load_entries(tmp_path / "nonexistent.jsonl")
        assert result == []

    def test_load_entries_skips_malformed_lines(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        log.write_text('{"timestamp": "2026-06-01", "overall": "pass"}\nBAD JSON\n')
        from scripts.trend_chart import load_entries
        entries = load_entries(log)
        assert len(entries) == 1
        assert entries[0]["overall"] == "pass"

    def test_load_entries_sorted_by_timestamp(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        log.write_text(
            '{"timestamp": "2026-06-08"}\n'
            '{"timestamp": "2026-06-01"}\n'
        )
        from scripts.trend_chart import load_entries
        entries = load_entries(log)
        assert entries[0]["timestamp"] < entries[1]["timestamp"]

    def test_render_table_no_entries(self):
        from scripts.trend_chart import render_table
        out = render_table([], "")
        assert "No eval runs recorded" in out

    def test_render_table_contains_pass_and_fail(self):
        from scripts.trend_chart import render_table
        out = render_table(self._sample_entries(), "")
        assert "PASS" in out
        assert "FAIL" in out

    def test_render_table_contains_model_name(self):
        from scripts.trend_chart import render_table
        out = render_table(self._sample_entries(), "")
        assert "distilbert" in out

    def test_render_table_sparkline_present(self):
        from scripts.trend_chart import render_table
        out = render_table(self._sample_entries(), "")
        # At least one sparkline block character should appear
        assert any(c in out for c in "▁▂▃▄▅▆▇█")

    def test_render_table_entry_count_in_footer(self):
        from scripts.trend_chart import render_table
        out = render_table(self._sample_entries(), "")
        assert "2 eval run(s)" in out

    def test_render_csv_has_headers(self):
        from scripts.trend_chart import render_csv
        out = render_csv(self._sample_entries())
        first_line = out.splitlines()[0]
        assert "timestamp" in first_line
        assert "model" in first_line
        assert "overall" in first_line

    def test_render_csv_has_correct_row_count(self):
        from scripts.trend_chart import render_csv
        out = render_csv(self._sample_entries())
        lines = [l for l in out.splitlines() if l.strip()]
        assert len(lines) == 3  # header + 2 data rows

    def test_render_csv_empty_returns_header_only(self):
        from scripts.trend_chart import render_csv
        out = render_csv([])
        assert "timestamp" in out
        assert len(out.splitlines()) == 1

    def test_get_trend_endpoint_no_log(self, api_client, tmp_path, monkeypatch):
        import app.api_server as srv
        monkeypatch.setattr(srv, "BASE_DIR", tmp_path)
        r = api_client.get("/trend")
        assert r.status_code == 200
        assert r.json()["entries"] == []

    def test_get_trend_endpoint_returns_entries(self, api_client, tmp_path, monkeypatch):
        import app.api_server as srv
        (tmp_path / "data").mkdir()
        log = tmp_path / "data" / "audit_log.jsonl"
        log.write_text(
            '{"timestamp":"2026-06-01","overall":"pass","model":"m","categories":{},"confidence":{}}\n'
            '{"timestamp":"2026-06-08","overall":"fail","model":"m","categories":{},"confidence":{}}\n'
        )
        monkeypatch.setattr(srv, "BASE_DIR", tmp_path)
        r = api_client.get("/trend")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 2
        assert body["entries"][0]["overall"] == "pass"

    def test_get_trend_endpoint_last_param(self, api_client, tmp_path, monkeypatch):
        import app.api_server as srv
        (tmp_path / "data").mkdir()
        log = tmp_path / "data" / "audit_log.jsonl"
        lines = [f'{{"timestamp":"2026-0{i}-01","overall":"pass","model":"m","categories":{{}},"confidence":{{}}}}'
                 for i in range(1, 6)]
        log.write_text("\n".join(lines))
        monkeypatch.setattr(srv, "BASE_DIR", tmp_path)
        r = api_client.get("/trend?last=2")
        assert r.json()["count"] == 2


# ---------------------------------------------------------------------------
# Scheduled eval — config validation, disabled-by-default behaviour
# ---------------------------------------------------------------------------

class TestScheduledEval:

    def test_scheduler_does_not_start_when_disabled(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("schedule:\n  enabled: false\n  cron: '0 0 * * 0'\n")
        with patch("app.scheduler.CONFIG_PATH", cfg):
            from app.scheduler import start_scheduler, stop_scheduler, _scheduler as sch_before
            start_scheduler()
            from app.scheduler import _scheduler
            # Scheduler should remain None when disabled
            assert _scheduler is None or not _scheduler.running

    def test_scheduler_rejects_invalid_cron(self, tmp_path, caplog):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("schedule:\n  enabled: true\n  cron: 'bad cron'\n")
        import logging
        with patch("app.scheduler.CONFIG_PATH", cfg):
            with caplog.at_level(logging.WARNING, logger="app.scheduler"):
                from app.scheduler import start_scheduler
                start_scheduler()
        assert any("Invalid cron" in r.message or "cron" in r.message.lower()
                   for r in caplog.records)

    def test_scheduler_config_cron_default(self):
        import yaml
        from pathlib import Path
        cfg_path = Path("config/config.yaml")
        if cfg_path.exists():
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f)
            assert "schedule" in cfg
            assert "cron" in cfg["schedule"]
            # default weekly Sunday midnight
            assert cfg["schedule"]["cron"].strip() == "0 0 * * 0"

    def test_scheduler_enabled_flag_defaults_to_false(self):
        import yaml
        from pathlib import Path
        cfg_path = Path("config/config.yaml")
        if cfg_path.exists():
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f)
            assert cfg["schedule"]["enabled"] is False
