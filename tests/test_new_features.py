"""
Unit tests for new features:
  - Confidence score reporting (_compute_confidence)
  - Audit log (_append_audit_log)
  - Red-teaming / robustness tests in config + agent
  - Block merge on failure (Check Run conclusion wiring)
  - Custom data upload (POST /upload-data) — extended coverage
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
