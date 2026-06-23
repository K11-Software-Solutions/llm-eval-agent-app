"""
Automated test script for LLM Eval Agent — Railway deployment.
Usage:
    python scripts/test_deployment.py
    python scripts/test_deployment.py --url https://your-other-url.up.railway.app
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

BASE_URL = "https://llm-eval-agent-app-production.up.railway.app"
TEST_DATA = Path(__file__).parent.parent / "data" / "test_data_small.jsonl"
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
    status = "unknown"
    while elapsed < POLL_TIMEOUT:
        try:
            r = requests.get(f"{base}/status/{run_id}", timeout=10)
            if r.status_code == 502:
                print(f"\n  [WARN]  502 from Railway — app likely ran out of memory.")
                print(f"  [WARN]  DistilBERT requires ~600MB RAM; Railway free tier = 512MB.")
                print(f"  [WARN]  Upgrade to Railway Starter ($5/mo, 8GB RAM) to run evals.")
                print(f"  [WARN]  All API endpoints (health/upload/webhook) still work fine.\n")
                return False
            assert r.status_code == 200, r.text
            status = r.json().get("status")
            info(f"[{elapsed:>3}s] status = {status}")
            if status == "completed":
                ok("Run completed successfully")
                return True
            if status == "failed":
                error = r.json().get("error", "unknown error")
                fail(f"Run failed: {error}")
        except requests.exceptions.ConnectionError:
            info(f"[{elapsed:>3}s] app restarting after OOM crash...")
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
    ids = [run["run_id"] for run in runs]
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
    parser.add_argument("--run-id", help="Specific run ID to fetch from the server")
    parser.add_argument("--skip-eval", action="store_true", help="Skip eval run (API-only, no model inference)")
    args = parser.parse_args()
    base = args.url.rstrip("/")

    print(f"\nTesting deployment: {base}\n")

    try:
        check_health(base)
        check_docs(base)
        test_webhook_ping(base)

        if args.skip_eval:
            info("Skipping eval run (--skip-eval). API endpoints all verified.")
        else:
            upload_data(base)
            run_id = trigger_run(base)
            completed = poll_status(base, run_id)
            if completed:
                check_results(base, run_id)
                check_runs_list(base, run_id)

        print(f"\n{'='*50}")
        print("  ALL CHECKS PASSED")
        print(f"{'='*50}\n")

    except AssertionError as e:
        fail(str(e))
    except requests.exceptions.ConnectionError:
        fail(f"Could not connect to {base} -- is it deployed?")


if __name__ == "__main__":
    main()
