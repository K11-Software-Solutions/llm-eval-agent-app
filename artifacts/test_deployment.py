"""
Automated test script for LLM Eval Agent — Railway deployment.
Usage:
    python artifacts/test_deployment.py
    python artifacts/test_deployment.py --url https://your-other-url.up.railway.app
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

BASE_URL = "https://llm-eval-agent-app-production.up.railway.app"
TEST_DATA = Path(__file__).parent.parent / "data" / "test_data.jsonl"
POLL_INTERVAL = 5   # seconds between status checks
POLL_TIMEOUT  = 120 # seconds before giving up


def ok(msg):   print(f"  [PASS]  {msg}")
def fail(msg): print(f"  [FAIL]  {msg}"); sys.exit(1)
def info(msg): print(f"  [INFO]  {msg}")
def header(msg): print(f"\n{'-'*50}\n{msg}\n{'-'*50}")


def check_health(base):
    header("1. Health check")
    r = requests.get(f"{base}/health", timeout=10)
    assert r.status_code == 200 and r.json().get("status") == "ok", r.text
    ok(f"GET /health -> {r.json()}")


def check_docs(base):
    header("2. Swagger docs")
    r = requests.get(f"{base}/docs", timeout=10)
    assert r.status_code == 200, f"HTTP {r.status_code}"
    ok("GET /docs -> 200 (Swagger UI reachable)")


def upload_data(base):
    header("3. Upload test data")
    if not TEST_DATA.exists():
        fail(f"Test data not found: {TEST_DATA}")
    with open(TEST_DATA, "rb") as f:
        r = requests.post(f"{base}/upload-data", files={"file": (TEST_DATA.name, f)}, timeout=30)
    assert r.status_code == 200, r.text
    ok(f"POST /upload-data -> {r.json()['status']} ({r.json()['filename']})")
    return r.json()["filename"]


def trigger_run(base):
    header("4. Trigger eval run")
    r = requests.post(f"{base}/run-tests", timeout=30)
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]
    ok(f"POST /run-tests -> run_id: {run_id}")
    return run_id


def poll_status(base, run_id):
    header("5. Poll run status")
    elapsed = 0
    while elapsed < POLL_TIMEOUT:
        r = requests.get(f"{base}/status/{run_id}", timeout=10)
        assert r.status_code == 200, r.text
        status = r.json().get("status")
        info(f"[{elapsed:>3}s] status = {status}")
        if status == "completed":
            ok("Run completed successfully")
            return True
        if status == "failed":
            error = r.json().get("error", "unknown error")
            fail(f"Run failed: {error}")
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
    fail(f"Timed out after {POLL_TIMEOUT}s — last status: {status}")


def check_results(base, run_id):
    header("6. Check results")
    r = requests.get(f"{base}/results/{run_id}", timeout=10)
    assert r.status_code == 200, r.text
    files = r.json().get("files", [])
    if not files:
        fail("No result files found")
    for f in files:
        ok(f"Result file: {f}")
    return files


def check_runs_list(base, run_id):
    header("7. Verify run appears in /runs")
    r = requests.get(f"{base}/runs", timeout=10)
    assert r.status_code == 200, r.text
    runs = r.json().get("runs", [])
    ids = [r["run_id"] for r in runs]
    assert run_id in ids, f"run_id {run_id} not found in /runs"
    ok(f"Found {len(runs)} total run(s) — current run listed")


def test_webhook_ping(base):
    header("8. Webhook endpoint smoke test")
    r = requests.post(
        f"{base}/github/webhook",
        headers={"X-GitHub-Event": "ping", "Content-Type": "application/json"},
        json={"zen": "test"},
        timeout=10,
    )
    # 200 or 400/422 are both acceptable — 404/500 are not
    assert r.status_code < 500, f"Server error: {r.status_code} {r.text}"
    ok(f"POST /github/webhook (ping) -> HTTP {r.status_code}")


def main():
    parser = argparse.ArgumentParser(description="Test LLM Eval Agent deployment")
    parser.add_argument("--url", default=BASE_URL, help="Base URL of the deployment")
    args = parser.parse_args()
    base = args.url.rstrip("/")

    print(f"\nTesting deployment: {base}\n")

    try:
        check_health(base)
        check_docs(base)
        upload_data(base)
        run_id = trigger_run(base)
        poll_status(base, run_id)
        check_results(base, run_id)
        check_runs_list(base, run_id)
        test_webhook_ping(base)

        print(f"\n{'='*50}")
        print("  ALL CHECKS PASSED")
        print(f"{'='*50}\n")

    except AssertionError as e:
        fail(str(e))
    except requests.exceptions.ConnectionError:
        fail(f"Could not connect to {base} — is it deployed?")


if __name__ == "__main__":
    main()
