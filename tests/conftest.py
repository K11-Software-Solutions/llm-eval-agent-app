"""
Shared pytest fixtures for LLM Eval Agent tests.
Results for each test are stored in results/tests/<test_node_id>/
"""

import json
import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture
def sample_jsonl(tmp_path):
    """Small JSONL test data file."""
    data = [
        {"text": "She delivered an outstanding presentation.", "label": 1},
        {"text": "He completed the project under budget.", "label": 1},
        {"text": "She failed to meet the deadline.", "label": 0},
        {"text": "He made errors in the report.", "label": 0},
        {"text": "This product is excellent and easy to use.", "label": 1},
        {"text": "Absolutely broken and unusable.", "label": 0},
    ]
    p = tmp_path / "test_data.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in data))
    return p


@pytest.fixture
def sample_config(tmp_path):
    """Minimal config.yaml for testing."""
    cfg = """
models:
  - name: distilbert-base-uncased-finetuned-sst-2-english
    hub: huggingface
    type: text-classification

categories:
  - bias
  - robustness

thresholds:
  min_pass_rate: 0.5
  bias_min_pass_rate: 0.5
  robustness_min_pass_rate: 0.5
  min_gender_f1_score: 0.3

report:
  format: [json]
  dir: results
"""
    p = tmp_path / "config.yaml"
    p.write_text(cfg)
    return p


@pytest.fixture
def sample_report():
    """Minimal langtest report dict."""
    return {
        "category":          {"0": "bias", "1": "robustness"},
        "test_type":         {"0": "replace_to_female_pronouns", "1": "add_typo"},
        "fail_count":        {"0": 0, "1": 1},
        "pass_count":        {"0": 5, "1": 9},
        "pass_rate":         {"0": "100%", "1": "90%"},
        "minimum_pass_rate": {"0": "80%", "1": "75%"},
        "pass":              {"0": True, "1": True},
    }


@pytest.fixture
def results_dir(request, tmp_path):
    """
    Per-test results directory at results/tests/<safe_test_id>/.
    Cleaned up only on test pass; kept on failure for inspection.
    """
    safe_id = request.node.nodeid.replace("/", "_").replace("::", "__").replace(" ", "_")
    out = ROOT / "results" / "tests" / safe_id
    out.mkdir(parents=True, exist_ok=True)

    yield out

    if request.node.rep_call.passed if hasattr(request.node, "rep_call") else True:
        shutil.rmtree(out, ignore_errors=True)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


@pytest.fixture
def api_client():
    """FastAPI TestClient for the main app."""
    from app.main import app
    return TestClient(app)
