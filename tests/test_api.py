"""Unit tests for app/api_server.py REST endpoints."""

import json
import io

import pytest


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_runs_empty(api_client):
    r = api_client.get("/runs")
    assert r.status_code == 200
    assert "runs" in r.json()
    assert isinstance(r.json()["runs"], list)


def test_upload_data_jsonl(api_client, sample_jsonl):
    with open(sample_jsonl, "rb") as f:
        r = api_client.post("/upload-data", files={"file": ("test.jsonl", f)})
    assert r.status_code == 200
    assert r.json()["status"] == "uploaded"
    assert r.json()["filename"] == "test.jsonl"


def test_upload_data_csv(api_client, tmp_path):
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("text,label\nGreat,1\nTerrible,0\n")
    with open(csv_file, "rb") as f:
        r = api_client.post("/upload-data", files={"file": ("data.csv", f)})
    assert r.status_code == 200
    assert r.json()["filename"] == "data.csv"


def test_status_unknown_run(api_client):
    r = api_client.get("/status/nonexistent_run_id")
    assert r.status_code == 200
    assert r.json()["status"] == "unknown"


def test_results_not_found(api_client):
    r = api_client.get("/results/nonexistent_run_id")
    assert r.status_code == 404


def test_results_file_not_found(api_client):
    r = api_client.get("/results/nonexistent/some_file.json")
    assert r.status_code in (400, 404)


def test_path_traversal_blocked(api_client):
    r = api_client.get("/results/../../../etc/passwd")
    assert r.status_code in (400, 404)


def test_logs_no_file(api_client):
    r = api_client.get("/logs/nonexistent_run_id")
    assert r.status_code == 200
    assert "No log file found" in r.json()["log"]


def test_run_tests_returns_run_id(api_client, sample_jsonl):
    # Upload data first so the run has a data file
    with open(sample_jsonl, "rb") as f:
        api_client.post("/upload-data", files={"file": ("test.jsonl", f)})
    r = api_client.post("/run-tests")
    assert r.status_code == 200
    assert "run_id" in r.json()
    assert r.json()["status"] == "started"


def test_delete_nonexistent_run(api_client):
    r = api_client.delete("/runs/nonexistent_run_id")
    assert r.status_code == 404
