"""Unit tests for app/agent.py"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.agent import LLMEvalAgent, _safe_name


# ── helper tests ──────────────────────────────────────────────────────────────

def test_safe_name_normal():
    assert _safe_name("distilbert-base") == "distilbert-base"


def test_safe_name_spaces_and_slashes():
    assert _safe_name("my model/v2 test") == "my_model_v2_test"


def test_safe_name_none():
    assert _safe_name(None) == "model"


# ── init tests ────────────────────────────────────────────────────────────────

def test_init_valid(sample_config, sample_jsonl):
    agent = LLMEvalAgent(
        config_path=str(sample_config),
        data_file_override=str(sample_jsonl),
    )
    assert agent.models
    assert "bias" in agent.categories
    assert agent.data_file == Path(sample_jsonl).as_posix()


def test_init_missing_data_file(sample_config, tmp_path):
    with pytest.raises(FileNotFoundError, match="Data file not found"):
        LLMEvalAgent(
            config_path=str(sample_config),
            data_file_override=str(tmp_path / "nonexistent.jsonl"),
        )


def test_init_no_data_file(sample_config):
    with pytest.raises(FileNotFoundError):
        LLMEvalAgent(config_path=str(sample_config))


def test_posix_path_conversion(sample_config, sample_jsonl):
    """Windows backslash paths must be converted to POSIX for langtest."""
    win_path = str(sample_jsonl).replace("/", "\\")
    agent = LLMEvalAgent(
        config_path=str(sample_config),
        data_file_override=win_path,
    )
    assert "\\" not in agent.data_file


# ── _build_tests_config ───────────────────────────────────────────────────────

def test_build_tests_config_all_categories(sample_config, sample_jsonl):
    agent = LLMEvalAgent(
        config_path=str(sample_config),
        data_file_override=str(sample_jsonl),
    )
    agent.categories = ["bias", "fairness", "robustness"]
    cfg = agent._build_tests_config()
    assert "bias" in cfg["tests"]
    assert "fairness" in cfg["tests"]
    assert "robustness" in cfg["tests"]
    assert "defaults" in cfg["tests"]


def test_build_tests_config_bias_only(sample_config, sample_jsonl):
    agent = LLMEvalAgent(
        config_path=str(sample_config),
        data_file_override=str(sample_jsonl),
    )
    agent.categories = ["bias"]
    cfg = agent._build_tests_config()
    assert "bias" in cfg["tests"]
    assert "fairness" not in cfg["tests"]
    assert "robustness" not in cfg["tests"]


def test_build_tests_config_thresholds(sample_config, sample_jsonl):
    agent = LLMEvalAgent(
        config_path=str(sample_config),
        data_file_override=str(sample_jsonl),
    )
    agent.categories = ["bias"]
    cfg = agent._build_tests_config()
    bias_rate = cfg["tests"]["bias"]["replace_to_female_pronouns"]["min_pass_rate"]
    assert isinstance(bias_rate, float)
    assert 0.0 <= bias_rate <= 1.0


# ── run_tests (mocked harness) ────────────────────────────────────────────────

def test_run_tests_mocked(sample_config, sample_jsonl, tmp_path):
    """run_tests calls Harness.generate().run() and saves a report."""
    mock_harness = MagicMock()
    mock_harness.generate.return_value = mock_harness
    mock_harness.run.return_value = mock_harness

    with patch("app.agent.Harness", return_value=mock_harness):
        agent = LLMEvalAgent(
            config_path=str(sample_config),
            results_dir=str(tmp_path),
            data_file_override=str(sample_jsonl),
        )
        agent.run_tests()

    mock_harness.generate.assert_called_once()
    mock_harness.run.assert_called_once()
    mock_harness.report.assert_called()
